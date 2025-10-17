import sys
import json
import os
import time
import subprocess
import socket
import threading
import contextlib
import importlib
import fasteners

import psutil
import zmq
import numpy as np
import logging

from ..catkit_bindings import LogForwarder, Server, ServiceState, DataStream, SharedMemory, LocalMessageBroker, get_timestamp, is_alive_state, Client, get_host_name
from .logging import *
from .distributor import ZmqDistributor
from .message_forwarder import MessageBrokerForwarder, MessageBrokerReceiver

from ..proto import testbed_pb2 as testbed_proto
from ..proto import service_pb2 as service_proto

try:
    import importlib.metadata as importlib_metadata
except ImportError:
    import importlib_metadata


SERVICE_LIVELINESS = 5


if sys.platform == 'win32':
    NICE_VALUES = {
        'idle': psutil.IDLE_PRIORITY_CLASS,
        'below_normal': psutil.BELOW_NORMAL_PRIORITY_CLASS,
        'normal': psutil.NORMAL_PRIORITY_CLASS,
        'above_normal': psutil.ABOVE_NORMAL_PRIORITY_CLASS,
        'high': psutil.HIGH_PRIORITY_CLASS
    }
else:
    NICE_VALUES = {
        'idle': 20,
        'below_normal': 10,
        'normal': 0,
        'above_normal': -10,
        'high': -20
    }


def get_unused_port(num_ports=1):
    '''Get port numbers that are unused.

    Parameters
    ----------
    num_ports : int, optional
        The number of port numbers to return. By default 1.

    Returns
    -------
    int or list of ints
        The port numbers. If only a single port was requested, an
        integer will be returned. Otherwise a list of integers.
    '''
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


def create_shared_memory(name, size):
    '''Create an empty shared memory object, even if it already existed.

    Parameters
    ----------
    name : str
        The name of the shared memory object.
    size : int
        The size in bytes of the shared memory object.
    '''
    try:
        return SharedMemory.create(name, size)
    except RuntimeError:
        # Try to open and destroy and try again.
        shm = SharedMemory.open(name)
        shm.destroy()

        return SharedMemory.create(name, size)


def _parse_broker_endpoint(endpoint):
    """Parse broker endpoint strings and return (host, port, raw_endpoint).

    Supports:
      - tcp://host:port
      - host:port
      - IPv6 in brackets: [::1]:5555
      - wildcard host: '*' or '*:5555' (host -> None meaning any)
    Attempts DNS resolution for hostnames and returns the first
    resolved address.

    Returns (host_or_none, port_or_none, original_endpoint)
    """
    if not endpoint:
        return (None, None, endpoint)

    ep = endpoint.strip()

    # Remove scheme if present
    if '://' in ep:
        ep = ep.split('://', 1)[1]

    # IPv6 with brackets
    host = None
    port = None
    if ep.startswith('['):
        # [addr]:port
        if ']:' in ep:
            host_part, port_part = ep.split(']:', 1)
            host = host_part[1:]
            port = port_part
        else:
            host = ep[1:-1]
            port = None
    else:
        # split on last ':' to allow IPv6 fallback if user omitted brackets
        if ':' in ep and ep.count(':') == 1:
            host_part, port_part = ep.rsplit(':', 1)
            host = host_part
            port = port_part
        else:
            # no port or ambiguous IPv6, treat entire ep as host
            host = ep
            port = None

    # Wildcard handling
    if host == '*' or host == '' or host is None:
        host_resolved = None
    else:
        # Try to resolve DNS; prefer IPv4 address strings for simplicity
        try:
            import socket as _socket

            infos = _socket.getaddrinfo(
                host, None, family=_socket.AF_UNSPEC, type=_socket.SOCK_STREAM)
            # pick first address family result
            if infos:
                addr = infos[0][4][0]
                host_resolved = addr
            else:
                host_resolved = host
        except Exception:
            host_resolved = host

    # Normalize port
    try:
        port_num = int(port) if port is not None and str(port) != '' else None
    except Exception:
        port_num = None

    return (host_resolved, port_num, endpoint)


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
    def __init__(self, service_id, service_type, state, dependencies, broker):
        self.service_id = service_id
        self.service_type = service_type
        self.broker = broker

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

        self.broker.publish_array(f'{self.service_id}/service_state/get', new_state)

    @property
    def is_alive(self):
        return is_alive_state(self.state)

    @property
    def process(self):
        if self.process_id is None or self.process_id == -1:
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

        # Cross-platform interrupt handling.
        # On POSIX (Linux/macOS) send SIGINT to the process group so the
        # target process receives a KeyboardInterrupt-equivalent.
        # On Windows keep the existing approach that generates a console
        # ctrl event via the ctypes API.
        if not self.is_alive:
            return

        try:
            if os.name == 'posix':
                import signal

                try:
                    # Send SIGINT to the process group of the child so all
                    # subprocesses in the group receive the interrupt.
                    pgid = os.getpgid(self.process.pid)
                    if pgid == os.getpgrp():
                        # Child is in the same group as us; avoid interrupting self.
                        os.kill(self.process.pid, signal.SIGINT)
                    else:
                        os.killpg(pgid, signal.SIGINT)
                except AttributeError:
                    # Fallback: no process group support, send SIGINT to pid.
                    os.kill(self.process.pid, signal.SIGINT)
            elif os.name == 'nt':
                # Windows: generate console ctrl event via ctypes.
                ctrl_c_code = ';'.join([
                    'import ctypes',
                    'kernel = ctypes.windll.kernel32',
                    'kernel.FreeConsole()',
                    'kernel.AttachConsole({pid})',
                    'kernel.SetConsoleCtrlHandler(None, 1)',
                    'kernel.GenerateConsoleCtrlEvent(0, 0)'
                ])

                ctrl_cmd = ctrl_c_code.format(pid=self.process.pid)
                psutil.Popen([sys.executable, '-c', ctrl_cmd])
            else:
                # Unknown OS: attempt POSIX-style SIGINT as a best-effort.
                import signal
                os.kill(self.process.pid, signal.SIGINT)
        except (OSError, psutil.NoSuchProcess, PermissionError):
            # If anything goes wrong, fall back to terminating the process
            # to avoid leaving it stuck. The caller can choose to escalate.
            try:
                if self.process:
                    self.process.terminate()
            except (OSError, psutil.NoSuchProcess, PermissionError) as term_exc:
                # Use self.log with lazy formatting to avoid long lines
                try:
                    pid = self.process.pid if self.process else 'unknown'
                    self.log.warning(
                        "Failed to terminate process %s: %s", pid, term_exc
                    )
                except Exception:
                    # Fallback if logging isn't set up
                    pid = self.process.pid if self.process else 'unknown'
                    print(
                        "Warning: Failed to terminate process %s: %s"
                        % (pid, term_exc),
                        file=sys.stderr,
                    )

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

        # Set a lock file so that no more than one testbed object exists for a specific port.
        if os.name == 'nt':
            lock_path = os.path.join(os.getenv('TEMP'), f'catkit2_{port}.lock')
        else:
            lock_path = f'/tmp/catkit2_{port}.lock'

        self.lock = fasteners.InterProcessLock(lock_path)
        if not self.lock.acquire(blocking=False):
            raise RuntimeError(f'Another testbed object is already running on port {port}.')

        self.host_name = get_host_name()

        self.logging_ingress_port = 0
        self.logging_egress_port = 0
        self.data_logging_ingress_port = 0
        self.data_logging_egress_port = 0
        self.tracing_ingress_port = 0
        self.tracing_egress_port = 0

        self.is_simulated = is_simulated
        self.config = config

        # Map of named remote testbeds from configuration (name -> {'endpoint','host','port'})
        self.remote_testbeds = {}
        remote_brokers_config = self.config.get('testbed', {}).get('remote_message_brokers', {})
        if remote_brokers_config.get('enabled'):
            for conn in remote_brokers_config.get('connections', []):
                name = conn.get('name')
                endpoint = conn.get('endpoint')
                if not name or not endpoint:
                    continue

                host, port, raw = _parse_broker_endpoint(endpoint)

                self.remote_testbeds[name] = {
                    'endpoint': endpoint,
                    'host': host,
                    'port': port
                }

        self.services = {}
        self.launched_processes = []

        self.log_distributor = None
        self.log_handler = None
        self.log_forwarder = None

        self.tracing_distributor = None
        
        self.message_forwarder = None
        self.message_receiver = None

        self.log = logging.getLogger(__name__)

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

        # Create a message broker.
        self.message_broker_buffer = create_shared_memory(f'catkit_broker_{port}.buf', 1024 * 1024 * 1024 * 2)

        required_header_bytes = LocalMessageBroker.calculate_required_header_size([self.message_broker_buffer])
        # Align to 1 MiB to avoid excessive reallocations when configuration changes slightly.
        alignment = 1024 * 1024
        required_header_bytes = ((required_header_bytes + alignment - 1) // alignment) * alignment

        self.message_broker_header = create_shared_memory(f'catkit_broker_{port}.hdr', required_header_bytes)

        self.message_broker = LocalMessageBroker.create(self.message_broker_header, [self.message_broker_buffer])

        # Fill in services dictionary.
        for service_id, service_info in self.config['services'].items():
            service_type = service_info['service_type']

            if self.is_simulated and 'simulated_service_type' in service_info:
                service_type = service_info['simulated_service_type']

            dependencies = service_info.get('depends_on', [])

            self.services[service_id] = ServiceReference(service_id, service_type, ServiceState.CLOSED, dependencies, self.message_broker)

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

        # Read in service types.
        self.service_type_paths = {}
        for entry_point in importlib_metadata.entry_points().get("catkit2.services", []):
            try:
                # grab the module
                module = entry_point.module

            except AttributeError:
                # In some configurations of EntryPoint there is no 'module'
                module = entry_point.value.split(':')[0]

            try:
                spec = importlib.util.find_spec(module)
                if spec is not None:
                    path = os.path.abspath(spec.origin)
                    self.register_service_type(entry_point.name, path)
                else:
                    self.log.warning(
                        f"Could not find spec for module: {module}")
            except (ModuleNotFoundError, ImportError) as e:
                self.log.warning(f"Could not import module {module}: {e}")

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
            
            # Start message broker forwarding/receiving
            self.start_message_forwarding()  # For remote testbeds
            self.start_message_receiving()    # For main testbed

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

                # Stop message forwarding/receiving.
                self.stop_message_forwarding()
                self.stop_message_receiving()

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

            self.message_broker.publish_array('testbed/heartbeat/get', heartbeat)

    def monitor_services(self):
        while not self.shutdown_flag.is_set():
            time.sleep(0.1)

            # Avoid zombie processes. Communicate with processes after they exit.
            for process in self.launched_processes:
                if process.poll() is not None:
                    process.communicate()

                    self.launched_processes.remove(process)

            for service_id, service in self.services.items():
                # For remote services (process_id == -1), skip all local monitoring
                is_remote = (service.process_id == -1)
                
                # Skip crash detection for remote services
                if service.state not in [ServiceState.CLOSED, ServiceState.CRASHED, ServiceState.FAIL_SAFE]:
                    if service.process is None and not is_remote:
                        # The process is not running anymore, but its state indicates it's alive:
                        # it has crashed.
                        self.log.error(f'Service "{service.service_id}" appears to have crashed.')
                        service.state = ServiceState.CRASHED

                # Skip heartbeat monitoring for remote services (no local heartbeat stream)
                if is_remote or service.heartbeat is None:
                    continue

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
        def callback(log_message):
            log_message = log_message[0].decode('utf-8')
            log_message = json.loads(log_message)

            print(f'[{log_message["service_id"]}] {log_message["message"]}')

        self.logging_ingress_port, self.logging_egress_port = get_unused_port(num_ports=2)

        self.log_distributor = ZmqDistributor(self.context, self.logging_ingress_port, self.logging_egress_port, callback)
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
        self.tracing_ingress_port, self.tracing_egress_port = get_unused_port(num_ports=2)

        self.tracing_distributor = ZmqDistributor(self.context, self.tracing_ingress_port, self.tracing_egress_port)
        self.tracing_distributor.start()

    def stop_tracing_distributor(self):
        if self.tracing_distributor:
            self.tracing_distributor.stop()
            self.tracing_distributor = None

    def start_message_forwarding(self):
        '''Start message broker forwarding for remote services.
        
        This should be called on remote testbeds to forward their local
        message broker messages to the main testbed.
        '''
        # Determine if we should forward messages (if we have topic prefixes)
        remote_brokers_config = self.config.get('testbed', {}).get('remote_message_brokers', {})
        
        if not remote_brokers_config.get('enabled'):
            return
        
        # For remote testbeds, we want to publish our messages for main testbed to subscribe
        # Check if we're a remote testbed by looking for forwarder config
        forwarder_config = remote_brokers_config.get('forwarder', {})
        
        if not forwarder_config.get('enabled'):
            return
        
        # Get list of exact topics to forward
        # For now, hardcode known topics (could be configured per service type)
        topics_to_forward = []
        for service_id in self.services.keys():
            # Add known topics for camera services
            if 'camera' in service_id.lower():
                topics_to_forward.append(f'{service_id}/images')
        
        if not topics_to_forward:
            self.log.warning('No topics to forward, message forwarding disabled')
            return
        
        # Start forwarder
        publish_port = forwarder_config.get('publish_port', 5555)
        self.message_forwarder = MessageBrokerForwarder(
            self.context,
            self.message_broker,
            publish_port,
            topics_to_forward
        )
        self.message_forwarder.start()
        self.log.info(f'Started message broker forwarder on port {publish_port}')
    
    def stop_message_forwarding(self):
        '''Stop message broker forwarding.'''
        if self.message_forwarder:
            self.message_forwarder.stop()
            self.message_forwarder = None
    
    def start_message_receiving(self):
        '''Start receiving forwarded messages from remote testbeds.
        
        This should be called on the main testbed to receive messages
        from remote testbeds.
        '''
        remote_brokers_config = self.config.get('testbed', {}).get('remote_message_brokers', {})
        
        if not remote_brokers_config.get('enabled'):
            return
        
        # Build list of remote endpoints to subscribe to
        remote_endpoints = []
        for conn in remote_brokers_config.get('connections', []):
            # Extract host from endpoint
            endpoint = conn.get('endpoint', '')
            if not endpoint:
                continue
            
            # Parse endpoint to get host
            # Format: "tcp://145.238.1.51:1234"
            host = endpoint.split('://')[1].split(':')[0] if '://' in endpoint else endpoint.split(':')[0]
            
            # Use forwarder port (default 5555)
            forwarder_port = conn.get('forwarder_port', 5555)
            remote_endpoint = f'tcp://{host}:{forwarder_port}'
            remote_endpoints.append(remote_endpoint)
            self.log.info(f'Will subscribe to messages from {remote_endpoint}')
        
        if not remote_endpoints:
            return
        
        # Start receiver
        self.message_receiver = MessageBrokerReceiver(
            self.context,
            self.message_broker,
            remote_endpoints
        )
        self.message_receiver.start()
        self.log.info(f'Started message broker receiver for {len(remote_endpoints)} remote testbeds')
    
    def stop_message_receiving(self):
        '''Stop receiving forwarded messages.'''
        if self.message_receiver:
            self.message_receiver.stop()
            self.message_receiver = None

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
        reply.message_broker_id = self.message_broker_header.filename

        return reply.SerializeToString()

    def on_get_service_info(self, data):
        request = testbed_proto.GetServiceInfoRequest()
        request.ParseFromString(data)

        service_id = request.service_id

        ref = self.services[service_id]

        # If this is a remote service, query the remote testbed
        if ref.process_id == -1:
            # For remote services, we need to query the remote testbed
            # to get the actual port where the service is listening
            try:
                config_service = self.config['services'][service_id]
                remote_server_name = config_service.get('remote_server')
                
                if remote_server_name:
                    remote_info = self.remote_testbeds.get(
                        remote_server_name
                    )
                    
                    if remote_info:
                        remote_host = remote_info.get('host')
                        remote_port = remote_info.get('port')
                        
                        if remote_host and remote_port:
                            # Create a client to query the remote testbed
                            remote_client = Client(
                                remote_host, remote_port
                            )
                            remote_service_info = (
                                remote_client.make_request(
                                    'get_service_info',
                                    testbed_proto.GetServiceInfoRequest(
                                        service_id=service_id
                                    ).SerializeToString()
                                )
                            )
                            
                            if remote_service_info:
                                return remote_service_info
                            
            except Exception as e:
                self.log.warning(
                    f'Failed to get service info from '
                    f'remote testbed: {e}'
                )
            
            # Fallback: return minimal info with placeholder values
            reply = testbed_proto.GetServiceInfoReply()
            service_ref = reply.service
            service_ref.id = service_id
            service_ref.type = ref.service_type
            service_ref.state_stream_id = f'remote_{service_id}_state'
            service_ref.host = '127.0.0.1'
            service_ref.port = 0
            return reply.SerializeToString()

        # Local service - return local info
        reply = testbed_proto.GetServiceInfoReply()

        service_ref = reply.service
        service_ref.id = service_id
        service_ref.type = ref.service_type
        service_ref.state_stream_id = ref.state_stream.stream_id
        # Always use hostname (or configured host if available) for connectivity,
        # not 127.0.0.1, since 127.0.0.1 only works locally
        service_ref.host = self.host_name
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

    def register_service_type(self, service_type, path):
        '''Register a service type.

        Parameters
        ----------
        service_type : str
            The service type.
        path : str
            The path to the Python file to run for this service.
        '''
        self.service_type_paths[service_type] = path

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

        # If this service is configured to run on a named remote testbed, forward
        # the start request to that testbed instead of launching locally.
        svc_cfg = self.config['services'].get(service_id, {})
        remote_name = svc_cfg.get('remote_server')
        if remote_name:
            # Lookup remote testbed configuration
            remote_info = self.remote_testbeds.get(remote_name)
            if not remote_info:
                raise RuntimeError(f'Remote testbed "{remote_name}" not configured.')

            # Create a proxy and ask it to start the service there.
            from .testbed_proxy import TestbedProxy  # local python wrapper around bindings

            # Use host/port if known, otherwise fall back to endpoint parsing
            host = remote_info.get('host') or '127.0.0.1'
            port = remote_info.get('port') or self.port

            proxy = TestbedProxy(host, port)
            try:
                proxy.start_service(service_id)
            except Exception as e:
                # Include the proxy error message to provide a useful reply
                # back to the original requester (salvaged reply will contain this).
                self.log.error(f'Failed to forward start_service to remote testbed {remote_name}: {e}')
                raise RuntimeError(f'Unable to start service (remote testbed {remote_name}): {e}') from e

            # Mark as remote service and get service details from remote testbed
            # The remote testbed knows the actual service host/port after registration
            self.services[service_id].process_id = -1  # Mark as remote
            self.services[service_id].state = ServiceState.RUNNING

            # Query remote testbed for actual service details
            # Note: We can't access the service's state_stream or other shared memory
            # from here, so we just mark it as remote and let ServiceProxy handle it
            self.services[service_id].host = None  # Will be filled by remote registration
            self.services[service_id].port = None  # Will be filled by remote registration

            self.log.info(
                f'Forwarded start of service "{service_id}" to remote '
                f'testbed "{remote_name}" ({host}:{port}).')

            return

        # Otherwise start service locally as before.
        # Resolve service type;
        path = self.resolve_service_type(service_type)
        dirname = os.path.dirname(path)

        # Build Python executable command.
        executable = [sys.executable, path]

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

        # Set CPU affinity
        if 'cpu_affinity' in self.config['testbed']:
            affinity_config = self.config['testbed']['cpu_affinity']

            # Only use affinity if there is an entry for our host name.
            if self.host_name in affinity_config:
                default_affinity = affinity_config[self.host_name].get('default')

                affinity = affinity_config[self.host_name].get(service_id, default_affinity)

                # Only set affinity if there was one for this service or if there was a default.
                if affinity:
                    self.services[service_id].process.cpu_affinity(affinity)

                    self.log.debug(f'with CPU affinity to {affinity}.')

        # Set process priority
        if 'process_priority' in self.config['testbed']:
            priority_config = self.config['testbed']['process_priority']

            # Only use priority if there is an entry for our host name.
            if self.host_name in priority_config:
                default_priority = priority_config[self.host_name].get('default', None)

                priority = priority_config[self.host_name].get(service_id, default_priority)

                # Only set priority if there was one for this service or if there was a default.
                if priority:
                    self.services[service_id].process.nice(NICE_VALUES[priority])

                    self.log.debug(f'with priority {priority}.')

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
            The path to the Python script of the service.
        '''
        if service_type not in self.service_type_paths:
            raise ValueError(f"Service type '{service_type}' not recognized.")

        return self.service_type_paths[service_type]

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
