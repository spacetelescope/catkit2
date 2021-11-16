from docopt import docopt

from ..bindings import Service

doc = '''
Usage:
  service --name NAME --port PORT
'''

def parse_service_args():
    arguments = docopt(doc)

    return arguments['NAME'], int(arguments['PORT'])
