"""Proxy for services running on remote testbeds."""

from .. import catkit_bindings
from ..proto import testbed_pb2 as testbed_proto


class RemoteServiceProxy:
    """A proxy for a service running on a remote testbed.
    
    This proxy communicates with the service directly using RPC,
    obtaining the service's actual host:port from the remote testbed.
    """

    def __init__(self, testbed, service_id, remote_server_name,
                 remote_info):
        """Initialize the remote service proxy.
        
        Parameters
        ----------
        testbed : TestbedProxy
            The local testbed proxy (on narada)
        service_id : string
            The id of the remote service
        remote_server_name : string
            The name of the remote testbed (e.g., 'camera_server')
        remote_info : dict
            Config dict with 'endpoint' key, format: 'tcp://host:port'
        """
        self._testbed = testbed
        self._service_id = service_id
        self._remote_server_name = remote_server_name
        self._remote_info = remote_info
        self._command_names = []
        self._property_names = []
        self._data_stream_names = []
        self._service_host = None
        self._service_port = None
        self._service_type = None
        
        # Get info about the remote service
        self._initialize_remote_service()

    def _initialize_remote_service(self):
        """Initialize connection to remote service via RPC."""
        # Parse endpoint from remote_info
        if not self._remote_info:
            raise RuntimeError(
                f'Remote testbed "{self._remote_server_name}" '
                'configuration not provided'
            )
        
        endpoint = self._remote_info.get('endpoint')
        if not endpoint:
            raise RuntimeError(
                f'Remote testbed "{self._remote_server_name}" '
                'has no endpoint configured'
            )
        
        # Parse endpoint format: "tcp://host:port"
        # Simple parsing for tcp://host:port format
        if endpoint.startswith('tcp://'):
            endpoint_addr = endpoint[6:]  # Remove 'tcp://'
            if ':' in endpoint_addr:
                remote_host, remote_port_str = endpoint_addr.rsplit(':', 1)
                try:
                    remote_port = int(remote_port_str)
                except ValueError:
                    raise RuntimeError(
                        f'Invalid port in endpoint: {endpoint}'
                    )
            else:
                raise RuntimeError(
                    f'Invalid endpoint format: {endpoint}'
                )
        else:
            raise RuntimeError(
                f'Unsupported endpoint protocol: {endpoint}'
            )
        
        # Create a client to query the remote testbed for service info
        # This avoids creating a TestbedProxy which would try to open
        # shared memory on the remote machine
        try:
            client = catkit_bindings.Client(remote_host, remote_port)
            service_info_bytes = client.make_request(
                'get_service_info',
                testbed_proto.GetServiceInfoRequest(
                    service_id=self._service_id
                ).SerializeToString()
            )
            
            service_info_reply = (
                testbed_proto.GetServiceInfoReply()
            )
            service_info_reply.ParseFromString(service_info_bytes)
            
            service = service_info_reply.service
            self._service_host = service.host
            self._service_port = service.port
            self._service_type = service.type
            
            # Check if service is registered
            if not self._service_host or self._service_port == 0:
                raise RuntimeError(
                    f'Service "{self._service_id}" is not registered '
                    f'on remote testbed "{self._remote_server_name}". '
                    f'Did you call testbed.start_service() first?'
                )
            
        except Exception as e:
            raise RuntimeError(
                f'Failed to get service info from remote testbed: {e}'
            )
        
        # Now get the command and property names
        self._get_service_metadata()

    def _get_service_metadata(self):
        """Query the service to get command/property names."""
        if not self._service_host or not self._service_port:
            raise RuntimeError(
                'Service host/port not known - cannot get metadata'
            )
        
        try:
            client = catkit_bindings.Client(
                self._service_host, self._service_port
            )
            info_bytes = client.make_request('get_info', b'')
            
            from ..proto import service_pb2 as service_proto
            info_reply = service_proto.GetInfoReply()
            info_reply.ParseFromString(info_bytes)
            
            self._command_names = list(info_reply.command_names)
            # Note: properties are not accessible via RPC for remote services
            # Only commands can be executed remotely
            self._property_names = []
            self._data_stream_names = list(
                info_reply.datastream_ids.keys()
            )
            
        except Exception as e:
            raise RuntimeError(
                f'Failed to get service metadata: {e}'
            )

    @property
    def property_names(self):
        """Get property names."""
        return self._property_names

    @property
    def command_names(self):
        """Get command names."""
        return self._command_names

    @property
    def data_stream_names(self):
        """Get data stream names."""
        return self._data_stream_names

    def get_property(self, name):
        """Get a property value from the remote service.
        
        Note: Properties are not accessible for remote services via RPC.
        Only local services support property access.
        """
        raise NotImplementedError(
            f'Cannot access property "{name}" on remote service. '
            'Properties are only accessible for local services.'
        )

    def set_property(self, name, value):
        """Set a property on the remote service.
        
        Note: Properties are not accessible for remote services via RPC.
        Only local services support property access.
        """
        raise NotImplementedError(
            f'Cannot set property "{name}" on remote service. '
            'Properties are only accessible for local services.'
        )

    def execute_command(self, name, arguments):
        """Execute a command on the remote service."""
        from ..proto import service_pb2 as service_proto
        
        if not self._service_host or not self._service_port:
            raise RuntimeError(
                'Service host/port not known'
            )
        
        try:
            client = catkit_bindings.Client(
                self._service_host, self._service_port
            )
            request = service_proto.ExecuteCommandRequest()
            request.command_name = name
            
            # Convert arguments to proto Dict
            # For now, convert simple types to strings
            for key, val in arguments.items():
                request.arguments[key] = str(val)
            
            response_bytes = client.make_request(
                'execute_command',
                request.SerializeToString()
            )
            
            response = service_proto.ExecuteCommandReply()
            response.ParseFromString(response_bytes)
            
            # Return the result
            return response.result
                
        except Exception as e:
            raise RuntimeError(
                f'Failed to execute command {name}: {e}'
            )
    
    def __getattr__(self, item):
        """Forward attribute access to service methods."""
        if item in self.property_names:
            return self.get_property(item)
        elif item in self.command_names:
            def cmd(**kwargs):
                return self.execute_command(item, kwargs)
            return cmd
        elif item in self.data_stream_names:
            raise NotImplementedError(
                'Data streams not yet supported for remote services'
            )
        else:
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no "
                f"attribute '{item}'"
            )
