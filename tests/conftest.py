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
