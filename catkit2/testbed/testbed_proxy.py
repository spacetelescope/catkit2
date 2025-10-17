from .. import catkit_bindings

from .service_proxy import ServiceProxy
from .remote_service_proxy import RemoteServiceProxy
from .proxies import *  # noqa


class TestbedProxy(catkit_bindings.TestbedProxy):
    '''A client for connecting to a testbed server.

    This object acts as a proxy for the Testbed object.
    '''
    def __init__(self, host, port):
        super().__init__(host, port)

        self._services = {}

    def get_service(self, service_id):
        '''Get a ServiceProxy object for the service `service_id`.

        Parameters
        ----------
        service_id : string
            The identifier for the service for which to return the ServiceProxy.

        Returns
        -------
        ServiceProxy or derived class object.
            A ServiceProxy for the named service.
        '''
        # If we already created a proxy, return it.
        if service_id in self._services:
            return self._services[service_id]

        # Check if this is a remote service
        service_config = self.config['services'].get(service_id, {})
        remote_server = service_config.get('remote_server')
        
        if remote_server:
            # This is a remote service - use RemoteServiceProxy
            # Get remote testbed config by parsing the testbed config
            testbed_config = self.config.get('testbed', {})
            remote_brokers = testbed_config.get(
                'remote_message_brokers', {}
            )
            
            # Find the remote testbed config
            remote_info = None
            if remote_brokers.get('enabled'):
                for conn in remote_brokers.get('connections', []):
                    if conn.get('name') == remote_server:
                        remote_info = conn
                        break
            
            proxy = RemoteServiceProxy(
                self, service_id, remote_server, remote_info
            )
        else:
            # This is a local service - use normal ServiceProxy
            # Get the service interface class.
            interface_name = service_config.get('interface')
            service_proxy_class = (
                ServiceProxy.get_service_interface(interface_name)
            )

            # Create proxy and store it in the cache.
            proxy = service_proxy_class(self, service_id)

        self._services[service_id] = proxy

        return proxy

    def __getattr__(self, item):
        '''Get the ServiceProxy named after the attribute.

        This acts as a shortcut for :func:`~catkit2.testbed.TestbedProxy.get_service`.

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
            service = self.get_service(item)

            # Remember the service for next time.
            setattr(self, item, service)

            return service
        except Exception as e:
            raise AttributeError(str(e))
