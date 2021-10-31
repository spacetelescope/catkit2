import os
import sys
import time
import random

from pyqtgraph.Qt import QtGui, QtCore, QtWidgets
import qdarkstyle
import numpy as np

os.environ['PYQTGRAPH_QT_LIB'] = 'PyQt5'

class LogMessage:
    def __init__(self, severity, module_name, message):
        self.severity = severity
        self.module_name = module_name
        self.message = message

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

        self.headers = ['Severity', 'Module', 'Message']
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

        if self.search_text not in message.message and self.search_text not in message.module_name:
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
                return QtCore.QVariant(message.severity.title())
            elif col == 1:
                return QtCore.QVariant(message.module_name)
            elif col == 2:
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

    @QtCore.pyqtSlot()
    def listen(self):
        while True:
            severity = ['critical', 'error', 'warning', 'info', 'debug', 'user'][random.randrange(6)]
            message = LogMessage(severity, 'test', 'This is a test message.')

            self.message_received.emit(message)

            time.sleep(0.1)

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
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)

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

        self.listen_thread = QtCore.QThread(self)

        self.listener = Listener()
        self.listener.message_received.connect(self.messages_model.add_message)
        self.listener.moveToThread(self.listen_thread)

        self.listen_thread.started.connect(self.listener.listen)
        self.listen_thread.start()

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
