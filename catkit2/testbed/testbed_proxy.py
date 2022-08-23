import zmq
import json
import os
import argparse
import threading

from ..catkit_bindings import DataStream
from .. import catkit_bindings

from .service_proxy import ServiceProxy
from .proxies import *

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
        if service_id in self._services:
            return self._services[service_id]

        # Get the service interface class.
        interface_name = self.config['services'][service_id].get('interface')
        service_proxy_class = ServiceProxy.get_service_interface(interface_name)

        return service_proxy_class(self, service_id)

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
