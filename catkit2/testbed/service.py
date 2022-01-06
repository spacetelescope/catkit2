from docopt import docopt

from ..catkit_bindings import Service

doc = '''
Usage:
  service --name NAME --port PORT
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
    port : integer
        The port of the server to connect to.
    '''
    arguments = docopt(doc, argv=argv)

    return arguments['NAME'], int(arguments['PORT'])
