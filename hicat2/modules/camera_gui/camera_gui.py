from hicat2.bindings import Module, DataStream, Property, Command
from hicat2.testbed import parse_module_args, Testbed

import matplotlib.pyplot as plt
import matplotlib.cm as cm
from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph as pg
import time
import numpy as np
import requests
import datetime
from hcipy import *
import os
import zmq
import qdarkstyle

os.environ['PYQTGRAPH_QT_LIB'] = 'PyQt5'
off_color = 'darkred'
on_color = 'darkgreen'
busy_color = 'darkorange'

params = [
    {'name': 'Exposure', 'type': 'group', 'children':[
        {'name': 'ExposureTime', 'type': 'float', 'value': 0.001, 'step': 0.001},
        {'name': 'Gain', 'type': 'float', 'value': 0, 'step': 5}]},
    {'name': 'Window', 'type': 'group', 'children':[
        {'name': 'Width', 'type': 'int', 'value': 2048, 'decimals': 4, 'step': 16},
        {'name': 'Height', 'type': 'int', 'value': 1536, 'decimals': 4, 'step': 16},
        {'name': 'OffsetX', 'type': 'int', 'value': 0, 'decimals': 4, 'step': 16},
        {'name': 'OffsetY', 'type': 'int', 'value': 0, 'decimals': 4, 'step': 16}
    ]}
]

class CameraViewer(QtGui.QMainWindow):
    def __init__(self, camera):
        super().__init__()

        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.setWindowIcon(QtGui.QIcon(os.path.join(script_dir, 'icon.png')))

        self.camera = camera
        self.grid = make_uniform_grid((self.camera.width, self.camera.height), (self.camera.width, self.camera.height))
        self.last_frame_count = -1

        self.setWindowTitle('HiCAT Camera Viewer')

        main_widget = QtGui.QWidget()
        self.setCentralWidget(main_widget)
        main = QtGui.QHBoxLayout()
        main_widget.setLayout(main)

        self.left_side = QtGui.QWidget()
        vbox_left = QtGui.QVBoxLayout()
        self.left_side.setLayout(vbox_left)
        main.addWidget(self.left_side)

        # Add image box
        self.plot_widget = pg.PlotWidget()
        vbox_left.addWidget(self.plot_widget)
        self.plot_widget.setAspectLocked()

        self.image_box = pg.ImageItem()
        self.plot_widget.addItem(self.image_box)

        self.plot_widget2 = pg.PlotWidget()
        self.hist = pg.PlotCurveItem()
        self.plot_widget2.setMaximumHeight(200)
        self.plot_widget2.addItem(self.hist)
        vbox_left.addWidget(self.plot_widget2)

        self.image_box.setImage(np.zeros((self.camera.width, self.camera.height)), levels=(-1,1))

        colormap = cm.get_cmap('hot')
        colormap._init()
        self.lut_img = (colormap._lut * 255).view(np.ndarray)

        self.image_box.setLookupTable(self.lut_img)

        self.right_side = QtGui.QWidget()
        vbox_right = QtGui.QVBoxLayout()
        self.right_side.setLayout(vbox_right)
        main.addWidget(self.right_side)

        self.right_side.setMaximumWidth(350)

        # Add capture, display, listen and closed loop buttons
        self.acquisition_button = QtGui.QPushButton('Acquisition')
        self.acquisition_button.setStyleSheet('background-color: ' + off_color)
        vbox_right.addWidget(self.acquisition_button)

        # Add parameters access
        self.p = pg.parametertree.Parameter.create(name='Camera parameters', type='group', children=params)
        self.tree = pg.parametertree.ParameterTree()
        self.tree.setParameters(self.p, showTop=False)
        vbox_right.addWidget(self.tree)

        self.acquisition_button.clicked.connect(self.toggle_acquisition)

        self.p.param('Exposure', 'ExposureTime').sigValueChanged.connect(self.set_camera_exposure_time)
        self.p.param('Exposure', 'Gain').sigValueChanged.connect(self.set_camera_gain)
        self.p.param('Window', 'Width').sigValueChanged.connect(self.set_camera_width)
        self.p.param('Window', 'Height').sigValueChanged.connect(self.set_camera_height)
        self.p.param('Window', 'OffsetX').sigValueChanged.connect(self.set_camera_offset_x)
        self.p.param('Window', 'OffsetY').sigValueChanged.connect(self.set_camera_offset_y)

        # Set to values of camera
        self.p.param('Exposure', 'ExposureTime').setValue(self.camera.exposure_time / 1e6)
        self.p.param('Exposure', 'Gain').setValue(self.camera.gain)
        self.p.param('Window', 'Width').setValue(self.camera.width)
        self.p.param('Window', 'Height').setValue(self.camera.height)
        self.p.param('Window', 'OffsetX').setValue(self.camera.offset_x)
        self.p.param('Window', 'OffsetY').setValue(self.camera.offset_y)

        self.show()

        self.statusbar = QtGui.QStatusBar()
        self.setStatusBar(self.statusbar)

        self.display_framerate = 30
        self.display_timer = QtCore.QTimer()
        self.display_timer.timeout.connect(self.update_image)
        self.display_timer.setInterval(1000 / self.display_framerate)
        self.display_timer.start()

        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.update)
        self.update_timer.setInterval(1000 / 5)
        self.update_timer.start()

    def toggle_acquisition(self):
        if self.camera.is_acquiring:
            self.camera.end_acquisition()
            self.acquisition_button.setStyleSheet('background-color: ' + off_color)
        else:
            self.camera.start_acquisition()
            self.acquisition_button.setStyleSheet('background-color: ' + on_color)

    def update_image(self):
        try:
            frame = self.camera.images.get_latest_frame()
        except:
            # No image is available yet.
            return

        frame_count = frame.id
        if frame_count == self.last_frame_count:
            return
        self.last_frame_count = frame_count

        img = frame.data

        self.image_box.setImage(img.T, levels=(img.min() - 30, img.max() + 30))
        self.image_box.setRect(QtCore.QRectF(self.grid.x.min(), self.grid.y.min(), self.grid.x.ptp(), self.grid.y.ptp()))
        self.image_box.setLookupTable(self.lut_img)

        # Update histogram
        y, x = np.histogram(img, 128, range=(-2**13,2**16))
        self.hist.setData(x, np.log10(y+1), stepMode=True, fillLevel=0, brush=(255,255,255,255))

    def update(self):
        is_acquiring = self.camera.is_acquiring

        if is_acquiring:
            status_bar_message = 'Running at %0.1f fps' % 10#self.camera.fps
        else:
            status_bar_message = 'Stopped'
        status_bar_message += '; Device Temperature: %0.1f C' % self.camera.temperature

        try:
            frame = self.camera.images.get_latest_frame()
            frame_count = frame.id
        except Exception as e:
            print(e)
            frame_count = 0

        status_bar_message += '; Frame #%d' % frame_count

        self.statusbar.showMessage(status_bar_message)

        self.acquisition_button.setStyleSheet('background-color: ' + (on_color if is_acquiring else off_color))

    def set_camera_exposure_time(self, exposure_time):
        try:
            self.camera.exposure_time = exposure_time.value() * 1e6
        except:
            self.p.param('Exposure', 'ExposureTime').setValue(self.camera.exposure_time / 1e6)

    def set_camera_gain(self, gain):
        try:
            self.camera.gain = gain.value()
        except:
            self.p.param('Exposure', 'Gain').setValue(self.camera.gain)

    def set_camera_width(self, width):
        try:
            self.camera.width = width.value()
        except:
            self.p.param('Window', 'Width').setValue(self.camera.width)
        finally:
            self.grid = make_uniform_grid((self.camera.width, self.camera.height), (self.camera.width, self.camera.height))

    def set_camera_height(self, height):
        try:
            self.camera.height = height.value()
        except:
            self.p.param('Window', 'Height').setValue(self.camera.height)
        finally:
            self.grid = make_uniform_grid((self.camera.width, self.camera.height), (self.camera.width, self.camera.height))

    def set_camera_offset_x(self, offset_x):
        try:
            self.camera.offset_x = offset_x.value()
        except:
            self.p.param('Window', 'OffsetX').setValue(self.camera.offset_x)

    def set_camera_offset_y(self, offset_y):
        try:
            self.camera.offset_y = offset_y.value()
        except:
            self.p.param('Window', 'OffsetY').setValue(self.camera.offset_y)

class CameraGuiModule(Module):
    def __init__(self):
        args = parse_module_args()
        Module.__init__(self, args.module_name, args.module_port)

        self.testbed = Testbed(args.testbed_server_port)
        config = self.testbed.config['modules'][args.module_name]

        self.camera_name = config['camera_name']

        self.shutdown_flag = False

    def main(self):

        self.app = QtGui.QApplication([])
        self.app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api=os.environ['PYQTGRAPH_QT_LIB']))

        cam = getattr(self.testbed, self.camera_name)
        viewer = CameraViewer(cam)

        QtGui.QApplication.instance().exec_()

        cam.shut_down()

    def shut_down(self):
        self.app.quit()

if __name__ == '__main__':
    module = CameraGuiModule()
    module.run()
