import logging
import sys

from .. import catkit_bindings
from .logging import CatkitLogHandler
from .testbed_proxy import TestbedProxy

doc = '''
Usage:
  service --id=ID --port=PORT --testbed_port=TESTBED_PORT

Options:
  --id=ID                      The ID of the service. This should correspond to a value in the testbed configuration.
  --port=PORT                  The port for this service.
  --testbed_port=TESTBED_PORT  The port where the testbed is running.
'''

def parse_service_args(argv=None):
    '''Parse the command line arguments for a launched service.

    Parameters
    ----------
    argv : list of strings or None
        The command line arguments. If this is None (default),
        sys.argv will be used instead.

    Returns
    -------
    service_id : string
        The name of the service that was launched.
    service_port : integer
        The port of the service to start on.
    testbed_port : integer
        The port of the testbed server to connect to.
    '''
    if argv is None:
        argv = sys.argv

    arguments = catkit_bindings.parse_service_args(argv)

    res = {
        'service_id': arguments[0],
        'service_port': arguments[1],
        'testbed_port': arguments[2],
    }

    return res

class Service(catkit_bindings.Service):
    log = logging.getLogger(__name__)

    def __init__(self, service_type, **kwargs):
        # Parse service arguments from argv, and update with overridden arguments.
        service_args = parse_service_args()
        service_args.update(kwargs)

        super().__init__(service_type, **service_args)

        # Override the testbed attribute with the extended Python version.
        self._testbed = TestbedProxy(getattr(super(), 'testbed').host, getattr(super(), 'testbed').port)

        # Set up log handler.
        self._log_handler = CatkitLogHandler()
        logging.getLogger(__name__).addHandler(self._log_handler)
        logging.getLogger(__name__).setLevel(logging.DEBUG)

    @property
    def testbed(self):
        return self._testbed
