from catkit2 import TestbedProxy, Testbed, read_config_files

import pytest
import socket
import pathlib
import os
import multiprocessing

@pytest.fixture()
def unused_port():
    def get():
        with socket.socket() as sock:
            sock.bind(('', 0))
            return sock.getsockname()[1]

    return get

def run_testbed(port, config):
    is_simulated = False

    testbed = Testbed(port, is_simulated, config)
    testbed.run()

@pytest.fixture(scope='session')
def testbed():
    config_path = pathlib.Path(os.path.join(os.path.dirname(__file__), 'config'))
    config_files = config_path.resolve().glob('*.yml')
    config = read_config_files(config_files)

    port = config['testbed']['default_port']

    process = multiprocessing.Process(target=run_testbed, args=(port, config))
    process.start()

    testbed = TestbedProxy('127.0.0.1', port)

    yield testbed

    testbed.shut_down()
    process.join()

@pytest.fixture(scope='session')
def dummy_service(testbed):
    testbed.start_service('dummy_service')

    yield testbed.dummy_service

    testbed.stop_service('dummy_service')
