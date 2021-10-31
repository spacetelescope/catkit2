import os
import sys

from pyqtgraph.Qt import QtGui, QtCore, QtSvg
import qdarkstyle

from .logging_display import LoggingDisplay
from .toolbar import Toolbar
from .bench_display import BenchDisplay

from hicat2.testbed import Testbed

os.environ['PYQTGRAPH_QT_LIB'] = 'PyQt5'

class MainWindow(QtGui.QMainWindow):
    def __init__(self, testbed, *args):
        QtGui.QMainWindow.__init__(self, *args)

        self.testbed = testbed

        # Set icon
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.setWindowIcon(QtGui.QIcon(os.path.join(script_dir, '..', 'icon.png')))

        # Set window title and size.
        self.setWindowTitle(u'Overview \u2013 HiCAT')
        self.resize(1350, 900)

        # Create and set central widget.
        self.central_widget = QtGui.QWidget(self)
        self.setCentralWidget(self.central_widget)

        # Create all sub-elements.
        #self.create_menubar()
        self.create_toolbar()
        self.create_bench_display()
        self.create_logging_display()

        splitter = QtGui.QSplitter(self)
        splitter.setOrientation(QtCore.Qt.Vertical)
        splitter.addWidget(self.bench_display)
        splitter.addWidget(self.logging_display)

        # Add all sub-elements to the main window.
        layout = QtGui.QVBoxLayout(self.central_widget)
        layout.addWidget(self.toolbar)
        layout.addWidget(splitter)
        self.central_widget.setLayout(layout)

    def create_toolbar(self):
        self.toolbar = Toolbar(self.testbed, self)

    def create_bench_display(self):
        self.bench_display = BenchDisplay(self.testbed, self)

    def create_logging_display(self):
        self.logging_display = LoggingDisplay(self.testbed, self)

def start_user_interface(port):
    app = QtGui.QApplication(sys.argv)
    app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api=os.environ['PYQTGRAPH_QT_LIB']))

    testbed = Testbed(port)

    win = MainWindow(testbed)
    win.show()

    return app.exec_()
