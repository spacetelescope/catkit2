from catkit2.catkit_bindings import Server, Client
import threading
import time
import pytest

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
        return self.make_request('bar', 'other_data')

    def baz(self):
        return self.make_request('baz', 'even_other_data')

def test_server_client_communication():
    server = OurServer(8080)
    client = OurClient(8080)

    server.start()

    assert client.foo('abcd') == 'foo:abcd'

    with pytest.raises(RuntimeError, match='Data is incorrect'):
        client.bar()

    with pytest.raises(RuntimeError, match='Unknown request type'):
        client.baz()

    server.stop()
