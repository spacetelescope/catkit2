import logging

from ..bindings import submit_log_entry, Severity

class CatkitLogHandler(logging.StreamHandler):
    def emit(self, record):
        filename = record.pathname
        line = record.lineno
        function = record.funcName
        message = record.msg % record.args
        severity = getattr(Severity, record.levelname)

        submit_log_entry(filename, line, function, severity, message)
