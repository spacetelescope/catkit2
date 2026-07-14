from catkit2.catkit_bindings import Server, Client
import time
import pytest
import weakref

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

def test_server_client_communication(unused_port):
    port = unused_port()

    server = OurServer(port)
    client = OurClient(port)

    server.start()

    assert client.foo(b'abcd') == b'foo:abcd'

    with pytest.raises(RuntimeError, match='Data is incorrect'):
        client.bar()

    with pytest.raises(RuntimeError, match='Unknown request type'):
        client.baz()

    server.stop()

def test_server_cleanup(unused_port):
    port = unused_port()
    server = OurServer(port)

    # Use a weak reference to the server, to check if actually gets deleted.
    server_ref = weakref.ref(server)
    assert server_ref() is not None

    # Run the server.
    server.start()
    time.sleep(0.5)
    server.stop()

    # Delete the server.
    del server

    # The server should now have been deleted.
    assert server_ref() is None

def test_server_cleanup_manual(unused_port):
    port = unused_port()
    server = OurServer(port)

    # Use a weak reference to the server, to check if actually gets deleted.
    server_ref = weakref.ref(server)
    assert server_ref() is not None

    # Cleanup the request handlers and delete the server.
    server.cleanup_request_handlers()
    del server

    # This should have deleted the server object itself.
    assert server_ref() is None
