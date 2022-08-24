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
import numpy as np

from ..catkit_bindings import LogConsole, LogForwarder, Server, ServiceState, DataStream, get_timestamp, is_alive_state
from .logging import *

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

        self.state_stream = DataStream.create('state', service_id, 'int8', [1], 20)
        self.state = state

        self._process_id = 0

        self.host = '127.0.0.1'
        self.port = 0
        self.heartbeat = None

        self.log = logging.getLogger(__name__)

    @property
    def state(self):
        return ServiceState(int(self.state_stream.get()[0]))

    @state.setter
    def state(self, state):
        new_state = np.array([state.value], dtype='int8')
        self.state_stream.submit_data(new_state)

    @property
    def is_alive(self):
        return is_alive_state(self.state)

    @property
    def process(self):
        try:
            return psutil.Process(self.process_id)
        except psutil.NoSuchProcess:
            return None

    def send_keyboard_interrupt(self):
        '''Send a keyboard interrupt to the service.
        '''
        if self.process is None:
            return

        # TODO: Linux/MacOS compatibility.
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
            if self.process:
                self.process.terminate()
        except psutil.NoSuchProcess:
            # Process was already shut down by itself.
            pass

class Testbed:
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
        self.host = '127.0.0.1'
        self.port = port

        self.is_simulated = is_simulated
        self.config = config

        self.services = {}

        self.log_handler = None
        self.logging_proxy = None
        self.log_console = None
        self.log_forwarder = None

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

        # Create server instance and register request handlers.
        self.server = Server(port)

        self.server.register_request_handler('start_service', self.on_start_service)
        self.server.register_request_handler('stop_service', self.on_stop_service)
        self.server.register_request_handler('interrupt_service', self.on_interrupt_service)
        self.server.register_request_handler('terminate_service', self.on_terminate_service)
        self.server.register_request_handler('get_info', self.on_get_info)
        self.server.register_request_handler('get_service_info', self.on_get_service_info)
        self.server.register_request_handler('register_service', self.on_register_service)
        self.server.register_request_handler('shut_down', self.on_shut_down)

        self.is_running = False
        self.shutdown_flag = threading.Event()

        self.heartbeat_stream = DataStream.create('heartbeat', 'testbed', 'uint64', [1], 20)

    def run(self):
        '''Run the main loop of the server.
        '''
        self.is_running = True
        self.shutdown_flag.clear()

        self.context = zmq.Context()

        # Start the logging.
        self.start_logging_proxy()
        self.setup_logging()

        # Start the server
        self.server.start()

        # Start the startup services.
        #for service_name in self.startup_services:
        #    self.start_service(service_name)

        try:
            # For now, wait until Ctrl+C.
            # In the future, monitor services and update heartbeat stream.
            while not self.shutdown_flag.is_set():
                time.sleep(0.01)

                # Probably should do this in a thread.
                heartbeat = np.array([get_timestamp()], dtype='uint64')
                self.heartbeat_stream.submit_data(heartbeat)
        except KeyboardInterrupt:
            self.log.info('Interrupted by the user...')
        finally:
            self.log.info('Shutting down all running services.')
            self.shut_down_all_services()

            # Submit zero heartbeat to signal a dead testbed.
            self.heartbeat_stream.submit_data(np.zeros(1, dtype='uint64'))

            # Shut down the server.
            self.server.stop()

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
        self.log_forwarder = LogForwarder('testbed', f'tcp://localhost:{self.port + 1}')

    def destroy_logging(self):
        '''Shut down all logging.
        '''
        if self.log_handler:
            logging.getLogger().removeHandler(self.log_handler)
            self.log_handler = None

        if self.log_console:
            del self.log_console
            self.log_console = None

        if self.log_forwarder:
            del self.log_forwarder
            self.log_forwarder = None

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

        ref = self.services[service_id]

        reply = testbed_proto.StartServiceReply()

        return reply.SerializeToString()

    def on_stop_service(self, data):
        request = testbed_proto.StopServiceRequest()
        request.ParseFromString(data)

        service_id = request.service_id

        self.stop_service(service_id)

        reply = testbed_proto.StopServiceReply()
        return reply.SerializeToString()

    def on_interrupt_service(self, data):
        request = testbed_proto.InterruptServiceRequest()
        request.ParseFromString(data)

        service_id = request.service_id

        self.interrupt_service(service_id)

        reply = testbed_proto.InterruptServiceReply()
        return reply.SerializeToString()

    def on_terminate_service(self, data):
        request = testbed_proto.TerminateServiceRequest()
        request.ParseFromString(data)

        service_id = request.service_id

        self.terminate_service(service_id)

        reply = testbed_proto.TerminateServiceReply()
        return reply.SerializeToString()

    def on_get_info(self, data):
        reply = testbed_proto.GetInfoReply()

        reply.port = self.port
        reply.config = json.dumps(self.config)
        reply.is_simulated = self.is_simulated
        reply.heartbeat_stream_id = self.heartbeat_stream.stream_id
        reply.logging_ingress_port = self.port + 1
        reply.logging_egress_port = self.port + 2
        reply.data_logging_ingress_port = 0
        reply.tracing_ingress_port = 0

        return reply.SerializeToString()

    def on_get_service_info(self, data):
        request = testbed_proto.GetServiceInfoRequest()
        request.ParseFromString(data)

        service_id = request.service_id

        ref = self.services[service_id]

        reply = testbed_proto.GetServiceInfoReply()

        service_ref = reply.service
        service_ref.id = service_id
        service_ref.type = ref.service_type
        service_ref.state_stream_id = ref.state_stream.stream_id
        service_ref.host = self.host
        service_ref.port = ref.port

        return reply.SerializeToString()

    def on_register_service(self, data):
        request = testbed_proto.RegisterServiceRequest()
        request.ParseFromString(data)

        service = self.services[request.service_id]

        if service.service_type != request.service_type:
            self.log.error('Service was started with the wrong service type.')

            raise RuntimeError('Service registration has the wrong service type.')

        service.host = request.host
        service.port = request.port
        service.process_id = request.process_id
        service.heartbeat = DataStream.open(request.heartbeat_stream_id)

        reply = testbed_proto.RegisterServiceReply()

        reply.state_stream_id = service.state_stream.stream_id

        return reply.SerializeToString()

    def on_shut_down(self, data):
        self.shutdown_flag.set()

        reply = testbed_proto.ShutDownReply()
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
        #startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        creationflags = subprocess.CREATE_NEW_CONSOLE

        process = psutil.Popen(
            executable + args,
            startupinfo=startupinfo,
            creationflags=creationflags,
            cwd=dirname)

        # Store a reference to the service.
        self.services[service_id].state = ServiceState.INITIALIZING
        self.services[service_id].process_id = process.pid
        self.services[service_id].port = port

        self.log.info(f'Started service "{service_id}" with type "{service_type}".')

    def stop_service(self, service_id):
        pass  # TODO

    def interrupt_service(self, service_id):
        self.log.debug(f'Interrupting service "{service_id}".')

        if service_id not in self.services:
            raise RuntimeError(f'Service "{service_id}" is not a known service.')

        self.services[service_id].send_keyboard_interrupt()

    def terminate_service(self, service_id):
        self.log.debug(f'Terminating service "{service_id}".')

        if service_id not in self.services:
            raise RuntimeError(f'Service "{service_id}" is not a known service.')

        self.services[service_id].terminate()

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
