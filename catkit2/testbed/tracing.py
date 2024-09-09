import json
import threading
import zmq
import contextlib

from ..proto import tracing_pb2 as tracing_proto
from .. import catkit_bindings


def write_json(f, data):
    data = json.dumps(data, indent=None, separators=(',', ':'))

    # Write JSON to file.
    f.write(data + ',\n')


class TraceWriter:
    '''A writer for performance trace logs.

    This writer writes the trace log in Google JSON format, described by
    https://docs.google.com/document/d/1CvAClvFfyA5R-PhYUmn5OOQtYMH4h6I0nSsKchNAySU
    This file can be read in by a number of trace log viewers for inspection.

    Parameters
    ----------
    host : str
        The host which distributes the trace messages.
    port : int
        The port on which the host distributes the trace messages.
    '''
    def __init__(self, host, port):
        self.f = None

        self.context = zmq.Context()

        self.host = host
        self.port = port

        self.shutdown_flag = threading.Event()
        self.thread = None

    def open(self, filename):
        '''Open the writer.

        Parameters
        ----------
        filename : str
            The path to the file where to write the performance trace.

        Returns
        -------
        TraceWriter
            The current trace writer. This is for use as a context manager.
        '''
        self.shutdown_flag.clear()

        self._filename = filename

        self.thread = threading.Thread(target=self._loop)
        self.thread.start()

        return self

    def close(self):
        '''Close the writer.
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

        # Set up cache for process names.
        process_names = {}
        thread_names = {}

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
                # All JSON timestamps are in us, our timestamps are in ns, so
                # divide all times by 1000.
                event_type = proto_event.WhichOneof('event')
                if event_type == 'interval':
                    raw_data = proto_event.interval
                    data = {
                        'name': raw_data.name,
                        'cat': raw_data.category,
                        'ph': 'X',
                        'ts': (raw_data.timestamp - t_0) / 1000,
                        'dur': raw_data.duration / 1000,
                        'pid': raw_data.process_id,
                        'tid': raw_data.thread_id
                    }
                elif event_type == 'instant':
                    raw_data = proto_event.instant
                    data = {
                        'name': raw_data.name,
                        'ph': 'i',
                        'ts': (raw_data.timestamp - t_0) / 1000,
                        'pid': raw_data.process_id,
                        'tid': raw_data.thread_id
                    }
                elif event_type == 'counter':
                    raw_data = proto_event.counter
                    data = {
                        'name': raw_data.name,
                        'ph': 'C',
                        'ts': (raw_data.timestamp - t_0) / 1000,
                        'pid': raw_data.process_id,
                        'args': {
                            raw_data.series: raw_data.counter
                        }
                    }

                if hasattr(raw_data, 'process_name') and raw_data.process_name:
                    # We haven't seen a message from this process before.
                    # Extract and store process name, and write metadata.
                    if raw_data.process_id not in process_names:
                        process_names[raw_data.process_id] = raw_data.process_name

                        metadata = {
                            'name': 'process_name',
                            'ph': 'M',
                            'pid': raw_data.process_id,
                            'args': {
                                'name': raw_data.process_name
                            }
                        }

                        write_json(f, metadata)

                if hasattr(raw_data, 'thread_name') and raw_data.thread_name:
                    # We haven't seen a message from this process before.
                    # Extract and store process name, and write metadata.
                    if raw_data.process_id not in thread_names:
                        thread_names[raw_data.process_id] = raw_data.thread_name

                        metadata = {
                            'name': 'thread_name',
                            'ph': 'M',
                            'pid': raw_data.process_id,
                            'tid': raw_data.thread_id,
                            'args': {
                                'name': raw_data.thread_name
                            }
                        }

                    write_json(f, metadata)

                write_json(f, data)

    def __enter__(self):
        '''Enter the context manager.

        Returns
        -------
        TraceWriter
            The current trace writer.
        '''
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        '''Exit the context manager.

        Parameters
        ----------
        exc_type : class
            The exception class.
        exc_val :
            The value of the exception.
        exc_tb : traceback
            The traceback of the exception.
        '''
        self.close()


@contextlib.contextmanager
def trace_interval(name, category=''):
    '''Trace an interval event.

    Both the start and end time will be logged and
    the event will be shown as a bar in the trace log viewer.

    Parameters
    ----------
    name : str
        The name of the event.
    category : str, optional
        The category of interval. Events with the same category will be
        colored the same in the log viewer. The default is empty.
    '''
    start = catkit_bindings.get_timestamp()

    try:
        yield
    finally:
        end = catkit_bindings.get_timestamp()

        catkit_bindings.trace_interval(name, category, start, end - start)

def trace_instant(name):
    '''Trace an instant event.

    The time at which this function is called will be logged and
    the event will be shown as a single arrow or line in the trace
    log viewer.

    Parameters
    ----------
    name : str
        The name of the event.
    '''
    timestamp = catkit_bindings.get_timestamp()

    catkit_bindings.trace_instant(name, timestamp)

def trace_counter(name, series, counter):
    '''Trace a counter event.

    The time at which this function is called is logged, in addition
    to a scalar that we want to keep track of. The event will be shown
    as a line graph.

    Parameters
    ----------
    name : str
        The name of the event.
    series : str
        The series of the event, e.g. "contrast", "iteration".
    counter : float, int
        The contents of this event, i.e. what changes over time.
    '''
    timestamp = catkit_bindings.get_timestamp()

    catkit_bindings.trace_counter(name, series, timestamp, counter)
