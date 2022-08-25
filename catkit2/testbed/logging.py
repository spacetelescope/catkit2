import logging
import threading
import zmq
import json
import contextlib

from ..catkit_bindings import submit_log_entry, Severity

class CatkitLogHandler(logging.StreamHandler):
    '''A log handler to pipe Python log messages into the catkit2 logging system.
    '''
    def emit(self, record):
        '''Handle the log message `record`.

        Parameters
        ----------
        record : LogRecord
            The log message to handle.
        '''
        filename = record.pathname
        line = record.lineno
        function = record.funcName
        message = record.msg % record.args
        severity = getattr(Severity, record.levelname)

        submit_log_entry(filename, line, function, severity, message)

class LogDistributor:
    '''Collects log messages on a port and re-publish them on another.

    This operates on a separate thread after it is started.

    Parameters
    ----------
    context : zmq.Context
        A previously-created ZMQ context. All sockets will be created on this context.
    input_port : integer
        The port number for the incoming log messages.
    output_port : integer
        The port number for the outgoing log messages.
    '''
    def __init__(self, context, input_port, output_port):
        self.context = context
        self.input_port = input_port
        self.output_port = output_port

        self.shutdown_flag = threading.Event()
        self.thread = None

    def start(self):
        '''Start the proxy thread.
        '''
        self.thread = threading.Thread(target=self.forwarder)
        self.thread.start()

    def stop(self):
        '''Stop the proxy thread.

        This function waits until the thread is actually stopped.
        '''
        self.shutdown_flag.set()

        if self.thread:
            self.thread.join()

    def forwarder(self):
        '''Create sockets and republish all received log messages.

        .. note::
            This function should not be called directly. Use
            :func:`~catkit2.testbed.LoggingProxy.start` to start the proxy.
        '''
        collector = self.context.socket(zmq.PULL)
        collector.RCVTIMEO = 50
        collector.bind(f'tcp://*:{self.input_port}')

        publicist = self.context.socket(zmq.PUB)
        publicist.bind(f'tcp://*:{self.output_port}')

        while not self.shutdown_flag.is_set():
            try:
                log_message = collector.recv_multipart()
                publicist.send_multipart(log_message)
            except zmq.ZMQError as e:
                if e.errno == zmq.EAGAIN:
                    # Timed out.
                    continue
                else:
                    raise RuntimeError('Error during receive') from e

            log_message = log_message[0].decode('ascii')
            log_message = json.loads(log_message)

            print(f'[{log_message["service_name"]}] {log_message["message"]}')

class LogWriter:
    def __init__(self, host, port, log_format=None):
        self.context = zmq.Context()
        self.host = host
        self.port = port

        if log_format is None:
            log_format = '{time} - {service_name} - {severity} - {message}'
        self.log_format = log_format

        self._output_file = None
        self._output_filename = None
        self.level = Severity.DEBUG

        self.shutdown_flag = threading.Event()
        self.thread = None

        self.lock = threading.Lock()

    def start(self):
        '''Start the proxy thread.
        '''
        self.thread = threading.Thread(target=self.loop)
        self.thread.start()

    def stop(self):
        '''Stop the proxy thread.

        This function waits until the thread is actually stopped.
        '''
        self.shutdown_flag.set()

        if self.thread:
            self.thread.join()

    @contextlib.contextmanager
    def output_to(self, output_filename):
        old_output_filename = self.output_filename

        self.output_filename = output_filename

        try:
            yield self
        finally:
            self.output_filename = old_output_filename

    @property
    def output_filename(self):
        return self._output_filename

    @output_filename.setter
    def output_filename(self, output_filename):
        with self.lock:
            # Close the output file, if there is one.
            if self._output_file is not None:
                self._output_file.close()
                self._output_file = None

            # Open output file with new filename.
            if output_filename is not None:
                self._output_file = open(output_filename, 'a')

        self._output_filename = output_filename

    def loop(self):
        # Set up sockets.
        socket = self.context.socket(zmq.SUB)
        socket.connect(f'tcp://{self.host}:{self.port}')
        socket.subscribe('')
        socket.RCVTIMEO = 50

        # Main loop.
        while not self.shutdown_flag.is_set():
            # Receive new log message.
            try:
                log_message = socket.recv_multipart()
            except zmq.ZMQError as e:
                if e.errno == zmq.EAGAIN:
                    # Timed out.
                    continue
                else:
                    raise RuntimeError('Error during receive.') from e

            # Decode log message.
            log_message = log_message[0].decode('ascii')
            log_message = json.loads(log_message)

            # Filter log message based on severity.
            severity = getattr(Severity, log_message['severity'].upper())
            if severity.value < self.level.value:
                continue

            # Format output message.
            message = self.log_format.format(**log_message)

            # Write log message to file.
            with self.lock:
                if self._output_file:
                    self._output_file.write(message + '\n')
                    self._output_file.flush()
