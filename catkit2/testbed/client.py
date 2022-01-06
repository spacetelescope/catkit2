import zmq
import json
import os
import argparse
import threading

from .protocol import *
from ..catkit_bindings import DataStream

from .service_proxy import ServiceProxy
from .proxies import *

class TestbedClient(object):
    '''A client for connecting to a testbed server.

    This object communicates with the testbed server to retrieve parameters,
    start services and return ServiceProxy objects for started services.

    Parameters
    ----------
    server_port : integer
        The port on which the server was started.
    '''
    def __init__(self, server_port):
        self.server_port = server_port

        self.context = zmq.Context()
        self.socket = None
        self._config = None

        self.lock = threading.Lock()

        self.reconnect()

    def reconnect(self):
        '''Reconnect to the server by recreating all sockets.
        '''
        if self.socket is not None:
            self.socket.close()

        self.socket = self.context.socket(zmq.REQ)
        self.socket.LINGER = 1
        self.socket.RCVTIMEO = 5000

        self.socket.connect(f'tcp://localhost:{self.server_port}')

    def _make_request(self, request_type, data=None, service_name=None):
        '''Make a general request to the testbed server.

        Parameters
        ----------
        request_type : string
            The type of request.
        data : dictionary or None
            The data for this request. Default: None.
        service_name : string or None
            The service this request should be forwarded to.
            Default: None (request is meant for the server itself).

        Returns
        -------
        dictionary
            The data of the reply from the server.

        Raises
        ------
        RuntimeError
            If the server didn't respond in time.
            If the reply was malformed in some way.
            If an error occurred on the server or the service during the handling
            of the request.
        '''
        request = {
            'request_type': request_type,
            'data': data
        }

        request = json.dumps(request).encode('ascii')

        if service_name is None:
            service_name = 'server'

        request = [CLIENT_ID, service_name.encode('ascii'), REQUEST_ID] + [request]

        with self.lock:
            try:
                self.socket.send_multipart(request)
                msg = self.socket.recv_multipart()
            except zmq.ZMQError as e:
                if e.errno == zmq.EAGAIN:
                    self.reconnect()
                    raise RuntimeError('Server did not respond.')
                else:
                    raise

        message_type, reply = msg

        if message_type != REPLY_ID:
            raise RuntimeError(f'Reply has an unexpected ID: "{message_type.decode("ascii")}".')

        try:
            reply = json.loads(reply.decode('ascii'))
        except json.JSONDecodeError as e:
            raise RuntimeError(f'JSON of reply malformed: "{e.msg}".')

        # Extract reply information.
        status = reply['status']
        description = reply['description']
        reply_type = reply['reply_type']
        reply_data = reply['data']

        assert reply_type == request_type

        if status != 'ok':
            raise RuntimeError(description)

        return reply_data

    def get_service_proxy(self, service_name):
        '''Get a ServiceProxy object for the service `service_name`.

        If the service was not yet running, it will be launched on the server.

        Parameters
        ----------
        service_name : string
            The identifier for the service for which to return the ServiceProxy.

        Returns
        -------
        ServiceProxy or derived class object.
            A ServiceProxy for the named service.

        Raises
        ------
        AttributeError
            If the named service could not be found by the server.
        '''
        # Require this service to be started on the server.
        body = {'service_name': service_name}

        try:
            service_info = self._make_request('require_service', body)
            service_type = service_info['service_type']
        except Exception as e:
            raise AttributeError(f'Service "{service_name}" could not be started: {str(e)}.') from e

        # Get the service interface class.
        interface_name = self.config['services'][service_name].get('interface')
        service_proxy_class = ServiceProxy.get_service_interface(interface_name)

        return service_proxy_class(service_name, service_type, self)

    def __getattr__(self, item):
        '''Get the ServiceProxy named after the attribute.

        This acts as a shortcut for :func:`~catkit2.testbed.TestbedClient.get_service_proxy`.

        Parameters
        ----------
        item : string
            The identifier for the service for which to return the ServiceProxy.

        Returns
        -------
        ServiceProxy or derived class object.
            A ServiceProxy for the named service.
        '''
        try:
            return self.get_service_proxy(item)
        except Exception as e:
            raise AttributeError(str(e))

    @property
    def running_services(self):
        '''The services that are currently running on the server.

        Dictionary. Keys are the service names, values are a dictionary themselves,
        indicating if they are connected, opened, and their service type.
        '''
        return self._make_request('running_services')

    @property
    def is_simulated(self):
        '''Whether the server is running in simulated mode.
        '''
        return self._make_request('is_simulated')

    @property
    def output_path(self):
        '''The current output path for experiment data output.
        '''
        return self._make_request('output_path')

    @property
    def config(self):
        '''The full configuration of the testbed server.

        .. note::
            Changing this dictionary has no effect on the configuration on the server.
            The configuration on the server is immutable.
        '''
        if self._config is None:
            self._config = self._make_request('configuration')

        return self._config

    def start_new_experiment(self, experiment_name, metadata=None):
        '''Start a new experiment on the server.

        Parameters
        ----------
        experiment_name : string
            A name indicating the type of experiment to start.
        metadata : dictionary or None
            Any metadata to store with the experiment data. Typically, these
            are the experiment parameters and any other identifying information used
            for post-processing of experiment runs. Default: None (no metadata).

        Returns
        -------
        string
            The new output path for experiment data output.
        '''
        if metadata is None:
            metadata = {}

        data = {
            'experiment_name': experiment_name,
            'metadata': metadata
        }

        return self._make_request('start_new_experiment', data=data)
