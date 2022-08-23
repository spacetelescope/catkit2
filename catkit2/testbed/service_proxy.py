import zmq
import json
import os
import argparse

from .protocol import *
from ..catkit_bindings import DataStream
from .. import catkit_bindings

class ServiceProxy(catkit_bindings.ServiceProxy):
    '''A proxy for a service connected to a server.

    Parameters
    ----------
    testbed : TestbedProxy
        A reference to the testbed. The service needs to be running on this testbed.
    service_id : string
        The id of the service.
    '''
    _service_interfaces = {}

    def __getattr__(self, name):
        '''Get a property, command or data stream.

        Properties
        ----------
        name : string
            The name of the attribute.

        Returns
        -------
        Property or Command or DataStream object
            The attribute.

        Raises
        ------
        AttributeError
            If the named attribute is not a property, command or data stream.
        '''
        if name in self.property_names:
            # Return property.
            return self.get_property(name)
        elif name in self.command_names:
            # Execute command.
            def cmd(**kwargs):
                return self.execute_command(name, kwargs)
            return cmd
        elif name in self.data_stream_names:
            # Return datastream.
            return self.get_data_stream(name)
        else:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'.")

    def __setattr__(self, name, value):
        '''Set the property.

        Parameters
        ----------
        name : string
            The name of the attribute.
        value : Python object
            What to set the property to.

        Raises
        ------
        AttributeError
            If the attribute is a command or datastream (both of which are not settable).
            If the attribute cannot be found on this service.
        '''
        if name in self.property_names:
            # Set property.
            self.set_property(name, value)
        elif name in self.command_names:
            raise AttributeError('Cannot set a command.')
        elif name in self.data_stream_names:
            raise AttributeError('Cannot set a data stream. Did you mean .submit_data()?')
        else:
            super().__setattr__(name, value)

    @classmethod
    def get_service_interface(cls, interface_name):
        '''Get the service proxy class belonging to an interface name.

        If the interface is not registered, return a default ServiceProxy class instead.

        Parameters
        ----------
        interface_name : string
            The name of the interface.

        Returns
        -------
        derived class of ServiceProxy or ServiceProxy
            The class belonging to the interface name.
        '''
        if interface_name in cls._service_interfaces:
            return cls._service_interfaces[interface_name]
        else:
            return cls

    @classmethod
    def register_service_interface(cls, interface_name):
        '''Register a ServiceProxy derived class.

        Parameters
        ----------
        interface_name : string
            The name of the interface.

        Returns
        -------
        class decorator
            For decorating your ServiceProxy derived class with.
        '''
        def decorator(interface_class):
            cls._service_interfaces[interface_name] = interface_class

            return interface_class

        return decorator
