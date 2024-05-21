import logging
import threading
import zmq
import json
import contextlib
from colorama import Fore, Back, Style

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

class LogObserver:
    def __init__(self, host, port):
        self.context = zmq.Context()
        self.host = host
        self.port = port

        self.shutdown_flag = threading.Event()
        self.thread = None

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

            self.handle_message(log_message)

    def handle_message(self, log_message):
        pass

class LogWriter(LogObserver):
    def __init__(self, host, port, log_format=None):
        super().__init__(host, port)

        if log_format is None:
            log_format = '{time} - {service_id} - {severity} - {message}'
        self.log_format = log_format

        self._output_file = None
        self._output_filename = None
        self.level = Severity.DEBUG

        self.file_lock = threading.Lock()

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
        with self.file_lock:
            # Close the output file, if there is one.
            if self._output_file is not None:
                self._output_file.close()
                self._output_file = None

            # Open output file with new filename.
            if output_filename is not None:
                self._output_file = open(output_filename, 'a')

        self._output_filename = output_filename

    def handle_message(self, log_message):
        # Filter log message based on severity.
        severity = getattr(Severity, log_message['severity'].upper())
        if severity.value < self.level.value:
            return

        # Format output message.
        message = self.log_format.format(**log_message)

        # Write log message to file.
        with self.file_lock:
            if self._output_file:
                self._output_file.write(message + '\n')
                self._output_file.flush()

class LogTerminal(LogObserver):
    def __init__(self, host, port):
        super().__init__(host, port)

        self.level = Severity.WARNING
        self.colors = {
            Severity.DEBUG: Fore.GREEN,
            Severity.INFO: Fore.BLUE,
            Severity.WARNING: Fore.YELLOW,
            Severity.ERROR: Fore.RED,
            Severity.CRITICAL: Fore.WHITE + Back.RED
        }

    def handle_message(self, log_message):
        severity = getattr(Severity, log_message['severity'].upper())

        if log_message['service_id'] != 'experiment':
            if severity.value < self.level.value:
                return

        header = '{time} - {severity: <8} - {service_id} - {filename}:{line}'.format(**log_message)
        formatted_message = '{message}'.format(**log_message)

        print(header)
        print(self.colors[severity] + formatted_message + Style.RESET_ALL)
