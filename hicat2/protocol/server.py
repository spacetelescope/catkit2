import sys
import json
import os
import time
import subprocess

import psutil
import zmq

from .constants import *
from ..config import read_config
from ..bindings import Severity, submit_log_entry, LogConsole

import inspect
def log(severity, message):
    stack = inspect.stack()[1]
    filename = stack[1]
    line = stack[2]
    function = stack[3]

    submit_log_entry(filename, line, function, severity, message)

def decode_json(json_bytes):
    try:
        return json.loads(json_bytes.decode('ascii'))
    except json.JSONDecodeError as err:
        raise RuntimeError(f'JSON of data is malformed: "{err.msg}".') from err

class LoggingProxy:
    def __init__(self, context, input_port, output_port):
        pass

    def start(self):
        pass

    def stop(self):
        pass

    def send_log_message(self, severity, message):
        pass

class ServiceReference:
    def __init__(self, process, service_type, service_name, server):
        self.process = process
        self.service_type = service_type
        self.service_name = service_name
        self.server = server

        self._socket_identity = None
        self._request_queue = []
        self.expiry_time = 0
        self._is_ready = False
        self.is_open = False

        self.last_sent_heartbeat = 0

    @property
    def socket_identity(self):
        return self._socket_identity

    @socket_identity.setter
    def socket_identity(self, identity):
        if self._socket_identity is not None:
            raise RuntimeError('Can only set the socket identity once.')

        self._socket_identity = identity

        self.on_heartbeat()

    @property
    def is_alive(self):
        if self.process.is_running():
            if self.is_connected:
                return self.expiry_time > time.time()
            else:
                return True
        return False

    @property
    def is_connected(self):
        return self.socket_identity is not None and self.process.is_running()

    @property
    def is_ready(self):
        return self._is_ready

    def send_request(self, client_identity, request):
        log(Severity.DEBUG, f'Sending request to {self.service_name}.')
        self._request_queue.append([client_identity, request])

        self.dispatch_all()

    def send_configuration(self, configuration):
        log(Severity.DEBUG, f'Sending configuration to {self.service_name}.')

        self.server.send_message(self.socket_identity, CONFIGURATION_ID, data=configuration)

    def dispatch_all(self):
        if self.is_open:
            for client_identity, data in self._request_queue:
                self.server.send_message(self.socket_identity, REQUEST_ID, client_identity=client_identity, data=data)

            self._request_queue = []

    def on_opened(self):
        self.on_heartbeat()

        self.is_open = True

        # Send any messages that were waiting to be sent.
        self.dispatch_all()

    def on_heartbeat(self):
        self.expiry_time = time.time() + HEARTBEAT_INTERVAL * HEARTBEAT_LIVENESS

    def send_heartbeat(self):
        if self.is_connected and (self.last_sent_heartbeat + HEARTBEAT_INTERVAL) < time.time():
            self.last_sent_heartbeat = time.time()

            # Do not add this message to the queue; send it right away.
            log(Severity.DEBUG, f'Sending heartbeat to {self.service_name}.')

            self.server.send_message(self.socket_identity, HEARTBEAT_ID)

    def send_keyboard_interrupt(self):
        ctrl_c_code = ';'.join([
            'import ctypes',
            'kernel = ctypes.windll.kernel32',
            'kernel.FreeConsole()',
            'kernel.AttachConsole({pid})',
            'kernel.SetConsoleCtrlHandler(None, 1)',
            'kernel.GenerateConsoleCtrlEvent(0, 0)'
        ])

        if self.is_alive:
            psutil.Popen([sys.executable, '-c', ctrl_c_code.format(pid=self.process.pid)])

    def terminate(self):
        self.process.terminate()

class TestbedServer:
    def __init__(self, port, is_simulated):
        self.log_console = LogConsole()

        self.port = port
        self.is_simulated = is_simulated
        self.services = {}

        self.is_running = False

        self.config = read_config()

        self.client_message_handlers = {
            REQUEST_ID: self.on_client_request
        }

        self.service_message_handlers = {
            REGISTER_ID: self.on_service_register,
            OPENED_ID: self.on_service_opened,
            HEARTBEAT_ID: self.on_service_heartbeat,
            REPLY_ID: self.on_service_reply
        }

        self.internal_request_handlers = {
            'require_service': self.on_require_service,
            'running_services': self.on_running_services,
            'start_new_experiment': self.on_start_new_experiment,
            'is_simulated': self.on_is_simulated,
            'configuration': self.on_configuration
        }

    def run(self):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.ROUTER)

        self.socket.bind(f'tcp://*:{self.port}')
        self.socket.RCVTIMEO = 100

        self.is_running = True

        self.start_logging_proxy()

        try:
            while self.is_running:
                try:
                    self.purge_stopped_services()
                    self.send_heartbeats()

                    try:
                        # Receive multipart message.
                        parts = self.socket.recv_multipart()

                        # Unpack multipart message.
                        identity, *parts = parts
                        empty, message_source, service_name, message_type, *parts = parts
                        service_name = service_name.decode('ascii')
                    except zmq.ZMQError as e:
                        if e.errno == zmq.EAGAIN:
                            # Timed out.
                            continue
                        else:
                            raise RuntimeError('Error during receive') from e

                    # Handle message
                    if message_source == CLIENT_ID:
                        self.client_message_handlers[message_type](identity, service_name, parts)
                    elif message_source == SERVICE_ID:
                        self.service_message_handlers[message_type](identity, service_name, parts)
                    else:
                        raise RuntimeError('Incoming message did not have a correct message source.')
                except Exception as e:
                    if identity is None:
                        # Error during receive. Reraise.
                        log(Severity.CRITICAL, f'Error during receive: {e}.')
                        raise
                    else:
                        # Something went wrong during handling of the message. Log error and ignore message.
                        log(Severity.ERROR, f'Error during handling of message: {repr(e)}.')
                        continue

        except KeyboardInterrupt:
            print('Interrupted by the user...')
        finally:
            print('Shutting down all running services.')

            self.shut_down_all_services()
            self.is_running = False

            self.stop_logging_proxy()

            self.socket = None
            self.context = None

    def start_logging_proxy(self):
        pass

    def stop_logging_proxy(self):
        pass

    def on_client_request(self, client_identity, service_name, parts):
        request = decode_json(parts[0])
        request_type = request['request_type']
        request_data = request['data']

        log(Severity.DEBUG, f'Handling client request "{request_type}" with data "{request_data}".')

        if service_name == 'server':
            handler = self.internal_request_handlers[request_type]
            handler(client_identity, request_data)
        else:
            if service_name not in self.services:
                self.send_reply_error(client_identity, request_type, f'Service {service_name} has not been started.')
            else:
                service = self.services[service_name]
                service.send_request(client_identity, request_type, request_data)

    def on_require_service(self, client_identity, request_data):
        # Ensure that service is started.
        service_name = request_data['service_name']

        if service_name not in self.services:
            try:
                self.start_service(service_name)
            except Exception as e:
                self.send_reply_error(client_identity, 'require_service', repr(e))
                return

        service = self.services[service_name]

        reply_data = {
            'service_name': service_name,
            'service_type': service.service_type,
            'is_connected': service.is_connected,
            'is_open': service.is_open
        }

        self.send_reply_ok(client_identity, 'require_service', reply_data)

    def on_running_services(self, client_identity, request_data):
        reply_data = {}

        for service_name, service in self.services.items():
            reply_data[service_name] = {
                'service_type': service.service_type,
                'is_connected': service.is_connected,
                'is_open': service.is_open
            }

        self.send_reply_ok(client_identity, 'running_services', reply_data)

    def on_start_new_experiment(self, client_identity, request_data):
        pass

    def on_is_simulated(self, client_identity, request_data):
        self.send_reply_ok(client_idenity, 'is_simulated', self.is_simulated)

    def on_configuration(self, client_identity, request_data):
        self.send_reply_ok(client_identity, 'configuration', self.config)

    def on_service_register(self, service_identity, service_name, parts):
        data = decode_json(parts[0])

        log(Severity.DEBUG, f'Handling service register for "{service_name}" with data "{data}".')

        if service_name in self.services:
            # Service was started by this server.
            service = self.services[service_name]
        else:
            # Service was not started by this server but just registered.
            process = psutil.Process(data['pid'])
            service_type = data['service_type']

            service = ServiceReference(process, service_type, service_name, self)
            self.services[service_name] = service

        service.socket_identity = service_identity
        service.send_configuration(self.config['services'][service_name])

    def on_service_opened(self, service_identity, service_name, parts):
        log(Severity.DEBUG, f'Handling service opened for "{service_name}".')

        service = self.services[service_name]
        service.on_opened()
        service.on_heartbeat()

    def on_service_heartbeat(self, service_identity, service_name, parts):
        log(Severity.DEBUG, f'Handling service heartbeat for "{service_name}".')

        service = self.services[service_name]
        service.on_heartbeat()

    def on_service_reply(self, service_identity, service_name, parts):
        client_identity = parts[0]
        data = decode_json(parts[1])

        log(Severity.DEBUG, f'Handling service reply for "{service_name}" with data "{data}".')

        service = self.services[service_name]
        service.on_heartbeat()

        self.send_message(client_identity, REPLY_ID, data=data)

    def send_reply_ok(self, identity, reply_type, data):
        reply_data = {
            'status': 'ok',
            'description': 'success',
            'reply_type': reply_type,
            'data': data
        }

        self.send_message(identity, REPLY_ID, data=reply_data)

    def send_reply_error(self, identity, reply_type, description):
        reply_data = {
            'status': 'error',
            'reply_type': reply_type,
            'description': description,
            'data': None
        }

        self.send_message(identity, REPLY_ID, data=reply_data)

    def send_message(self, identity, message_type, client_identity=None, data=None):
        msg = [identity, b'', message_type]

        if client_identity is not None:
            msg += [client_identity]

        if data is not None:
            message = json.dumps(data).encode('ascii')
            msg += [message]

        self.socket.send_multipart(msg)

    def start_service(self, service_name):
        log(Severity.DEBUG, f'Trying to start service "{service_name}".')

        if service_name not in self.config['services']:
            raise RuntimeError(f'Service "{service_name}" is not a known service.')

        service_type = self.config['services'][service_name]['service_type']

        # Resolve module type;
        dirname = self.resolve_service_type(service_type)

        # Find if Python or C++.
        if os.path.exists(os.path.join(dirname, service_type + '.py')):
            executable = [sys.executable, os.path.join(dirname, service_type + '.py')]
        elif os.path.exists(os.path.join(dirname, service_type + '.exe')):
            executable = [os.path.join(dirname, service_type + '.exe')]
        elif os.path.exists(os.path.join(dirname, service_type)):
            executable = [os.path.join(dirname, service_type)]
        else:
            raise RuntimeError(f"Service '{service_name}' is not Python or C++.")

        # Build arguments.
        args = [
            '--name', service_name,
            '--port', str(self.port)
        ]

        # Start process.
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        creationflags = subprocess.CREATE_NEW_CONSOLE

        process = psutil.Popen(executable + args, startupinfo=startupinfo, creationflags=creationflags)#, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Store a reference to the module.
        self.services[service_name] = ServiceReference(process, service_type, service_name, self)

    def resolve_service_type(self, service_type):
        dirname = os.path.join(os.path.dirname(__file__), '..', 'services', service_type)

        if not os.path.exists(dirname):
            raise ServerError(f"Module type '{service_type}' not recognized.")

        return dirname

    def purge_stopped_services(self):
        dead_services = [service_name for service_name, service in self.services.items() if not service.is_alive]

        for service_name in dead_services:
            log(Severity.INFO, f'Service {service_name} shut down. Removing from running services list.')

            del self.services[service_name]

    def send_heartbeats(self):
        for service in self.services.values():
            service.send_heartbeat()

    def shut_down_all_services(self):
        pass
