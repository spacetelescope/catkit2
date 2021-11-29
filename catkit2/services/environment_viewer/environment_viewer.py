from threading import Thread
from catkit2.testbed import *
from catkit2.bindings import *

from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph as pg
import qdarkstyle

os.environ['PYQTGRAPH_QT_LIB'] = 'PyQt5'

class EnvironmentViewerModule(Module):
    def __init__(self):
        args = parse_module_args()
        Module.__init__(self, args.module_name, args.module_port)

        self.shutdown_flag = False

        self.testbed = Testbed(args.testbed_server_port)

        self.window = QtGui.QMainWindow()
        self.window.setWindowTitle('Environment Viewer')

        main_widget = QtGui.QWidget()
        self.window.setCentralWidget(main_widget)
        main = QtGui.QHBoxLayout()
        main_widget.setLayout(main)

        self.sensor = self.testbed.a
        self.lcd_temperature = QtGui.QLCDNumber(5)
        self.lcd_humidity = QtGui.QLCDNumber(5)

        main.addWidget(self.lcd_temperature)
        main.addWidget(self.lcd_humidity)

        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.update)
        self.update_timer.setInterval(1000 / 15)
        self.update_timer.start()

    def update(self):
        temperature_frame = self.sensor.temperature.get_frame(self.sensor.temperature.newest_available_frame_id)
        humidity_frame = self.sensor.humidity.get_frame(self.sensor.humidity.newest_available_frame_id)

        temperature_string = ('%.2f' % temperature_frame.data[0]).rjust(5)
        humidity_string = ('%.2f' % humidity_frame.data[0]).rjust(5)

        self.lcd_temperature.display(temperature_string)
        self.lcd_humidity.display(humidity_string)

    def main(self):
        self.window.show()
        QtGui.QApplication.instance().exec_()

    def shut_down(self):
        pass

def main():
    app = QtGui.QApplication([])
    app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api=os.environ['PYQTGRAPH_QT_LIB']))

    module = EnvironmentViewerModule()
    module.run()

if __name__ == '__main__':
    main()