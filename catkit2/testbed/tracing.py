import os
import json
import threading
import zmq
import contextlib

from ..proto import tracing_pb2 as tracing_proto
from .. import catkit_bindings


class TraceWriter:
    '''
    '''
    def __init__(self, host, port):
        self.f = None

        self.context = zmq.Context()

        self.host = host
        self.port = port

        self.shutdown_flag = threading.Event()
        self.thread = None

    def open(self, filename):
        '''
        '''
        self.shutdown_flag.clear()

        self._filename = filename

        self.thread = threading.Thread(target=self._loop)
        self.thread.start()

        return self

    def close(self):
        '''
        '''
        self.shutdown_flag.set()

        if self.thread:
            self.thread.join()

    def _loop(self):
        # Set up socket.
        socket = self.context.socket(zmq.SUB)
        socket.connect(f'tcp://{self.host}:{self.port}')
        socket.subscribe('')
        socket.RCVTIMEO = 50

        # Set initial time.
        # Subtracting one second before current time to hopefully never have negative timestamps.
        t_0 = catkit_bindings.get_timestamp() - 1_000_000_000

        with open(self._filename, 'w') as f:
            # Write JSON header.
            f.write('[\n')

            # Main loop.
            while not self.shutdown_flag.is_set():
                # Receive a new trace event.
                try:
                    message = socket.recv_multipart()
                except zmq.ZMQError as e:
                    if e.errno == zmq.EAGAIN:
                        # Timed out.
                        continue
                    else:
                        raise RuntimeError('Error during receive.') from e

                # Decode event.
                proto_event = tracing_proto.TraceEvent()
                proto_event.ParseFromString(message[0])

                # Convert event to JSON format.
                event_type = proto_event.WhichOneof('event')
                if event_type == 'interval':
                    interval = proto_event.interval
                    data = {
                        'name': interval.name,
                        'cat': interval.category,
                        'ph': 'X',
                        'ts': (interval.timestamp - t_0) / 1000,
                        'dur': interval.duration / 1000,
                        'pid': interval.process_id,
                        'tid': interval.thread_id
                    }
                elif event_type == 'instant':
                    instant = proto_event.instant
                    data = {
                        'name': instant.name,
                        'ph': 'i',
                        'ts': (instant.timestamp - t_0) / 1000,
                        'pid': instant.process_id,
                        'tid': instant.thread_id
                    }
                elif event_type == 'counter':
                    counter = proto_event.counter
                    data = {
                        'name': counter.name,
                        'ph': 'C',
                        'ts': (counter.timestamp - t_0) / 1000,
                        'args': {
                            counter.series: counter.counter
                        }
                    }

                data = json.dumps(data)

                # Write JSON to file.
                f.write(data + ',\n')

    def __enter__(self):
        '''
        '''
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        '''
        '''
        self.close()


@contextlib.contextmanager
def trace_interval(name, category=''):
    start = catkit_bindings.get_timestamp()

    try:
        yield
    finally:
        end = catkit_bindings.get_timestamp()

        return catkit_bindings.trace_interval(name, category, start, end - start)

def trace_instant(name):
    timestamp = catkit_bindings.get_timestamp()

    return catkit_bindings.trace_instant(name, timestamp)

def trace_counter(name, series, counter):
    timestamp = catkit_bindings.get_timestamp()

    return catkit_bindings.trace_counter(name, series, timestamp, counter)
