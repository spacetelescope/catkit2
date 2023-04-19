from catkit2 import TestbedProxy, Testbed, read_config_files

import pytest
import socket
import pathlib
import os
import multiprocessing

@pytest.fixture(scope='session')
def unused_port():
    def get():
        with socket.socket() as sock:
            sock.bind(('', 0))
            return sock.getsockname()[1]

    return get

def run_testbed(port):
    is_simulated = False

    config_path = pathlib.Path(os.path.join(os.path.dirname(__file__), 'config'))
    config_files = config_path.resolve().glob('*.yml')
    config = read_config_files(config_files)

    testbed = Testbed(port, is_simulated, config)
    testbed.run()

@pytest.fixture(scope='session')
def testbed(unused_port):
    port = unused_port()

    process = multiprocessing.Process(target=run_testbed, args=(port,))
    process.start()

    testbed = TestbedProxy('127.0.0.1', port)

    yield testbed

    testbed.shut_down()
    process.join()

@pytest.fixture(scope='session')
def test_service(testbed):
    testbed.start_service('test_service')

    yield testbed.test_service

    testbed.stop_service('test_service')
