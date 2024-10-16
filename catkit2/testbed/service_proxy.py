from .. import catkit_bindings

import importlib.metadata

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

    def __init__(self, testbed, service_id):
        super().__init__(testbed, service_id)

        # Override the testbed attribute with the extended Python version.
        # The import is here instead of at the top of the file to avoid circular imports.
        from .testbed_proxy import TestbedProxy  # noqa: E402
        object.__setattr__(self, '_testbed', TestbedProxy(getattr(super(), 'testbed').host, getattr(super(), 'testbed').port))

    @property
    def testbed(self):
        return self._testbed

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

        If no interface is defined, return a default ServiceProxy class.

        Parameters
        ----------
        interface_name : string
            The name of the interface.

        Returns
        -------
        derived class of ServiceProxy or ServiceProxy
            The class belonging to the interface name.
        '''
        entry_point = importlib.metadata.entry_points(group='catkit2.proxies', name=interface_name)

        if not entry_point:
            raise AttributeError(f"Service proxy class with interface name '{interface_name}' not found. Did you set it as an entry point?")

        return entry_point.load()
