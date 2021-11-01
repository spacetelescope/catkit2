import zmq
import sys
import json
import os
import subprocess

from .config import read_config

class ServerError(Exception):
	def __init__(self, value):
		self.value = value

	def __str__(self):
		return str(self.value)

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
            from .testbed import ModuleProxy

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

        if self.is_alive:
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
