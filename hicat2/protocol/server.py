import sys
import json
import os
import time

import psutil
import zmq

from .constants import *
from ..config import read_config

class ServerError(Exception):
	def __init__(self, value):
		self.value = value

	def __str__(self):
		return str(self.value)

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
        self._message_queue = []
        self.expiry_time = 0

        self.last_sent_heartbeat = 0

    @property
    def socket_identity(self):
        return self._socket_identity

    @socket_identity.setter
    def socket_identity(self, identity):
        if self._socket_identity is not None:
            raise RuntimeError('Can only set the socket identity once.')

        self._socket_identity = identity

        self.dispatch_all()

    @property
    def is_alive(self):
        return self.process.is_running() and self.expiry_time > time.time()

    @property
    def is_connected(self):
        return self.socket_identity is not None and self.is_alive

    def send_request(self, client_identity, request):
        self.message_queue.append([REQUEST_ID, client_identity, request])

        self.dispatch_all()

    def send_configuration(self, configuration):
        self.message_queue.append([CONFIGURATION_ID, configuration])

        self.dispatch_all()

    def dispatch_all(self):
        if self.is_connected:
            for message in self.message_queue:
                if len(message) == 3:
                    message_type, client_identity, msg = message
                else:
                    message_type, msg = message
                    client_identity = None

                self.server.send_reply(self.socket_identity, message_type, client_identity=client_identity, reply=msg)

            self.message_queue = []

    def on_heartbeat(self):
        self.expiry_time = time.time() + HEARTBEAT_INTERVAL * HEARTBEAT_LIVENESS

    def send_heartbeat(self):
        if self.is_connected and (self.last_sent_heartbeat + HEARTBEAT_INTERVAL) < time.time():
            self.server.send_reply(self.socket_identity, HEARTBEAT_ID)
            self.last_sent_heartbeat = time.time()

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
    def __init__9self, port, is_simulated):
        def port = port
        self.is_simulated = is_simulated
        self.services = {}

        self.is_running = False

        self.config = read_config()

    def run(self):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.ROUTER)

        self.socket.bind(f'tcp://*:{self.port}')
        self.socket.RCVTIMEO = 100

        self.is_running = True

        self.start_logging_proxy()

        try:
            while self.is_running:
                self.purge_stopped_services()
                self.send_heartbeats()

                try:
                    identity = None

                    try:
                        # Receive multipart message.
                        parts = self.socket.recv_multipart()

                        # Unpack multipart message.
                        identity, *parts = parts
                        empty, message_source, service_name, message_type, *message = parts
                        service_name = service_name.decode('ascii')
                    except zmq.ZMQError as e:
                        if e.errno == zmq.EAGAIN:
                            # Timed out.
                            continue
                        else:
                            raise RuntimeError('Error during receive') from e
                    except ValueError as e:
                        raise ServerError("Incoming message had not enough parts.") from e

                    # Handle message
                    if message_source == CLIENT_ID:
                        reply = self.on_client_message(identity, service_name, message_type, message)
                    elif message_source == SERVICE_ID:
                        reply = self.on_service_message(identity, service_name, message_type, message)
                    else:
                        raise ServerError('Incoming message did not have a correct message source. Ignoring...')

                except Exception as e:
                    if identity is None:
                        # Error during receive. Reraise.
                        raise
                    else:
                        # Something went wrong during handling of the message.
                        # Send error response.
                        reply = {'error_message': repr(e)}
                        self.send_reply(identity, ERROR_ID, reply)

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

    def log(self, log_message):
        pass

    def on_client_message(self, client_identity, service_name, message_type, message):
        if message_type == REQUEST_ID:
            try:
                request = json.loads(message[0].decode('ascii'))
            except json.JSONDecodeError as err:
                raise ServerError(f'JSON of request malformed: "{err.msg}".') from err

            if service_name == 'server':
                self.on_internal_request(client_identity, request)
            else:
                if service_name not in self.services:
                    raise ServerError('Service has not been started.')

                service = self.services[service_name]
                service.send_request(client_identity, request)
        else:
            raise ServerError(f'Message type "{message_type.decode("ascii")}" is not allowed.')

    def on_internal_request(self, client_identity, service_name, request):
        request_type = request['request_type']

        if request_type == 'require_service':
            # Ensure that service is started.
            service_name = request['service_name']

            if service_name not in self.services:
                self.start_service(service_name)

            service = self.services[service_name]

            reply = {
                'service_name': service_name,
                'service_type': service.service_type,
                'is_connected': service.is_connected
            }
        elif request_type == 'running_services':
            # Return the running services.
            reply = {
                'services': {}
            }

            for service_name, service in self.services.items():
                reply['services'][service_name] = {
                    'service_type': service.service_type,
                    'is_connected': service.is_connected
                }
        elif request_type == 'start_new_experiment':
            # TODO: Create new experiment directory and return.
        elif request_type == 'is_simulated':
            reply = {'is_simulated': self.is_simulated}
        elif request_type == 'configuration':
            reply = {'configuration': self.config}
        else:
            raise ServerError(f'Request type "{request_type}" is not allowed.')

        self.send_reply(client_identity, REPLY_ID, reply)

    def start_service(self, service_name):
        if service_name not in self.config['services']:
            raise ServerError(f'Service "{service_name}" is not a known service.')

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
            raise ServerError(f"Service '{service_name}' is not Python or C++.")

        # Build arguments.
        args = [
            '--service_name', service_name,
            '--server_port', str(self.port)
        ]

        # Start process.
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        creationflags = subprocess.CREATE_NEW_CONSOLE

        process = psutil.Popen(executable + args, startupinfo=startupinfo, creationflags=creationflags)#, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Store a reference to the module.
        self.services[service_name] = ServiceReference(process, service_type, service_name, self)

    def on_service_message(self, service_identity, service_name, message_type, message):
        try:
            client_identity, *message = message
            if len(message):
                message = json.loads(message[0].decode('ascii'))
            else:
                message = {}
        except ValueError as e:
            raise ServerError("Incoming message had not enough parts.") from e
        except json.JSONDecodeError as e:
            raise ServerError(f'JSON of request malformed: "{e.msg}".') from e

        if message_type == READY_ID:
            if service_name in self.services:
                # Service was started by this server.
                service = self.services[service_name]
            else:
                # Service was not started by this server, but just registered.
                process = psutil.Process(message['pid'])
                service_type = message['service_type']

                service = ServiceReference(process, service_type, service_name, self)
                self.services[service_name] = service

            service.socket_identity = service_identity
            service.send_configuration(self.config)
        else:
            if service_name not in self.services:
                raise ServerError('Service has not been started.')

            service = self.services[service_name]

            # Any incoming message counts as a heartbeat.
            service.on_heartbeat()

            if message_type == HEARTBEAT_ID:
                return
            elif message_type == REPLY_ID:
                # Forward reply to client.
                self.send_reply(client_identity, REPLY_ID, reply=message)
            else:
                raise ServerError(f'Message type "{message_type.encode("ascii")}" is not allowed.')

    def send_reply(self, identity, message_type, client_identity=None, reply=None):
        msg = [identity, b'', message_type]

        if client_identity is not None:
            msg += [client_identity]

        if reply is not None:
            message = json.dumps(reply).encode('ascii')
            msg += [message]

        self.socket.send_multipart(msg)

    def purge_stopped_services(self):
        dead_services = [service_name for service_name, service in self.services.items() if not service.is_alive]

        for service_name in dead_services:
            del self.services[service_name]

    def send_heartbeats(self):
        for service in self.services.values():
            service.send_heartbeat()

    def shut_down_all_services(self):
        pass
