from catkit2.catkit_bindings import Server, Client, LogConsole
from docopt import docopt
import threading
import time

class OurServer(Server):
    def __init__(self, port):
        super().__init__(port)

        self.register_request_handler('foo', self.foo)
        self.register_request_handler('bar', self.bar)

    def foo(self, data):
        return 'bar'

    def bar(self, data):
        return 'baz'
        raise ValueError("Data is incorrect.")

class OurClient(Client):
    def __init__(self, port):
        super().__init__('127.0.0.1', port)

    def foo(self):
        return self.make_request('foo', 'data')

    def bar(self):
        return self.make_request('bar', 'other_data')

__doc__ = '''Tester.

Usage:
  tester server
  tester client
'''

if __name__ == '__main__':
    args = docopt(__doc__)

    #console = LogConsole()

    port = 6435

    if args['client']:
        client = OurClient(port)
        print(client.foo())

        N = 100000

        print('Doing performance testing...')
        start = time.perf_counter()
        for i in range(N):
            client.foo()
        end = time.perf_counter()

        print('On average,', int((end - start) / N * 1000000), 'us per request')

    if args['server']:
        server = OurServer(port)
        server.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            server.shut_down()
