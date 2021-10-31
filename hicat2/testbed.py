import zmq
import sys
import json
import os
import subprocess
import argparse
from threading import Lock
import signal

from .config import read_config
from .bindings import DataStream

class ServerError(Exception):
	def __init__(self, value):
		self.value = value

	def __str__(self):
		return str(self.value)

class PropertyProxy:
    def __init__(self, property_name, module_proxy):
        self.module_proxy = module_proxy
        self.name = property_name

    def __get__(self, instance, owner=None):
        message_data = {'property_name': self.name}
        data, binary_data = self.module_proxy._make_request('get_property_request', message_data)

        return data['value']

    def __set__(self, instance, value):
        message_data = {'value': value, 'property_name': self.name}
        self.module_proxy._make_request('set_property_request', message_data)

class CommandProxy:
    def __init__(self, command_name, module_proxy):
        self.name = command_name
        self.module_proxy = module_proxy

    def __call__(self, **kwargs):
        message_data = {'arguments': kwargs, 'command_name': self.name}
        data, binary_data = self.module_proxy._make_request('execute_command_request', message_data)

        return data['result']

class ModuleProxy:
    def __init__(self, port):
        self.port = port

        self.lock = Lock()

        self.context = zmq.Context()
        self.socket = None

        self.remake_sockets()

        # Give the module up to five seconds to start up.
        self.socket.RCVTIMEO = 5000

        # Get own name
        self._name = self._make_request('get_name_request')[0]['value']

        # Only give the module up to one second to respond after it has started up.
        self.socket.RCVTIMEO = 1000

        # Set properties
        properties = self.list_all_properties()
        for name in properties:
            prop = PropertyProxy(name, self)
            setattr(self.__class__, name, prop)

        # Set commands
        commands = self.list_all_commands()
        for name in commands:
            cmd = CommandProxy(name, self)
            setattr(self, name, cmd)

        # Set data streams
        datastreams = self.list_all_data_streams()
        for name in datastreams:
            stream = DataStream.open(name, self.name)
            setattr(self, name, stream)

    def remake_sockets(self):
        if self.socket is not None:
            self.socket.close()

        self.socket = self.context.socket(zmq.REQ)
        self.socket.LINGER = 1
        self.socket.RCVTIMEO = 1000

        self.socket.connect(f'tcp://localhost:{self.port}')

    @property
    def name(self):
        return self._name

    def list_all_properties(self):
        message_data = {}
        return self._make_request('list_all_properties_request', message_data)[0]['value']

    def list_all_commands(self):
        message_data = {}
        return self._make_request('list_all_commands_request', message_data)[0]['value']

    def list_all_data_streams(self):
        message_data = {}
        return self._make_request('list_all_data_streams_request', message_data)[0]['value']

    def shut_down(self):
        self._make_request('shut_down_request')

    def _make_request(self, message_type, message_data=None, binary_data=None):
        if message_data is None:
            message_data = {}

        message = {'message_type': message_type, 'message_data': message_data}
        message = json.dumps(message)

        with self.lock:
            if binary_data is None:
                self.socket.send(message.encode('ascii'))
            else:
                self.socket.send(message.encode('ascii'), zmq.SNDMORE)
                self.socket.send(binary_data)

            try:
                reply = self.socket.recv()
                has_binary_data = self.socket.getsockopt(zmq.RCVMORE)

                if has_binary_data:
                    reply_binary_data = self.socket.recv()

                    # Ignore any more message parts (this shouldn't happen)
                    while self.socket.getsockopt(zmq.RCVMORE):
                        self.socket.recv()
                else:
                    reply_binary_data = None
            except zmq.ZMQError as e:
                if e.errno == zmq.EAGAIN:
                    self.remake_sockets()
                    raise ServerError('Module did not respond.')
                else:
                    raise

        try:
            rep_message = json.loads(reply.decode(encoding='ascii'))
        except json.JSONDecodeError as err:
            raise ServerError('JSON of reply malformed: "' + err.msg + '"')

        rep_message_type = rep_message['message_type']
        rep_message_data = rep_message['message_data']

        if rep_message_data['status'] != 'ok':
            raise ServerError(rep_message_data['status_description'])

        return rep_message_data, reply_binary_data

_module_interfaces = {None: ModuleProxy}

def register_module_interface(interface_name):
    def decorator(cls):
        _module_interfaces[interface_name] = cls

        return cls

    return decorator

class Testbed:
    def __init__(self, testbed_server_port):
        self.lock = Lock()

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.RCVTIMEO = 1000

        self.socket.connect(f'tcp://localhost:{testbed_server_port}')

        try:
            self._load_config()
        except zmq.ZMQError:
            raise RuntimeError('Could not connect to testbed server. Did you forget to start it?')

    def _make_request(self, request):
        with self.lock:
            self.socket.send(json.dumps(request).encode('ascii'))

            reply = self.socket.recv()

            # Ignore any more message parts (this shouldn't happen)
            while self.socket.getsockopt(zmq.RCVMORE):
                self.socket.recv()

        reply_json = json.loads(reply.decode(encoding='ascii'))
        return reply_json

    def _load_config(self):
        request = {'message_type': 'config_request'}
        reply = self._make_request(request)

        self.config = reply['config']

    def _get_module_port(self, name):
        request = {'message_type': 'module_port_request', 'module_name': name}
        reply = self._make_request(request)

        if 'port' not in reply:
            raise ValueError(f'The module "{name}" is not known by the server.')

        return reply['port']

    def shut_down_server(self):
        request = {'message_type': 'shut_down_request'}
        self._make_request(request)

    def get_module_proxy(self, name):
        port = self._get_module_port(name)

        # Get the module interface class.
        interface_name = self.config['modules'][name].get('interface')
        module_proxy_class = _module_interfaces[interface_name]

        return module_proxy_class(port)

    def __getattr__(self, item):
        try:
            return self.get_module_proxy(item)
        except Exception as e:
            raise AttributeError(str(e))

class ModuleReference:
    def __init__(self, module_type, module_name, process, port):
        self.module_type = module_type
        self.module_name = module_name
        self.process = process
        self.port = port

    @property
    def is_alive(self):
        return self.process.poll() is None

    def shut_down(self):
        if self.is_alive:
            module = ModuleProxy(self.port)
            module.shut_down()

    def terminate(self):
        ctrl_c_code = ';'.join([
            'import ctypes',
            'kernel = ctypes.windll.kernel32',
            'kernel.FreeConsole()',
            'kernel.AttachConsole({pid})',
            'kernel.SetConsoleCtrlHandler(None, 1)',
            'kernel.GenerateConsoleCtrlEvent(0, 0)'
        ])

        subprocess.Popen([sys.executable, '-c', ctrl_c_code.format(pid=self.process.pid)])

class TestbedServer:
    def __init__(self, port):
        self.port = port
        self.next_module_port = port + 10
        self.modules = {}

        self.is_running = False
        self.request_handlers = {
            'config_request': self.handle_config_request,
            'module_port_request': self.handle_module_port_request,
            'shut_down_request': self.handle_shut_down_request,
        }

        self.config = read_config()

    def run(self):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)

        self.socket.bind(f'tcp://*:{self.port}')

        # Use timeout to allow for periodic checking of self.is_running.
        self.socket.RCVTIMEO = 20

        self.is_running = True
        i = 0

        try:
            while self.is_running:
                try:
                    request = self.socket.recv()
                except zmq.ZMQError as e:
                    if e.errno == zmq.EAGAIN:
                        continue
                    else:
                        raise

                try:
                    try:
                        request = json.loads(request.decode(encoding='ascii'))
                    except json.JSONDecodeError as err:
                        raise ServerError(f'JSON of request malformed: "{err.msg}".')

                    if 'message_type' not in request:
                        raise ServerError('Request must contain a message_type attribute.')

                    if request['message_type'] not in self.request_handlers:
                        raise ServerError(f"Message type {request['message_type']} is not recognized.")

                    reply = self.request_handlers[request['message_type']](request)
                except ServerError as e:
                    reply = {'message_type': 'error_reply', 'description': e.value}

                msg = json.dumps(reply)
                self.socket.send(msg.encode('ascii'))
        except KeyboardInterrupt:
            print('Interrupted by the user...')
        finally:
            print('Shutting down all running modules...')
            self.shut_down_all_modules()

            self.socket = None
            self.context = None

            self.is_running = False

    def handle_config_request(self, request):
        return {'config': self.config}

    def handle_module_port_request(self, request):
        if 'module_name' not in request:
            raise ServerError('A module name is required when asking for a module port.')

        name = request['module_name']

        module_ref = self.get_module_reference(name)
        return {'port': module_ref.port}

    def handle_shut_down_request(self, request):
        self.is_running = False

    def get_module_reference(self, name, auto_start=True):
        if name in self.modules:
            if self.modules[name].is_alive:
                return self.modules[name]

        if not auto_start:
            return None

        return self.start_module(name)

    def start_module(self, name):
        # Check if the module is not already running.
        if name in self.modules:
            if self.modules[name].is_alive:
                raise ServerError(f"Module '{name}' is already running.")

        # Find module type from name.
        if name not in self.config['modules']:
            raise ServerError(f"Module '{name}' has not been found in the config.")

        module_type = self.config['modules'][name]['module_type']

        # Resolve module type;
        dirname = self.resolve_module_type(module_type)

        # Find if Python or C++.
        if os.path.exists(os.path.join(dirname, module_type + '.py')):
            executable = [sys.executable, os.path.join(dirname, module_type + '.py')]
        elif os.path.exists(os.path.join(dirname, module_type + '.exe')):
            executable = [os.path.join(dirname, module_type + '.exe')]
        elif os.path.exists(os.path.join(dirname, module_type)):
            executable = [os.path.join(dirname, module_type)]
        else:
            raise ServerError(f"Module '{name}' is not Python or C++.")

        # Build arguments.
        module_port = self.next_module_port
        self.next_module_port += 2

        args = [
            '--module_name', name,
            '--module_port', str(module_port),
            '--testbed_server_port', str(self.port),
        ]

        # Start process.
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        creationflags = subprocess.CREATE_NEW_CONSOLE

        process = subprocess.Popen(executable + args, startupinfo=startupinfo, creationflags=creationflags)#, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Store a reference to the module.
        self.modules[name] = ModuleReference(module_type, name, process, module_port)

        return self.modules[name]

    def resolve_module_type(self, module_type):
        dirname = os.path.join(os.path.dirname(__file__), 'modules', module_type)

        if not os.path.exists(dirname):
            raise ServerError(f"Module type '{module_type}' not recognized.")

        return dirname

    def shut_down_all_modules(self):
        for module_ref in self.modules.values():
            module_ref.shut_down()

def parse_module_args():
    parser = argparse.ArgumentParser(description='Start the module')
    parser.add_argument('--module_name', type=str, help='The module name.', required=True)
    parser.add_argument('--module_port', type=int, help='The port of this Module.', required=True)
    parser.add_argument('--testbed_server_port', type=int, help='The port of the TestbedServer.', required=True)

    args = parser.parse_args()
    return args
