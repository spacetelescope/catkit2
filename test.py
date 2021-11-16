'''
class Command:
    def __init__(self, name):
        self.name = name

    def __call__(self, *args, **kwargs):
        print(f'Called {self.name} with {args} and {kwargs}.')

class Service:
    def __init__(self):
        super().__setattr__('d', 3)

    @property
    def properties(self):
        return ['a', 'b']

    @property
    def commands(self):
        return ['c']

    def __getattr__(self, name):
        print('__getattr__')
        if name in self.properties:
            print(f'Getting property {name}')
            return 0
        elif name in self.commands:
            print(f'Constructing command {name}')
            command = Command(name)

            setattr(self, name, command)
            return command
        else:
            return super().__getattr__(name)

    def __setattr__(self, name, value):
        print('__setattr__')
        if name in self.properties:
            print(f'Setting property {name} to {value}.')
        else:
            super().__setattr__(name, value)

service = Service()
print('start')
print(service.a)
service.a = 3
service.b
service.c
service.c(1, 2, abc='kwarg')
service.c(1, 2, abc='kwarg')
service.c(1, 2, abc='kwarg')
print(hasattr(service, 'a'))
'''

from hicat2.bindings import DataStream
import numpy as np

num = 10
for n in [32, 64, 128, 256, 512, 1024, 2048]:
    print(f'{n}x{n}:')
    stream = DataStream.create('test', 'mod', 'float32', [n, n], num)
    data = np.random.randn(n*n).reshape((n, n)).astype('float32')

    import time

    N = int(10 / (n * n * 4 / 20e9))

    start = time.perf_counter()
    for i in range(N):
        stream.submit_data(data)
    end = time.perf_counter()

    print(f'{(end - start) / N * 1000000:.01f} us per submit')
    print(f'{int(N / (end - start))} fps')
    print(f'{N / (end - start) * n * n * 4 / 1024**3:.2f} GB/s')
    print()

    del stream

'''
class Service:
    def __init__(self):
        self._x = 0

    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, val):
        self._x = val

service = Service()
print(getattr(service, 'x'))
setattr(service, 'x', 2)
print(getattr(service, 'x'))
setattr(service, 'x', 3)
print(getattr(service, '_x'))
'''
'''
from hicat2.bindings import get_timestamp
import time

N = 100_000_000

start = get_timestamp()
for i in range(N):
    ts = get_timestamp()
end = get_timestamp()

print(f'{int((end - start) / N)} ns per timestamp')
'''