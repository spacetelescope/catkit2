import logging

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
