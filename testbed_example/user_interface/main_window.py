import os
import sys

from pyqtgraph.Qt import QtGui, QtCore
import qtvscodestyle as qtvsc
from qtvscodestyle.base import _load_stylesheet, _RESOURCES_BASE_DIR

from .logging_display import LoggingDisplay
from .bench_display import BenchDisplay

from catkit2.testbed.testbed_proxy import TestbedProxy

os.environ['PYQTGRAPH_QT_LIB'] = 'PyQt5'

class MainWindow(QtGui.QMainWindow):
    def __init__(self, testbed, *args):
        QtGui.QMainWindow.__init__(self, *args)

        self.testbed = testbed

        # Set icon
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.setWindowIcon(QtGui.QIcon(os.path.join(script_dir, 'assets', 'icon.jpg')))
        # Set window title and size.
        self.setWindowTitle(u'THD2 \u2013 Overview')
        self.resize(1350, 900)

        # Create and set central widget.
        self.central_widget = QtGui.QWidget(self)
        self.setCentralWidget(self.central_widget)

        # Create all sub-elements.
        self.create_bench_display()
        self.create_logging_display()

        splitter = QtGui.QSplitter(self)
        splitter.setOrientation(QtCore.Qt.Vertical)
        splitter.addWidget(self.bench_display)
        splitter.addWidget(self.logging_display)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 0.1)

        # Add all sub-elements to the main window.
        layout = QtGui.QVBoxLayout(self.central_widget)
        layout.addWidget(splitter)
        self.central_widget.setLayout(layout)

    def create_bench_display(self):
        self.bench_display = BenchDisplay(self.testbed, self)

    def create_logging_display(self):
        self.logging_display = LoggingDisplay(self.testbed, self)

def start_user_interface(port):
    script_dir = os.path.dirname(os.path.abspath(__file__))

    app = QtGui.QApplication(sys.argv)
    app.setStyleSheet(_load_stylesheet(qtvsc.Theme.DARK_VS, {}, output_svg_path=_RESOURCES_BASE_DIR))
    app.setWindowIcon(QtGui.QIcon(os.path.join(script_dir, 'assets', 'icon.jpg')))

    testbed = TestbedProxy('127.0.0.1', port)

    win = MainWindow(testbed)
    win.show()

    return app.exec_()
