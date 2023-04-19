from catkit2 import Service

import numpy as np

N = 16

class DummyService(Service):
    def __init__(self):
        super().__init__('dummy_service')

        self.readonly_property = self.config['readonly_property']
        self.readwrite_property = 1

    def open(self):
        self.make_property('readonly_property', self.get_readonly)
        self.make_property('readwrite_property', self.get_readwrite, self.set_readwrite)

        self.make_command('add', self.add)
        self.make_command('push_on_stream', self.push_on_stream)

        self.stream = self.make_data_stream('stream', 'float64', [N, N], 20)
        self.push_on_stream()

    def main(self):
        while not self.should_shut_down:
            self.sleep(0.1)

    def close(self):
        pass

    def get_readonly(self):
        return self.readonly_property

    def get_readwrite(self):
        return self.readwrite_property

    def set_readwrite(self, value):
        self.readwrite_property = value

    def add(self, a, b):
        return a + b

    def push_on_stream(self):
        arr = np.random.randn(N, N).astype('float64')
        self.stream.submit_data(arr)

if __name__ == '__main__':
    service = DummyService()
    service.run()
