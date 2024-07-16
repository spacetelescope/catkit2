import os
import sys
import traceback
import json

from pyqtgraph.Qt import QtGui, QtCore, QtWidgets
import qdarkstyle
import numpy as np
import zmq
import pytz
import datetime

os.environ['PYQTGRAPH_QT_LIB'] = 'PyQt5'

EUROPE_PARIS = pytz.timezone('Europe/Paris')

class LogMessage:
    def __init__(self, timestamp, severity, service_id, message):
        self.timestamp = timestamp
        self.severity = severity
        self.service_id = service_id
        self.message = message

    @property
    def timestamp(self):
        return self._timestamp

    @timestamp.setter
    def timestamp(self, timestamp):
        self._timestamp = timestamp

        # Convert timestamp to readable format.
        t = datetime.datetime.fromtimestamp(int(timestamp) / 1e9)
        t = t.astimezone(tz=EUROPE_PARIS)

        self._datetime = t.strftime('%Y-%m-%d %H:%M:%S')

    @property
    def datetime(self):
        return self._datetime

foreground_colors = {
    'error': QtGui.QColor('#F44336'),
    'warning': QtGui.QColor('#FF9800'),
    'info': QtGui.QColor('#2196F3'),
    'debug': QtGui.QColor('#4CAF50')
}

background_colors = {
    'critical': QtGui.QColor('#D32F2F')
}

severities = {'critical': 0, 'error': 1, 'warning': 2, 'user': 3, 'info': 4, 'debug': 5}

class LogMessageTableModel(QtCore.QAbstractTableModel):
    MAX_NUM_MESSAGES = 100000

    def __init__(self, parent=None):
        super().__init__(parent)

        self.headers = ['Time [Europe/Paris]', 'Severity', 'Service', 'Message']
        self.messages = []
        self.severities = np.array([], dtype='int')
        self.indices = np.array([], dtype='int')

        self.threshold = max(*severities.values())
        self.search_text = ''

        self.rows_loaded = LogMessageTableModel.MAX_NUM_MESSAGES

        for i, header in enumerate(self.headers):
            self.setHeaderData(i, QtCore.Qt.Horizontal, header)

    @QtCore.pyqtSlot(LogMessage)
    def add_message(self, message):
        self.beginResetModel()

        self.messages.append(message)
        self.severities = np.append(self.severities, severities[message.severity])

        if self.is_unfiltered(message):
            self.indices = np.append(self.indices, len(self.messages) - 1)

        self.endResetModel()

    @QtCore.pyqtSlot(str)
    def set_severity_filter(self, severity):
        self.beginResetModel()

        self.threshold = severities[severity.lower()]
        self.update_filter()

        self.endResetModel()

    @QtCore.pyqtSlot(str)
    def set_search_filter(self, text):
        self.beginResetModel()

        self.search_text = text
        self.update_filter()

        self.endResetModel()

    def is_unfiltered(self, message):
        if severities[message.severity] > self.threshold:
            return False

        if self.search_text not in message.message and self.search_text not in message.service_id:
            return False

        return True

    def update_filter(self):
        self.indices = np.flatnonzero([self.is_unfiltered(msg) for msg in self.messages])

    def rowCount(self, index=QtCore.QModelIndex()):
        if len(self.indices) <= self.rows_loaded:
            return len(self.indices)
        else:
            return self.rows_loaded

    def columnCount(self, index=QtCore.QModelIndex()):
        return len(self.headers)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        col = index.column()
        message = self.messages[self.indices[index.row()]]

        if role == QtCore.Qt.DisplayRole:
            if col == 0:
                return QtCore.QVariant(message.datetime)
            elif col == 1:
                return QtCore.QVariant(message.severity.title())
            elif col == 2:
                return QtCore.QVariant(message.service_id)
            elif col == 3:
                return QtCore.QVariant(message.message)
            return QtCore.QVariant()
        elif role == QtCore.Qt.TextAlignmentRole:
            return QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter
        elif role == QtCore.Qt.BackgroundRole:
            return background_colors.get(message.severity)
        elif role == QtCore.Qt.ForegroundRole:
            return foreground_colors.get(message.severity)

        return QtCore.QVariant()

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role != QtCore.Qt.DisplayRole:
            return QtCore.QVariant()

        if orientation == QtCore.Qt.Horizontal:
            return QtCore.QVariant(self.headers[section])
        return QtCore.QVariant(int(section + 1))

class Listener(QtCore.QObject):
    message_received = QtCore.pyqtSignal(LogMessage)

    def __init__(self, port, parent=None):
        super().__init__(parent)

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect(f"tcp://127.0.0.1:{port}")
        self.socket.subscribe('')

    @QtCore.pyqtSlot()
    def handle_messages(self):
        try:
            while True:
                message = self.socket.recv(flags=zmq.NOBLOCK)
                message = json.loads(message.decode('ascii'))

                log_message = LogMessage(message['timestamp'], message['severity'], message['service_id'], message['message'])

                self.message_received.emit(log_message)
        except zmq.ZMQError as e:
            if e.errno == zmq.EAGAIN:
                pass  # no message was ready (yet!)
            else:
                traceback.print_exc()

class LoggingDisplay(QtGui.QWidget):
    def __init__(self, testbed, parent=None):
        super().__init__(parent)

        self.testbed = testbed

        self.messages_model = LogMessageTableModel(self)

        self.table = QtGui.QTableView(self)
        self.table.setModel(self.messages_model)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.table.verticalHeader().setVisible(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtGui.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QtGui.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QtGui.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)

        self.controls = QtGui.QWidget(self)

        self.threshold_dropdown = QtGui.QComboBox(self.controls)
        self.threshold_dropdown.addItem('Critical')
        self.threshold_dropdown.addItem('Error')
        self.threshold_dropdown.addItem('Warning')
        self.threshold_dropdown.addItem('User')
        self.threshold_dropdown.addItem('Info')
        self.threshold_dropdown.addItem('Debug')
        self.threshold_dropdown.currentTextChanged.connect(self.messages_model.set_severity_filter)

        self.search_filter = QtGui.QLineEdit(self.controls)
        self.search_filter.setPlaceholderText('Search...')
        self.search_filter.textChanged.connect(self.messages_model.set_search_filter)

        self.clear_button = QtGui.QPushButton(self.controls)
        self.clear_button.setText('Clear')
        self.clear_button.clicked.connect(self.clear_filter)

        self.clear_filter()

        layout = QtGui.QHBoxLayout()
        layout.addWidget(QtGui.QLabel('Minimum severity:'))
        layout.addWidget(self.threshold_dropdown)
        layout.addWidget(QtGui.QLabel('Filter:'))
        layout.addWidget(self.search_filter)
        layout.addWidget(self.clear_button)
        layout.setContentsMargins(0, 5, 0, 5)
        self.controls.setLayout(layout)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.table)
        layout.addWidget(self.controls)
        layout.setContentsMargins(0, 5, 0, 5)
        self.setLayout(layout)

        self.listener = Listener(testbed.logging_egress_port, parent=self)
        self.listener.message_received.connect(self.messages_model.add_message)

        self.listen_timer = QtCore.QTimer(self)
        self.listen_timer.timeout.connect(self.listener.handle_messages)
        self.listen_timer.setInterval(100)
        self.listen_timer.start()

    def clear_filter(self):
        self.search_filter.setText('')

        i = self.threshold_dropdown.findText('Info')
        if i >= 0:
            self.threshold_dropdown.setCurrentIndex(i)

if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api=os.environ['PYQTGRAPH_QT_LIB']))

    win = LoggingDisplay(None)
    win.show()

    sys.exit(app.exec_())
    