import sys
import json
import os
import time
import subprocess
import socket
import threading
import contextlib

import psutil
import zmq
import numpy as np

from ..catkit_bindings import LogForwarder, Server, ServiceState, DataStream, get_timestamp, is_alive_state, Client
from .logging import *

from ..proto import testbed_pb2 as testbed_proto
from ..proto import service_pb2 as service_proto

SERVICE_LIVELINESS = 5

def get_unused_port(num_ports=1):
    ports = []

    with contextlib.ExitStack() as stack:
        for i in range(num_ports):
            sock = socket.socket()
            stack.enter_context(sock)

            sock.bind(('', 0))
            ports.append(sock.getsockname()[1])

    if num_ports == 1:
        return ports[0]

    return ports


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
    def __init__(self, service_id, service_type, state, dependencies):
        self.service_id = service_id
        self.service_type = service_type

        if dependencies is None:
            dependencies = []

        self.dependencies = dependencies
        self.depended_on_by = []

        self.state_stream = DataStream.create('state', service_id, 'int8', [1], 20)
        self.state = state

        self.process_id = None

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
        if self.process_id is None:
            return None

        try:
            return psutil.Process(self.process_id)
        except psutil.NoSuchProcess:
            self.process_id = None
            return None

    def stop(self):
        if self.state != ServiceState.RUNNING:
            return

        try:
            client = Client(self.host, self.port)

            request = service_proto.ShutDownRequest()
            client.make_request('shut_down', request.SerializeToString())
        except Exception as e:
            raise RuntimeError("Something went wrong while stopping service.") from e

    def interrupt(self):
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

        self.logging_ingress_port = 0
        self.logging_egress_port = 0
        self.data_logging_ingress_port = 0
        self.data_logging_egress_port = 0
        self.tracing_ingress_port = 0
        self.tracing_egress_port = 0

        self.is_simulated = is_simulated
        self.config = config

        self.services = {}
        self.launched_processes = []

        self.log_distributor = None
        self.log_handler = None
        self.log_forwarder = None

        self.tracing_distributor = None

        self.log = logging.getLogger(__name__)

        self.service_paths = [os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'services'))]
        if 'service_paths' in self.config['testbed']:
            self.service_paths.extend(self.config['testbed']['service_paths'])

        self.startup_services = []
        if 'safety' in self.config['testbed']:
            self.startup_services.append(self.config['testbed']['safety']['service_id'])
        else:
            self.log.warning('No safety service specified in the configuration file. The testbed will not be checked for safety.')

        if 'startup_services' in self.config['testbed']:
            self.startup_services.extend(self.config['testbed']['startup_services'])

        # Add simulator to startup services, if we are in simulated mode.
        if self.is_simulated:
            self.startup_services.append('simulator')

        # Fill in services dictionary.
        for service_id, service_info in self.config['services'].items():
            service_type = service_info['service_type']

            if self.is_simulated and 'simulated_service_type' in service_info:
                service_type = service_info['simulated_service_type']

            dependencies = service_info.get('depends_on', [])

            self.services[service_id] = ServiceReference(service_id, service_type, ServiceState.CLOSED, dependencies)

        # Set up dependency management.
        for service_id, service in self.services.items():
            for dependency in service.dependencies:
                self.services[dependency].depended_on_by.append(service_id)

            if self.config['services'][service_id]['requires_safety']:
                if 'safety' in self.config['testbed']:
                    self.services[self.config['testbed']['safety']['service_id']].depended_on_by.append(service_id)
                else:
                    # Raise an exception if a service requires safety but no safety service is specified.
                    raise RuntimeError(f'Service "{service_id}" requires safety but no safety service is specified in the configuration file.')

        # Check for circular dependencies.
        services_to_shut_down = list(self.services.keys())
        while services_to_shut_down:
            shut_down_list = []

            for service_id in services_to_shut_down:
                for dependent in self.services[service_id].depended_on_by:
                    if dependent in services_to_shut_down:
                        # Dependent is still alive, so do not shut down this service.
                        break
                else:
                    # All services that depended on us are dead. We can shut down now too.
                    shut_down_list.append(service_id)

            if not shut_down_list:
                # No services were shut down this iteration.
                raise RuntimeError("Circular dependencies detected. Please fix the dependencies in your services.yml config.")

            for service_id in shut_down_list:
                services_to_shut_down.remove(service_id)

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
        self.shutdown_requested = threading.Event()
        self.shutdown_flag = threading.Event()

        self.heartbeat_stream = DataStream.create('heartbeat', 'testbed', 'uint64', [1], 20)

    def run(self):
        '''Run the main loop of the server.
        '''
        self.is_running = True
        self.shutdown_requested.clear()
        self.shutdown_flag.clear()

        heartbeat_thread = None
        monitor_services_thread = None

        try:
            self.context = zmq.Context()

            # Start the logging.
            self.start_log_distributor()
            self.setup_logging()

            # Start tracing distributor.
            self.start_tracing_distributor()

            heartbeat_thread = threading.Thread(target=self.do_heartbeats)
            heartbeat_thread.start()

            # Start the server
            self.server.start()

            # Start monitoring services.
            monitor_services_thread = threading.Thread(target=self.monitor_services)
            monitor_services_thread.start()

            # Start the startup services.
            for service_id in self.startup_services:
                try:
                    self.start_service(service_id)
                except Exception as e:
                    self.log.error(str(e))

            # For now, wait until Ctrl+C.
            # In the future, monitor services and update heartbeat stream.
            while not self.shutdown_requested.is_set():
                time.sleep(0.1)

        except KeyboardInterrupt:
            self.log.info('Interrupted by the user...')
        finally:
            self.shutdown_requested.set()

            try:
                self.log.info('Shutting down all running services.')
                self.shut_down_all_services()
            finally:
                self.shutdown_flag.set()

                if heartbeat_thread:
                    heartbeat_thread.join()

                if monitor_services_thread:
                    monitor_services_thread.join()

                # Submit zero heartbeat to signal a dead testbed.
                self.heartbeat_stream.submit_data(np.zeros(1, dtype='uint64'))

                # Shut down the server.
                self.server.stop()

                # Stop tracing distributor.
                self.stop_tracing_distributor()

                # Stop the logging.
                self.destroy_logging()
                self.stop_log_distributor()

                self.context = None

    def do_heartbeats(self):
        while not self.shutdown_flag.is_set():
            time.sleep(0.1)

            heartbeat = np.array([get_timestamp()], dtype='uint64')
            self.heartbeat_stream.submit_data(heartbeat)

    def monitor_services(self):
        while not self.shutdown_flag.is_set():
            time.sleep(0.1)

            # Avoid zombie processes. Communicate with processes after they exit.
            for process in self.launched_processes:
                if process.poll() is not None:
                    process.communicate()

                    self.launched_processes.remove(process)

            for service_id, service in self.services.items():
                if service.state not in [ServiceState.CLOSED, ServiceState.CRASHED, ServiceState.FAIL_SAFE]:
                    if service.process is None:
                        # The process is not running anymore, but its state indicates it's alive:
                        # it has crashed.
                        self.log.error(f'Service "{service.service_id}" appears to have crashed.')
                        service.state = ServiceState.CRASHED

                if service.state == ServiceState.RUNNING:
                    heartbeat_time = service.heartbeat.get()[0]
                    time_stamp = get_timestamp()

                    if time_stamp - heartbeat_time > SERVICE_LIVELINESS * 1e9:
                        # Service didn't submit a heartbeat in a while but its process is still alive:
                        # it is unresponsive.
                        self.log.warning(f'Service "{service.service_id}" appears to be unresponsive.')
                        service.state = ServiceState.UNRESPONSIVE

                if service.state == ServiceState.UNRESPONSIVE:
                    heartbeat_time = service.heartbeat.get()[0]
                    time_stamp = get_timestamp()

                    if time_stamp - heartbeat_time < SERVICE_LIVELINESS * 1e9:
                        # The service state indicates it's unresponsive, but it just submitted a
                        # heartbeat again: the service recovered.
                        self.log.info(f'Service "{service.service_id}" appears to have recovered from being unresponsive.')
                        service.state = ServiceState.RUNNING

    def setup_logging(self):
        '''Set up all logging.
        '''
        self.log_handler = CatkitLogHandler()
        logging.getLogger().addHandler(self.log_handler)
        logging.getLogger().setLevel(logging.DEBUG)

        self.log_forwarder = LogForwarder()
        self.log_forwarder.connect('testbed', f'tcp://localhost:{self.logging_ingress_port}')

    def destroy_logging(self):
        '''Shut down all logging.
        '''
        if self.log_handler:
            logging.getLogger().removeHandler(self.log_handler)
            self.log_handler = None

        if self.log_forwarder:
            del self.log_forwarder
            self.log_forwarder = None

    def start_log_distributor(self):
        '''Start the log distributor.
        '''
        self.logging_ingress_port, self.logging_egress_port = get_unused_port(num_ports=2)

        self.log_distributor = LogDistributor(self.context, self.logging_ingress_port, self.logging_egress_port)
        self.log_distributor.start()

    def stop_log_distributor(self):
        '''Stop the log distributor.
        '''
        if self.log_distributor:
            self.log_distributor.stop()
            self.log_distributor = None

    def start_tracing_distributor(self):
        '''Start the tracing distributor.
        '''
        self.tracing_distributor = LogDistributor(self.context, self.port + 3, self.port + 4)
        self.tracing_distributor.start()

    def stop_tracing_distributor(self):
        if self.tracing_distributor:
            self.tracing_distributor.stop()
            self.tracing_distributor = None

    def on_start_service(self, data):
        request = testbed_proto.StartServiceRequest()
        request.ParseFromString(data)

        service_id = request.service_id

        self.start_service(service_id)

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
        reply.logging_ingress_port = self.logging_ingress_port
        reply.logging_egress_port = self.logging_egress_port
        reply.data_logging_ingress_port = self.data_logging_ingress_port
        reply.data_logging_egress_port = self.data_logging_egress_port
        reply.tracing_ingress_port = self.tracing_ingress_port
        reply.tracing_egress_port = self.tracing_egress_port

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
            self.log.error(f'Service was started with the wrong service type: {service.service_type} was expected.')

            raise RuntimeError('Service registration has the wrong service type.')

        service.host = request.host
        service.port = request.port
        service.process_id = request.process_id
        service.heartbeat = DataStream.open(request.heartbeat_stream_id)

        reply = testbed_proto.RegisterServiceReply()

        reply.state_stream_id = service.state_stream.stream_id

        return reply.SerializeToString()

    def on_shut_down(self, data):
        self.shutdown_requested.set()

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
        if self.shutdown_requested.is_set():
            raise RuntimeError("The testbed is shutting down. Starting new services is not allowed anymore.")

        self.log.debug(f'Trying to start service "{service_id}".')

        if service_id not in self.services:
            raise RuntimeError(f'Service "{service_id}" is not a known service.')

        if self.services[service_id].state not in [ServiceState.CLOSED, ServiceState.CRASHED, ServiceState.FAIL_SAFE]:
            self.log.debug(f'Service "{service_id}" was already started.')
            return

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

        env = os.environ.copy()

        if 'env' in self.config['services'][service_id]:
            for key, value in self.config['services'][service_id]['env'].items():
                env[key] = str(value)

                self.log.debug(f'with environment variable {key} = {str(value)}.')

        # Start process.
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = subprocess.CREATE_NEW_CONSOLE

            process = subprocess.Popen(
                executable + args,
                startupinfo=startupinfo,
                creationflags=creationflags,
                cwd=dirname,
                env=env)
        else:
            process = subprocess.Popen(
                executable + args,
                stdin=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                start_new_session=True,
                cwd=dirname,
                env=env)

        # Store a reference to the service.
        self.services[service_id].state = ServiceState.INITIALIZING
        self.services[service_id].process_id = int(process.pid)
        self.services[service_id].port = port

        self.launched_processes.append(process)

        self.log.info(f'Started service "{service_id}" with type "{service_type}".')

        # Start the dependencies. This is not required but will speed things up.
        for dependency in self.services[service_id].dependencies:
            self.start_service(dependency)

    def stop_service(self, service_id):
        self.log.debug(f'Trying to stop service "{service_id}".')

        if service_id not in self.services:
            raise RuntimeError(f'Service "{service_id}" is not a known service.')

        self.services[service_id].stop()

    def interrupt_service(self, service_id):
        self.log.debug(f'Interrupting service "{service_id}".')

        if service_id not in self.services:
            raise RuntimeError(f'Service "{service_id}" is not a known service.')

        self.services[service_id].interrupt()

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
        # Keep track of current shutdown state of services.
        shutdown_state = {service_id: ('alive', 0) for service_id in self.services.keys()}

        while shutdown_state:
            try:
                shut_down_services = []

                for service_id, (state, t) in shutdown_state.items():
                    if self.services[service_id].process is None:
                        # Service has shut down. Remove it by appending to a remove list.
                        # This needs to be done as removing elements from a dict directly
                        # during iteration is not possible in Python.
                        shut_down_services.append(service_id)
                        continue

                    # Service is still alive. Check if all its dependents have shut down.
                    for dependent in self.services[service_id].depended_on_by:
                        if dependent in shutdown_state:
                            # At least one dependent is still alive, so we cannot shut this service down yet.
                            break
                    else:
                        # All dependents have been shut down. Try to shut this service down now.
                        shutdown_state[service_id] = self._shut_down_service_with_leniency(service_id, 60, state, t)

                # Remove stopped services from shutdown state.
                for service_id in shut_down_services:
                    del shutdown_state[service_id]

                # Wait a little bit.
                time.sleep(0.1)
            except KeyboardInterrupt:
                # Gather services that we are waiting for.
                waiting_for = []

                for service_id in shutdown_state.keys():
                    if self.services[service_id].process is None:
                        continue

                    for dependent in self.services[service_id].depended_on_by:
                        if dependent in shutdown_state:
                            # At least one dependent is still alive, so we cannot shut this service down yet.
                            break
                    else:
                        waiting_for.append(service_id)

                print('Press Ctrl+C again in the next five seconds to force shutdown of:')
                print(waiting_for)

                try:
                    time.sleep(5)
                except KeyboardInterrupt:
                    for service_id in waiting_for:
                        shutdown_state[service_id] = self._shut_down_service_with_leniency(service_id, 0, *shutdown_state[service_id])

    def _shut_down_service_with_leniency(self, service_id, leniency_period, state, t):
        if state == 'alive':
            # Send shutdown.
            self.services[service_id].stop()

            # Update shutdown state.
            return ('stopped', time.time())
        elif state == 'stopped':
            # Send interrupt if we have been waiting for long enough.
            if time.time() - t > leniency_period:
                self.log.warning(f'Service "{service_id}" is still alive. Interrupting...')
                self.services[service_id].interrupt()

                # Update shutdown state.
                return ('interrupted', time.time())
        elif state == 'interrupted':
            # Terminate if we have been waiting for long enough.
            if time.time() - t > leniency_period:
                self.log.error(f'Service "{service_id}" is still alive, even after interruption. Terminating...')
                self.services[service_id].terminate()

                # Update shutdown state.
                return ('terminated', time.time())

        # No changes have been made to the state.
        return (state, t)
