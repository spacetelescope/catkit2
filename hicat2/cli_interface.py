'''
    ██╗  ██╗██╗ ██████╗ █████╗ ████████╗
    ██║  ██║██║██╔════╝██╔══██╗╚══██╔══╝
    ███████║██║██║     ███████║   ██║
    ██╔══██║██║██║     ██╔══██║   ██║
    ██║  ██║██║╚██████╗██║  ██║   ██║
    ╚═╝  ╚═╝╚═╝ ╚═════╝╚═╝  ╚═╝   ╚═╝
The control software for the HiCAT testbed.

Usage:
  hicat start (server | gui) [options]
  hicat (-h | --help)
  hicat --version

Options:
  -p, --port PORT   The port number on which the testbed server operates.
                    Defaults to the port specified in the config file.
  -h, --help        Show this help message and exit.
  --version         Show version and exit.
'''
import sys

from docopt import docopt

from .config import read_config
from .testbed import TestbedServer
from .user_interface.main_window import start_user_interface

def get_port(arguments):
    if arguments['--port'] is None:
        # Load port from config file.
        config = read_config()
        return config['testbed_server']['port']
    else:
        # Return specified port.
        try:
            return int(arguments['--port'])
        except ValueError:
            raise RuntimeError('The supplied port number must be an integer.')

def main():
    arguments = docopt(__doc__, version='0.1')

    if arguments['start']:
        port = get_port(arguments)

        if arguments['server']:
            print(f'Starting testbed server on port {port}...')
            server = TestbedServer(port)

            print('Use Ctrl-C to terminate the server and close all modules.')
            server.run()
        elif arguments['gui']:
            print(f'Starting testbed gui with testbed on on port {port}...')
            sys.exit(start_user_interface(port))
