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
from ..proto import service_pb2 as service_proto

def get_unused_port():
    with socket.socket() as sock:
        sock.bind(('', 0))
        return sock.getsockname()[1]

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
        self.port = None

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

            if self.is_simulated and 'simulated_service_type' in service_info:
                service_type = service_info['simulated_service_type']

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

        # Start the logging.
        self.start_logging_proxy()
        self.setup_logging()

        # Start the server
        self.start()

        # Start the startup services.
        #for service_name in self.startup_services:
        #    self.start_service(service_name)

        try:
            # For now, wait until Ctrl+C.
            # In the future, monitor services.
            while True:
                self.sleep(1)
        except KeyboardInterrupt:
            self.log.info('Interrupted by the user...')
        finally:
            self.log.info('Shutting down all running services.')
            self.shut_down_all_services()

            # Shut down the server.
            self.shut_down()

            # Wait until we are fully shut down.
            while self.is_running:
                time.sleep(0.1)

            # Stop the logging.
            self.destroy_logging()
            self.stop_logging_proxy()

            self.context = None

    def setup_logging(self):
        '''Set up all logging.
        '''
        self.log_handler = CatkitLogHandler()
        logging.getLogger().addHandler(self.log_handler)
        logging.getLogger().setLevel(logging.DEBUG)

        #self.log_console = LogConsole()
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
        request.ParseFromString(bytes(data, 'ascii'))

        service_id = request.service_id

        self.start_service(service_id)

        ref = self.services[service_id]

        reply = testbed_proto.StartServiceReply()

        service_ref = reply.service
        service_ref.id = service_id
        service_ref.type = ref.service_type
        service_ref.state = ref.state.value
        service_ref.host = '127.0.0.1'
        service_ref.port = ref.port

        return reply.SerializeToString()

    def on_stop_service(self, data):
        pass  # TODO

    def on_get_info(self, data):
        reply = testbed_proto.GetInfoReply()

        reply.port = self.port
        reply.config = json.dumps(self.config)
        reply.is_simulated = self.is_simulated
        reply.heartbeat_stream_id = 'a'
        reply.logging_ingress_port = self.port + 1
        reply.logging_egress_port = self.port + 2
        reply.data_logging_ingress_port = 0
        reply.tracing_ingress_port = 0

        return reply.SerializeToString()

    def on_get_service_info(self, data):
        request = testbed_proto.GetServiceInfoRequest()
        request.ParseFromString(bytes(data, 'ascii'))

        service_id = request.service_id

        self.start_service(service_id)

        ref = self.services[service_id]

        service_ref = testbed_proto.ServiceReference()
        service_ref.id = service_id
        service_ref.type = ref.service_type
        service_ref.state = ref.state
        service_ref.host = self.host
        service_ref.port = ref.port

        reply = testbed_proto.GetServiceInfoReply()
        reply.service = service_ref

        return reply.SerializeToString()

    def on_register_service(self, data):
        pass  # TODO

    def on_update_service_status(self, data):
        request = testbed_proto.UpdateServiceStateRequest()
        request.ParseFromString(bytes(data, 'ascii'))

        service_id = request.service_id
        new_state = request.new_state  # TODO: conversion

        self.services[service_id].update_state(new_state)

        reply = testbed_proto.UpdateServiceStateReply()
        reply.new_state = request.new_state

        return reply.SerializeToString()

    def start_service(self, service_id):
        '''Start a service.

        Parameters
        ----------
        service_id : string
            The identifier of the service. This should correspond to an entry in the services section of
            the configuration of this testbed.

        Raises
        ------
        RuntimeError
            If the service is not found in the configuration.
            If the service type path did not contain an executable or Python script.
        ValueError
            If the service type could not be found in the known services paths.
        '''
        self.log.debug(f'Trying to start service "{service_id}".')

        if service_id not in self.services:
            raise RuntimeError(f'Service "{service_id}" is not a known service.')

        service_type = self.services[service_id].service_type

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
            self.log.warning(f"Could not find the script/executable for service type \"{service_type}\".")

            raise RuntimeError(f"Service '{service_id}' is not Python or C++.")

        # Get unused port for this service.
        port = get_unused_port()

        # Build arguments.
        args = [
            '--id', service_id,
            '--port', str(port),
            '--testbed_port', str(self.port)
        ]

        self.log.debug(f'Starting new service with {executable + args}.')

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
        self.services[service_id].port = port

        self.log.info(f'Started service "{service_id}" with type "{service_type}".')

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