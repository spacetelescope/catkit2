import logging

from docopt import docopt

from .. import catkit_bindings
from .logging import CatkitLogHandler

doc = '''
Usage:
  service --id ID --port PORT --testbed_port TESTBEDPORT
'''

class Service(catkit_bindings.Service):
    def __init__(self, *args, **kwargs):
        super().__init__(self, *args, **kwargs)

        self._log_handler = CatkitLogHandler()
        logging.getLogger(__name__).addHandler(self.log_handler)
        logging.getLogger(__name__).setLevel(logging.DEBUG)

def parse_service_args(argv=None):
    '''Parse the command line arguments for a launched service.

    Parameters
    ----------
    argv : list of strings or None
        The command line arguments. If this is None (default),
        sys.argv[1:] will be used instead.

    Returns
    -------
    service_id : string
        The name of the service that was launched.
    service_port : integer
        The port of the service to start on.
    testbed_port : integer
        The port of the testbed server to connect to.
    '''
    arguments = docopt(doc, argv=argv)

    return arguments['ID'], int(arguments['PORT']), int(arguments['TESTBEDPORT'])
