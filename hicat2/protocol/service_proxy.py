import zmq
import json
import os
import argparse

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
        super().__setattr__('_datastream_ids', None)

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
    def datastream_ids(self):
        if self._datastream_ids is None:
            # Request data stream names.
            self._datastream_ids = self.testbed_proxy._make_request('all_datastreams', service_name=self.service_name)['value']

        return self._datastream_ids

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
        elif name in self.datastream_ids:
            # Return datastream
            stream = DataStream.open(self.datastream_ids[name])

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
