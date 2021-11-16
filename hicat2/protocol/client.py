import zmq
import json
import os
import argparse
import threading

from .constants import *
from ..bindings import DataStream

from ..interfaces import *

class TestbedClient(object):
    def __init__(self, server_port):
        self.server_port = server_port

        self.context = zmq.Context()
        self.socket = None
        self._config = None

        self.lock = threading.Lock()

        self.reconnect()

    def reconnect(self):
        if self.socket is not None:
            self.socket.close()

        self.socket = self.context.socket(zmq.REQ)
        self.socket.LINGER = 1
        self.socket.RCVTIMEO = 5000

        self.socket.connect(f'tcp://localhost:{self.server_port}')

    def _make_request(self, request_type, data=None, service_name=None):
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

    def get_service_proxy(self, name):
        # Require this service to be started on the server.
        body = {'service_name': name}

        try:
            service_info = self._make_request('require_service', body)
            service_type = service_info['service_type']
        except Exception as e:
            raise AttributeError(f'Service "{name}" could not be started: {str(e)}.') from e

        # Get the service interface class.
        interface_name = self.config['services'][name].get('interface')
        service_proxy_class = _service_interfaces[interface_name]

        return service_proxy_class(name, service_type, self)

    def __getattr__(self, item):
        try:
            return self.get_service_proxy(item)
        except Exception as e:
            raise AttributeError(str(e))

    @property
    def running_services(self):
        return self._make_request('running_services')

    @property
    def is_simulated(self):
        return self._make_request('is_simulated')

    @property
    def config(self):
        if self._config is None:
            self._config = self._make_request('configuration')

        return self._config
