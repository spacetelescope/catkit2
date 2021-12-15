import zmq
import json
import os
import argparse

from .constants import *
from ..catkit_bindings import DataStream

class ServiceProxy:
    _service_interfaces = {}

    def __init__(self, service_name, service_type, testbed_proxy):
        # Avoid calling __setattr__ on this class during construction,
        # to defer communication with the service itself.
        super().__setattr__('service_name', service_name)
        super().__setattr__('service_type', service_type)
        super().__setattr__('testbed_proxy', testbed_proxy)

        super().__setattr__('_property_names', None)
        super().__setattr__('_command_names', None)
        super().__setattr__('_datastream_ids', None)
        super().__setattr__('_configuration', None)

    @property
    def property_names(self):
        if self._property_names is None:
            # Request property names.
            names = self.testbed_proxy._make_request('all_properties', service_name=self.service_name)
            super().__setattr__('_property_names', names)

        return self._property_names

    @property
    def command_names(self):
        if self._command_names is None:
            # Request command names.
            self._command_names = self.testbed_proxy._make_request('all_commands', service_name=self.service_name)

        return self._command_names

    @property
    def datastream_ids(self):
        if self._datastream_ids is None:
            # Request data stream names.
            self._datastream_ids = self.testbed_proxy._make_request('all_datastreams', service_name=self.service_name)

        return self._datastream_ids

    @property
    def configuration(self):
        if self._configuration is None:
            # Request configuration.
            self._configuration = self.__getattr__(self, 'configuration')

        return self._configuration

    def __getattr__(self, name):
        if name in self.property_names:
            # Get property.
            message_data = {'property_name': name}
            val = self.testbed_proxy._make_request('get_property', message_data, service_name=self.service_name)

            return val
        elif name in self.command_names:
            # Return function
            def command(**kwargs):
                message_data = {'command_name': name, 'arguments': kwargs}
                res = self.testbed_proxy._make_request('execute_command', message_data, service_name=self.service_name)

                return res

            # Save command in the instance so it doesn't need to be created every time.
            super().__setattr__(name, command)

            return command
        elif name in self.datastream_ids:
            # Return datastream
            stream = DataStream.open(self.datastream_ids[name])

            super().__setattr__(name, stream)

            return stream
        else:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'.")

    def __setattr__(self, name, value):
        if name in ['_property_names', '_command_names', '_datastream_ids']:
            super().__setattr__(name, value)
        elif name in self.property_names:
            # Set property.
            message_data = {'property_name': name, 'value': value}
            self.testbed_proxy._make_request('set_property', message_data, service_name=self.service_name)
        elif name in self.command_names:
            raise AttributeError('Cannot set a command.')
        elif name in self.datastream_ids:
            raise AttributeError('Cannot set a data stream. Did you mean .submit_data()?')
        else:
            super().__setattr__(name, value)

    @classmethod
    def get_service_interface(cls, interface_name):
        if interface_name in cls._service_interfaces:
            return cls._service_interfaces[interface_name]
        else:
            return cls

    @classmethod
    def register_service_interface(cls, interface_name):
        def decorator(interface_class):
            cls._service_interfaces[interface_name] = interface_class

            return interface_class

        return decorator
