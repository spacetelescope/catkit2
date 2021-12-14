import sys
import json
import os
import time
import datetime
import subprocess
import traceback
import socket
import threading

import psutil
import zmq
import yaml

from .constants import *
from ..config import read_config_files
from ..catkit_bindings import LogConsole, LogPublish
from .log_handler import *

def decode_json(json_bytes):
    try:
        return json.loads(json_bytes.decode('ascii'))
    except json.JSONDecodeError as err:
        raise RuntimeError(f'JSON of data is malformed: "{err.msg}".') from err

class LoggingProxy:
    def __init__(self, context, input_port, output_port):
        self.context = context
        self.input_port = input_port
        self.output_port = output_port

        self.shutdown_flag = threading.Event()
        self.thread = None

    def start(self):
        self.thread = threading.Thread(target=self.forwarder)
        self.thread.start()

    def stop(self):
        self.shutdown_flag.set()

        if self.thread:
            self.thread.join()

    def forwarder(self):
        collector = self.context.socket(zmq.PULL)
        collector.RCVTIMEO = 50
        collector.bind(f'tcp://*:{self.input_port}')

        publicist = self.context.socket(zmq.PUB)
        publicist.bind(f'tcp://*:{self.output_port}')

        while not self.shutdown_flag.is_set():
            try:
                log_message = collector.recv_multipart()
                publicist.send_multipart(log_message)
            except zmq.ZMQError as e:
                if e.errno == zmq.EAGAIN:
                    # Timed out.
                    continue
                else:
                    raise RuntimeError('Error during receive') from e

            log_message = log_message[0].decode('ascii')
            log_message = json.loads(log_message)

            print(log_message['message'])

            # TODO: Write to a file.

class ServiceReference:
    def __init__(self, process, service_type, service_name, server):
        self.process = process
        self.service_type = service_type
        self.service_name = service_name
        self.server = server
        self.log = logging.getLogger(__name__)

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
        self.log.debug(f'Sending request to {self.service_name}.')
        self._request_queue.append([client_identity, request])

        self.dispatch_all()

    def send_configuration(self, configuration):
        self.log.debug(f'Sending configuration to {self.service_name}.')

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

    @staticmethod
    def wait_for_termination(services, timeout):
        procs = [s.process for n, s in services.items()]

        gone, alive = psutil.wait_procs(procs, timeout)

class TestbedServer:
    def __init__(self, port, is_simulated, config_files):
        self.port = port
        self.is_simulated = is_simulated
        self.config_files = config_files

        self.services = {}
        self.is_running = False

        self.log_handler = None
        self.log = logging.getLogger(__name__)

        self.config = read_config_files(self.config_files)

        self.base_data_path = None

        if 'base_data_path' in self.config['testbed']:
            conf = self.config['testbed']['base_data_path']
            self.base_data_path = conf['default']

            if 'by_hostname' in conf:
                hostname = socket.gethostname()
                if hostname in conf['by_hostname']:
                    self.base_data_path = conf['by_hostname'][hostname]
        elif 'CATKIT_DATA_PATH' in os.environ:
            self.base_data_path = os.environ['CATKIT_DATA_PATH']
        else:
            raise RuntimeError('No data path could be found in the config files nor as an environment variable.')

        self.experiment_path = self.config['testbed']['experiment_path']

        self.start_new_experiment('server_boot')

        self.service_paths = [os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'services'))]
        if 'service_paths' in self.config['testbed']:
            self.service_paths.extend(self.config['testbed']['service_paths'])

        self.startup_services = [self.config['testbed']['safety']['service_name']]
        if 'startup_services' in self.config['testbed']:
            self.startup_services.extend(self.config['testbed']['startup_services'])

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
            'output_path': self.on_output_path,
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
        self.setup_logging()

        for service_name in self.startup_services:
            self.start_service(service_name)

        try:
            while self.is_running:
                self.purge_stopped_services()

                self.send_heartbeats()

                self.handle_incoming_message()

        except KeyboardInterrupt:
            print('Interrupted by the user...')
        finally:
            print('Shutting down all running services.')

            self.shut_down_all_services()

            self.is_running = False

            self.stop_logging_proxy()

            self.socket = None
            self.context = None

    def setup_logging(self):
        self.log_handler = CatkitLogHandler()
        logging.getLogger().addHandler(self.log_handler)

        self.log_console = LogConsole()
        self.log_publish = LogPublish('server', f'tcp://localhost:{self.port + 1}')

    def destroy_logging(self):
        if self.log_handler:
            logging.getLogger().removeHandler(self.log_handler)
            self.log_handler = None

    def purge_stopped_services(self):
        dead_services = [service_name for service_name, service in self.services.items() if not service.is_alive]

        for service_name in dead_services:
            self.log.info(f'Service {service_name} shut down. Removing from running services list.')

            print(f'Service {service_name} stopped.')

            del self.services[service_name]

    def send_heartbeats(self):
        for service in self.services.values():
            service.send_heartbeat()

    def handle_incoming_message(self):
        try:
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
                    return
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
                self.log.critical(f'Error during receive: {traceback.format_exc()}.')
                raise
            else:
                # Something went wrong during handling of the message. Log error and ignore message.
                self.log.error(f'Error during handling of message: {traceback.format_exc()}.')
                return

    def start_logging_proxy(self):
        self.logging_proxy = LoggingProxy(self.context, self.port + 1, self.port + 2)
        self.logging_proxy.start()

    def stop_logging_proxy(self):
        self.logging_proxy.stop()

    def on_client_request(self, client_identity, service_name, parts):
        request = decode_json(parts[0])
        request_type = request['request_type']
        request_data = request['data']

        self.log.debug(f'Handling client request "{request_type}" with data "{request_data}".')

        if service_name == 'server':
            handler = self.internal_request_handlers[request_type]
            handler(client_identity, request_data)
        else:
            if service_name not in self.services:
                self.send_reply_error(client_identity, request_type, f'Service {service_name} has not been started.')
            else:
                service = self.services[service_name]
                service.send_request(client_identity, request)

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
        experiment_name = request_data['experiment_name']
        metadata = request_data.get('metadata', {})

        data_path = self.start_new_experiment(experiment_name)

        self.send_reply_ok(client_identity, 'start_new_experiment', data_path)

    def start_new_experiment(self, experiment_name, metadata=None):
        if metadata is None:
            metadata = {}

        # Get current date and time as a string.
        time_stamp = time.time()
        date_and_time = datetime.datetime.fromtimestamp(time_stamp).strftime("%Y-%m-%dT%H-%M-%S")

        # Create experiment path.
        format_dict = {
            'simulator_or_hardware': 'simulator' if self.is_simulated else 'hardware',
            'date_and_time': date_and_time,
            'experiment_name': experiment_name
        }
        experiment_path = self.experiment_path.format(**format_dict)

        # Create a directory for the output path.
        output_path = os.path.join(self.base_data_path, experiment_path)
        os.makedirs(output_path, exist_ok=True)

        # Write out metadata and configuration files.
        with open(os.path.join(output_path, 'metadata.yml'), 'w') as f:
            yaml.dump(metadata, f)
        with open(os.path.join(output_path, 'config.yml'), 'w') as f:
            yaml.dump(self.config, f)

        self.output_path = output_path
        return output_path

    def on_output_path(self, client_identity, request_data):
        self.send_reply_ok(client_identity, 'output_path', self.output_path)

    def on_is_simulated(self, client_identity, request_data):
        self.send_reply_ok(client_identity, 'is_simulated', self.is_simulated)

    def on_configuration(self, client_identity, request_data):
        self.send_reply_ok(client_identity, 'configuration', self.config)

    def on_service_register(self, service_identity, service_name, parts):
        data = decode_json(parts[0])

        self.log.debug(f'Handling service register for "{service_name}" with data "{data}".')

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

        print(f'Service {service_name} ({service.service_type}) registered.')

    def on_service_opened(self, service_identity, service_name, parts):
        self.log.debug(f'Handling service opened for "{service_name}".')

        service = self.services[service_name]
        service.on_opened()
        service.on_heartbeat()

    def on_service_heartbeat(self, service_identity, service_name, parts):
        if service_name not in self.services:
            self.log.error(f"Received a heartbeat from '{service_name}, which is not running. Ignoring.")
            return

        service = self.services[service_name]
        service.on_heartbeat()

    def on_service_reply(self, service_identity, service_name, parts):
        client_identity = parts[0]
        data = decode_json(parts[1])

        self.log.debug(f'Handling service reply for "{service_name}" with data "{data}".')

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
        self.log.debug(f'Trying to start service "{service_name}".')

        if service_name not in self.config['services']:
            raise RuntimeError(f'Service "{service_name}" is not a known service.')

        config = self.config['services'][service_name]
        service_type = config['service_type']

        if self.is_simulated and 'simulated_service_type' in config:
            service_type = config['simulated_service_type']

        # Resolve service type;
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

        process = psutil.Popen(
            executable + args,
            startupinfo=startupinfo,
            creationflags=creationflags,
            cwd=dirname)

        # Store a reference to the service.
        self.services[service_name] = ServiceReference(process, service_type, service_name, self)

    def resolve_service_type(self, service_type):
        for base_path in self.service_paths:
            dirname = os.path.join(base_path, service_type)
            if os.path.exists(dirname):
                break
        else:
            raise ValueError(f"Service type '{service_type}' not recognized.")

        return dirname

    def shut_down_all_services(self):
        for service in self.services.values():
            service.send_keyboard_interrupt()

        print('Waiting for services to shut down...')

        try:
            ServiceReference.wait_for_termination(self.services, None)
        except KeyboardInterrupt:
            print("Hard shutdown remaining services...")
            for service in self.services.values():
                service.terminate()

        print("All services were shut down safely!")
