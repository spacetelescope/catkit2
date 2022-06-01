from docopt import docopt

from ..catkit_bindings import Service

doc = '''
Usage:
  service --name NAME --service_port SERVICEPORT --testbed_port TESTBEDPORT
'''

def parse_service_args(argv=None):
    '''Parse the command line arguments for a launched service.

    Parameters
    ----------
    argv : list of strings or None
        The command line arguments. If this is None (default),
        sys.argv[1:] will be used instead.

    Returns
    -------
    service_name : string
        The name of the service that was launched.
    service_port : integer
        The port of the service to start on.
    testbed_port : integer
        The port of the testbed server to connect to.
    '''
    arguments = docopt(doc, argv=argv)

    return arguments['NAME'], int(arguments['SERVICEPORT']), int(arguments['TESTBEDPORT'])
