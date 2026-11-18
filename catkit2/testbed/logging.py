import logging
import threading
import json
import contextlib
from colorama import Fore, Back, Style

from ..catkit_bindings import submit_log_entry, Severity, MessageSubscriptionMode

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
    def __init__(self, broker):
        self.broker = broker
        self.subscription = None

        self.shutdown_flag = threading.Event()
        self.thread = None

    def start(self):
        '''Start the proxy thread.
        '''
        # Subscribe to all log topics
        self.subscription = self.broker.subscribe('logs', mode=MessageSubscriptionMode.Sequential)
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
        # Main loop.
        while not self.shutdown_flag.is_set():
            # Receive new log message.
            try:
                message = self.subscription.get_next_message(timeout_in_sec=0.1)
                if message is None:
                    continue
            except Exception:
                continue

            # Decode log message from payload.
            payload = message.payload.tobytes().decode('utf-8')
            log_message = json.loads(payload)

            self.handle_message(log_message)

    def handle_message(self, log_message):
        pass

class LogWriter(LogObserver):
    def __init__(self, broker, log_format=None):
        super().__init__(broker)

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

        # Add service_id to log_message for formatting (extract from source).
        log_message_for_format = log_message.copy()
        log_message_for_format['service_id'] = log_message['source']['service_id']
        log_message_for_format['filename'] = log_message['source']['file']
        log_message_for_format['line'] = log_message['source']['line']
        log_message_for_format['function'] = log_message['source']['function']

        # Format output message.
        message = self.log_format.format(**log_message_for_format)

        # Write log message to file.
        with self.file_lock:
            if self._output_file:
                self._output_file.write(message + '\n')
                self._output_file.flush()

class LogTerminal(LogObserver):
    def __init__(self, broker):
        super().__init__(broker)

        self.level = Severity.WARNING
        self.colors = {
            Severity.DEBUG: Fore.GREEN,
            Severity.INFO: Fore.CYAN,
            Severity.WARNING: Fore.YELLOW,
            Severity.ERROR: Fore.RED,
            Severity.CRITICAL: Fore.WHITE + Back.RED
        }

    def handle_message(self, log_message):
        severity = getattr(Severity, log_message['severity'].upper())
        service_id = log_message['source']['service_id']

        if service_id != 'experiment':
            if severity.value < self.level.value:
                return

        header = '{time} - {severity: <8} - {service_id} - {file}:{line}'.format(
            time=log_message['time'],
            severity=log_message['severity'],
            service_id=service_id,
            file=log_message['source']['file'],
            line=log_message['source']['line']
        )
        formatted_message = '{message}'.format(message=log_message['message'])

        print(header)
        print(self.colors[severity] + formatted_message + Style.RESET_ALL)
