from catkit2 import TraceWriter, TracingProxy
from catkit2.catkit_bindings import get_timestamp
import datetime
import time
import random
import numpy as np


def main():
    writer = TraceWriter('127.0.0.1', 5239)
    proxy = TracingProxy('127.0.0.1', 5238)

    time.sleep(0.1)

    with writer.open(f'trace_{get_timestamp()}.json'):
        for i in range(100):
            with proxy.trace_interval('a'):
                for j in range(random.randint(1, 4)):
                    with proxy.trace_interval('b'):
                        np.random.randn(random.randint(1000, 10000))

                if random.randint(0, 1):
                    proxy.trace_instant('blank')

        time.sleep(0.1)


if __name__ == '__main__':
    main()
