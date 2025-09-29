'''
The control software for an example testbed called "Benchlet".

Usage:
  benchlet start server [--port PORT_ID] [--simulated] [--config_path PATH]...
  benchlet (-h | --help)
  benchlet --version

Options:
  -p, --port PORT_ID      The port number on which the testbed server operates.
                          Defaults to the port specified in the config file.
  --simulated             Whether the testbed server should be run in simulated mode or not.
  -c, --config_path PATH  A path were additional config files can be found. By default,
                          the config directory of this example is prepended.
  -h, --help              Show this help message and exit.
  --version               Show version and exit.
'''
from docopt import docopt
from catkit2.testbed.testbed import Testbed
from . import config


def get_port(arguments, config):
    if arguments['--port'] is None:
        # Load port from config file.
        return config['testbed']['default_port']
    else:
        # Return specified port.
        try:
            return int(arguments['--port'])
        except ValueError:
            raise RuntimeError('The supplied port number must be an integer.')


def main():
    arguments = docopt(__doc__, version='0.1')

    if arguments['start']:
        configuration = config.read_config(arguments['--config_path'])
        port = get_port(arguments, configuration)

        if arguments['server']:
            print(f'Starting the Benchlet testbed on port {port}...')
            server = Testbed(port, arguments['--simulated'], configuration)

            print('Use Ctrl-C to terminate the server and close all modules.')
            server.run()
