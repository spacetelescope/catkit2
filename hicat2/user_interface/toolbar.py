import os
import sys
import time
import random

from pyqtgraph.Qt import QtGui, QtCore, QtWidgets
import qdarkstyle
import numpy as np

class Toolbar(QtGui.QWidget):
    def __init__(self, testbed):
        super().__init__()

        self.testbed = testbed

        self.num_modules_running = QtWidgets.QLCDNumber(3, self)
        self.num_modules_running.setSegmentStyle(QtGui.QLCDNumber.Flat)
        self.num_modules_running.setFrameStyle(QtGui.QFrame.StyledPanel | QtGui.QFrame.Plain)
        self.num_modules_running.display('24')

        self.safety = QtGui.QPushButton('Safe operation', self)

        self.testbed_time = QtWidgets.QLCDNumber(13, self)
        self.testbed_time.display('00:00:00:00.0')
        self.testbed_time.setSegmentStyle(QtGui.QLCDNumber.Flat)

        layout = QtGui.QHBoxLayout()
        layout.addWidget(QtGui.QLabel('Testbed safety:'))
        layout.addWidget(self.safety)
        layout.addWidget(QtGui.QLabel('Running modules:'))
        layout.addWidget(self.num_modules_running)
        layout.addWidget(QtGui.QLabel('Testbed time:'))
        layout.addWidget(self.testbed_time)
        self.setLayout(layout)
