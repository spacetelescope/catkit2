'''
The control software for an example testbed called {{cookiecutter.project_slug}}.

Usage:
  {{cookiecutter.project_slug}} start server [--port PORT_ID] [--simulated] [--config_path PATH]...
  {{cookiecutter.project_slug}} (-h | --help)
  {{cookiecutter.project_slug}} --version
  
Options:
  -p, --port PORT_ID      The port number on which the testbed server operates.
                          Defaults to the port specified in the config file.
  --simulated             Whether the testbed server should be run in simulated mode or not.
  -c, --config_path PATH  A path were additional config files can be found. By default,
                          the config directory of this example is prepended.
  -h, --help              Show this help message and exit.
  --version               Show version and exit.
'''

from catkit2.testbed.testbed import Testbed
from docopt import docopt
from . import config

from {{cookiecutter.project_slug}} import utils

def get_port(arguments, config):
    if arguments['--port'] is None:
        # Load port from config file.
        return config['testbed']['default_port']
    else:
        # Return specified port.
        try:
            return int(arguments['--port'])
        except ValueError:
            raise RuntimeError(
                'The supplied port number must be an integer.')


def main():
    arguments = docopt(__doc__, version='0.1')

    if arguments['start']:
        configuration = config.read_config(arguments['--config_path'])
        port = get_port(arguments, configuration)

        if arguments['server']:
            print(
                'Starting the {{cookiecutter.project_slug}} testbed on {}...'.format(
                    port))
            server = Testbed(port, arguments['--simulated'], configuration)

            print(
                'Use Ctrl-C to terminate the server and close all modules.')
            server.run()
