import zmq
import json
import os
import argparse
from threading import Lock

from .constants import *
from ..bindings import DataStream

class ServiceProxy:
    def __init__(self, service_name, service_type, testbed_proxy):
        # Avoid calling __setattr__ on this class during construction,
        # to defer communication with the service itself.
        super().__setattr__('service_name', service_name)
        super().__setattr__('service_type', service_type)
        super().__setattr__('testbed_proxy', testbed_proxy)

        super().__setattr__('_property_names', None)
        super().__setattr__('_command_names', None)
        super().__setattr__('_datastream_names', None)

    @property
    def property_names(self):
        if self._property_names is None:
            # Request property names.
            self._property_names = self.testbed_proxy._make_request('all_properties', service_name=self.service_name)['value']

        return self._property_names

    @property
    def command_names(self):
        if self._command_names is None:
            # Request command names.
            self._command_names = self.testbed_proxy._make_request('all_commands', service_name=self.service_name)['value']

        return self._command_names

    @property
    def datastream_names(self):
        if self._datastream_names is None:
            # Request data stream names.
            self._datastream_names = self.testbed_proxy._make_request('all_datastreams', service_name=self.service_name)['value']

        return self._datastream_names

    def __getattr__(self, name):
        if name in self.property_names:
            # Get property.
            message_data = {'property_name': name}
            data = self.testbed_proxy._make_request('get_property', message_data, service_name=self.service_name)

            return data['value']
        elif name in self.command_names:
            # Return function
            def command(*kwargs):
                message_data = {'command_name': self.name, 'args': kwargs}
                data = self.testbed_proxy._make_request('execute_command', message_data, service_name=self.service_name)

                return data['result']

            # Save command in the instance so it doesn't need to be created every time.
            setattr(self, name, command)

            return command
        elif name in self.datastream_names:
            # Return datastream
            stream = DataStream.open(name, self.service_name)

            setattr(self, name, stream)

            return stream
        else:
            return super().__getattr__(name)

    def __setattr__(self, name, value):
        if name in self.property_names:
            # Set property.
            message_data = {'property_name': name, 'value': value}
            data = self.testbed_proxy._make_request('set_property', message_data, service_name=self.service_name)
        else:
            super().__setattr__(name, value)

_service_interfaces = {None: ServiceProxy}

def register_service_interface(interface_name):
    def decorator(cls):
        _service_interfaces[interface_name] = cls

        return cls

    return decorator

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

    def make_request(self, request_type, body=None, service_name=None):
        request = {'request_type': request_type, 'body': body}
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

        try:
            reply = json.loads(reply.decode('ascii'))
        except json.JSONDecodeError as e:
            raise RuntimeError(f'JSON of reply malformed: "{e.msg}".')

        if message_type == ERROR_ID:
            raise RuntimeError(reply['error_message'])
        elif message != REPLY_ID:
            raise RuntimeError(f'Reply did have an unexpected ID: "{message_type.decode("ascii")}".')

        return reply

    def get_service_proxy(self, name):
        # Require this service to be started on the server.
        body = {'service_name': name}
        try:
            service_info = self.make_request('require_service', body)
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
        return self.make_request('running_services')['services']

    @property
    def is_simulated(self):
        return self.make_request('is_simulated')['is_simulated']

    @property
    def config(self):
        if self._config is None:
            self._config = self.make_request('configuration')['configuration']

        return self._config
