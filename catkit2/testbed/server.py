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

from ..catkit_bindings import LogConsole, LogPublish, Server, ServiceState
from .log_handler import *

from ..proto import testbed_pb2 as testbed_proto

class LoggingProxy:
    '''A proxy to collect log messages from services and clients, and re-publish them.

    This proxy operates on a separate thread after it is started.

    Parameters
    ----------
    context : zmq.Context
        A previously-created ZMQ context. All sockets will be created on this context.
    input_port : integer
        The port number for the incoming log messages.
    output_port : integer
        The port number for the outgoing log messages.
    '''
    def __init__(self, context, input_port, output_port):
        self.context = context
        self.input_port = input_port
        self.output_port = output_port

        self.shutdown_flag = threading.Event()
        self.thread = None

    def start(self):
        '''Start the proxy thread.
        '''
        self.thread = threading.Thread(target=self.forwarder)
        self.thread.start()

    def stop(self):
        '''Stop the proxy thread.

        This function waits until the thread is actually stopped.
        '''
        self.shutdown_flag.set()

        if self.thread:
            self.thread.join()

    def forwarder(self):
        '''Create sockets and republish all received log messages.

        .. note::
            This function should not be called directly. Use
            :func:`~catkit2.testbed.LoggingProxy.start` to start the proxy.
        '''
        collector = self.context.socket(zmq.PULL)
        collector.RCVTIMEO = 50
        collector.bind(f'tcp://*:{self.input_port}')

        publicist = self.context.socket(zmq.PUB)
        publicist.bind(f'tcp://*:{self.output_port}')

        while True:
            try:
                log_message = collector.recv_multipart()
                publicist.send_multipart(log_message)
            except zmq.ZMQError as e:
                if e.errno == zmq.EAGAIN:
                    # Timed out.
                    if self.shutdown_flag.is_set():
                        break
                    else:
                        continue
                else:
                    raise RuntimeError('Error during receive') from e

            log_message = log_message[0].decode('ascii')
            log_message = json.loads(log_message)

            print(f'[{log_message["service_name"]}] {log_message["message"]}')

            # TODO: Write to a file.

class ServiceReference:
    '''A reference to a service running on another process.

    TODO: this should probably also contain a service proxy object to the service.

    Parameters
    ----------
    service_id : string
        The identifier of the service.
    service_type : string
        The type of the service.
    state : ServiceState
        The current state of the service.
    '''
    def __init__(self, service_id, service_type, state):
        self.service_id = service_id
        self.service_type = service_type

        self.state = state
        self.process = None

        self.log = logging.getLogger(__name__)

    def update_state(self, new_state):
        self.state = new_state
        self.log.info(f'The state of service "{self.service_id}" is now {new_state}.')

    def send_keyboard_interrupt(self):
        '''Send a keyboard interrupt to the service.
        '''
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
        '''Terminate the service.

        This kills the process directly and should be used as a last resort.
        '''
        try:
            self.process.terminate()
        except psutil.NoSuchProcess:
            # Process was already shut down by itself.
            pass

class Testbed(Server):
    '''Manages services.

    Parameters
    ----------
    port : integer
        The port on which the server should operate.
    is_simulated : boolean
        Whether the server should operate in simulated mode or not.
        This changes whether a simulated or hardware service is launched when
        a specific service is requested.
    config : dictionary
        The full configuration as read in from the configuration files.
    '''
    def __init__(self, port, is_simulated, config):
        super().__init__(port)

        self.is_simulated = is_simulated
        self.config = config

        self.services = {}

        self.log_handler = None
        self.logging_proxy = None
        self.log_console = None
        self.log_publish = None

        self.log = logging.getLogger(__name__)

        self.service_paths = [os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'services'))]
        if 'service_paths' in self.config['testbed']:
            self.service_paths.extend(self.config['testbed']['service_paths'])

        self.startup_services = [self.config['testbed']['safety']['service_name']]
        if 'startup_services' in self.config['testbed']:
            self.startup_services.extend(self.config['testbed']['startup_services'])

        # Fill in services dictionary.
        for service_id, service_info in self.config['services'].items():
            service_type = service_info['service_type']

            self.services[service_id] = ServiceReference(service_id, service_type, ServiceState.CLOSED)

        self.register_request_handler('start_service', self.on_start_service)
        self.register_request_handler('stop_service', self.on_stop_service)
        self.register_request_handler('get_info', self.on_get_info)
        self.register_request_handler('get_service_info', self.on_get_service_info)
        self.register_request_handler('register_service', self.on_register_service)
        self.register_request_handler('update_service_status', self.on_update_service_status)

    def run(self):
        '''Run the main loop of the server.
        '''
        self.context = zmq.Context()

        self.start_logging_proxy()
        self.setup_logging()

        #for service_name in self.startup_services:
        #    self.start_service(service_name)

        try:
            self.run_server()
        except KeyboardInterrupt:
            self.log.info('Interrupted by the user...')
        finally:
            self.log.info('Shutting down all running services.')
            self.shut_down_all_services()

            self.destroy_logging()
            self.stop_logging_proxy()

            self.context = None

    def setup_logging(self):
        '''Set up all logging.
        '''
        self.log_handler = CatkitLogHandler()
        logging.getLogger().addHandler(self.log_handler)
        logging.getLogger().setLevel(logging.DEBUG)

        self.log_console = LogConsole()
        self.log_publish = LogPublish('testbed', f'tcp://localhost:{self.port + 1}')

    def destroy_logging(self):
        '''Shut down all logging.
        '''
        if self.log_handler:
            logging.getLogger().removeHandler(self.log_handler)
            self.log_handler = None

        if self.log_console:
            del self.log_console
            self.log_console = None

        if self.log_publish:
            del self.log_publish
            self.log_publish = None

    def start_logging_proxy(self):
        '''Start the logging proxy.
        '''
        self.logging_proxy = LoggingProxy(self.context, self.port + 1, self.port + 2)
        self.logging_proxy.start()

    def stop_logging_proxy(self):
        '''Stop the logging proxy.
        '''
        if self.logging_proxy:
            self.logging_proxy.stop()
            self.logging_proxy = None

    def on_start_service(self, data):
        request = testbed_proto.StartServiceRequest()
        request.ParseFromString(data)

        service_id = request.service_id

        self.start_service(service_id)

    def on_stop_service(self, data):
        pass  # TODO

    def on_get_info(self, data):
        pass  # TODO

    def on_get_service_info(self, data):
        pass  # TODO

    def on_register_service(self, data):
        pass  # TODO

    def on_update_service_status(self, data):
        pass  # TODO

    def start_service(self, service_id):
        '''Start a service.

        Parameters
        ----------
        service_id : string
            The identifier of the service. This should correspond to an entry in the services section of
            the configuration of this server.

        Raises
        ------
        RuntimeError
            If the service is not found in the configuration.
            If the service type path did not contain an executable or Python script.
        ValueError
            If the service type could not be found in the known services paths.
        '''
        self.log.debug(f'Trying to start service "{service_id}".')

        if service_id not in self.config['services']:
            raise RuntimeError(f'Service "{service_id}" is not a known service.')

        config = self.config['services'][service_id]
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
            raise RuntimeError(f"Service '{service_id}' is not Python or C++.")

        # Build arguments.
        args = [
            '--id', service_id,
            '--port', str(get_unused_port()),
            '--testbed_port', str(self.port)
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
        self.services[service_id].update_state(ServiceState.INITIALIZING)

    def stop_service(self, service_name):
        pass  # TODO

    def resolve_service_type(self, service_type):
        '''Resolve a service type into a path.

        Parameters
        ----------
        service_type : string
            The type of the service.

        Returns
        -------
        string
            The path to where the Python script or executable for the
            service can be found.
        '''
        for base_path in self.service_paths:
            dirname = os.path.join(base_path, service_type)
            if os.path.exists(dirname):
                break
        else:
            raise ValueError(f"Service type '{service_type}' not recognized.")

        return dirname

    def shut_down_all_services(self):
        '''Shut down all running services.

        This sends a keyboard interrupt to all running services, and waits for each
        service to shut down. If a KeyboardInterrupt occurs during this shutdown process,
        all services that have not shut down already will be killed.
        '''
        pass  # TODO
