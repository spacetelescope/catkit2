from catkit2.catkit_bindings import Server, Client
import threading
import time
import pytest
import socket

def _get_unused_port():
    with socket.socket() as sock:
        sock.bind(('', 0))
        return sock.getsockname()[1]

class OurServer(Server):
    def __init__(self, port):
        super().__init__(port)

        self.register_request_handler('foo', self.foo)
        self.register_request_handler('bar', self.bar)

    def foo(self, data):
        return ('foo:' + data.decode('ascii')).encode('ascii')

    def bar(self, data):
        raise ValueError("Data is incorrect.")

class OurClient(Client):
    def __init__(self, port):
        super().__init__('127.0.0.1', port)

    def foo(self, data):
        return self.make_request('foo', data)

    def bar(self):
        return self.make_request('bar', b'other_data')

    def baz(self):
        return self.make_request('baz', b'even_other_data')

def test_server_client_communication():
    port = _get_unused_port()

    server = OurServer(port)
    client = OurClient(port)

    server.start()

    assert client.foo(b'abcd') == b'foo:abcd'

    with pytest.raises(RuntimeError, match='Data is incorrect'):
        client.bar()

    with pytest.raises(RuntimeError, match='Unknown request type'):
        client.baz()

    server.stop()
