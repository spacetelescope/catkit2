import matplotlib.cm as cm
from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph as pg
import time
import numpy as np
import hcipy

from .common import Toggle

params = [
    {'name': 'Exposure', 'type': 'group', 'children': [
        {'name': 'ExposureTime', 'type': 'float', 'value': 0.001, 'step': 0.001},
        {'name': 'Gain', 'type': 'float', 'value': 0, 'step': 5}]},
    {'name': 'Window', 'type': 'group', 'children': [
        {'name': 'Width', 'type': 'int', 'value': 2048, 'decimals': 4, 'step': 16},
        {'name': 'Height', 'type': 'int', 'value': 1536, 'decimals': 4, 'step': 16},
        {'name': 'OffsetX', 'type': 'int', 'value': 0, 'decimals': 4, 'step': 16},
        {'name': 'OffsetY', 'type': 'int', 'value': 0, 'decimals': 4, 'step': 16}
    ]}
]

class CameraViewer(QtGui.QMainWindow):
    def __init__(self, camera, parent):
        super().__init__(parent)

        self.camera = camera
        self.grid = hcipy.make_uniform_grid((self.camera.width, self.camera.height), (self.camera.width, self.camera.height))
        self.last_frame_count = -1

        self.setWindowTitle(f'THD2 \u2013 Camera Viewer \u2013 {camera.id}')
        self.resize(800, 700)

        widget_inner = QtGui.QSplitter(self)
        widget_inner.setOrientation(QtCore.Qt.Vertical)

        widget_outer = QtGui.QSplitter(self)
        widget_outer.setOrientation(QtCore.Qt.Horizontal)

        # Add image box
        self.plot_widget = pg.PlotWidget(self)
        self.plot_widget.setAspectLocked()

        self.image_box = pg.ImageItem()
        self.image_box.setImage(np.zeros((self.camera.width, self.camera.height)), levels=(-1, 1))
        self.plot_widget.addItem(self.image_box)

        self.histogram = pg.PlotWidget(widget_inner)
        self.hist = pg.PlotCurveItem()
        self.histogram.setMinimumHeight(200)
        self.histogram.addItem(self.hist)

        colormap = cm.get_cmap('inferno')
        colormap._init()
        self.lut_img = (colormap._lut[:-3] * 255).view(np.ndarray).astype('ubyte')

        self.image_box.setLookupTable(self.lut_img)

        self.sidebar = QtGui.QWidget(widget_outer)
        vbox_sidebar = QtGui.QVBoxLayout()
        self.sidebar.setLayout(vbox_sidebar)
        self.sidebar.setMinimumWidth(250)

        self.acquisition_toggle = Toggle()
        self.acquisition_toggle.clicked.connect(self.toggle_acquisition)

        hbox = QtGui.QHBoxLayout()
        hbox.addWidget(QtGui.QLabel('Acquisition'))
        hbox.addWidget(self.acquisition_toggle)
        hbox.setContentsMargins(0, 0, 0, 0)

        w = QtGui.QWidget()
        w.setLayout(hbox)
        vbox_sidebar.addWidget(w)

        self.log_scale_toggle = Toggle()

        hbox = QtGui.QHBoxLayout()
        hbox.addWidget(QtGui.QLabel('Log scale'))
        hbox.addWidget(self.log_scale_toggle)
        hbox.setContentsMargins(0, 0, 0, 0)

        w = QtGui.QWidget()
        w.setLayout(hbox)
        vbox_sidebar.addWidget(w)

        # Add parameters access
        self.p = pg.parametertree.Parameter.create(name='Camera parameters', type='group', children=params)
        self.tree = pg.parametertree.ParameterTree(self.sidebar)
        self.tree.setParameters(self.p, showTop=False)
        vbox_sidebar.addWidget(self.tree)

        # Set to values of camera
        self.p.param('Exposure', 'ExposureTime').setValue(self.camera.exposure_time / 1e6)
        self.p.param('Exposure', 'Gain').setValue(self.camera.gain)
        self.p.param('Window', 'Width').setValue(self.camera.width)
        self.p.param('Window', 'Height').setValue(self.camera.height)
        self.p.param('Window', 'OffsetX').setValue(self.camera.offset_x)
        self.p.param('Window', 'OffsetY').setValue(self.camera.offset_y)

        # Connect functions to change camera parameters.
        self.p.param('Exposure', 'ExposureTime').sigValueChanged.connect(self.set_camera_exposure_time)
        self.p.param('Exposure', 'Gain').sigValueChanged.connect(self.set_camera_gain)
        self.p.param('Window', 'Width').sigValueChanged.connect(self.set_camera_width)
        self.p.param('Window', 'Height').sigValueChanged.connect(self.set_camera_height)
        self.p.param('Window', 'OffsetX').sigValueChanged.connect(self.set_camera_offset_x)
        self.p.param('Window', 'OffsetY').sigValueChanged.connect(self.set_camera_offset_y)

        self.statusbar = QtGui.QStatusBar()
        self.setStatusBar(self.statusbar)

        widget_inner.addWidget(self.plot_widget)
        widget_inner.addWidget(self.histogram)
        widget_inner.setStretchFactor(0, 1)
        widget_inner.setStretchFactor(1, 0)

        widget_outer.addWidget(widget_inner)
        widget_outer.addWidget(self.sidebar)
        widget_outer.setStretchFactor(0, 1)
        widget_outer.setStretchFactor(1, 0)

        self.setCentralWidget(widget_outer)

        self.fps_last_time = None
        self.fps_last_frame_id = None
        self.fps = 0

        self.display_framerate = 15
        self.display_timer = QtCore.QTimer(self)
        self.display_timer.timeout.connect(self.update_image)
        self.display_timer.setInterval(1000 / self.display_framerate)
        self.display_timer.start()

        self.update_timer = QtCore.QTimer(self)
        self.update_timer.timeout.connect(self.update)
        self.update_timer.setInterval(1000 / 5)
        self.update_timer.start()

        self.setWindowFlags(QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

    def toggle_acquisition(self, value):
        if value:
            self.camera.start_acquisition()
        else:
            self.camera.end_acquisition()

    def update_image(self):
        # If the camera is not running, do not update the screen.
        if not self.camera.is_running:
            return

        try:
            frame = self.camera.images.get_latest_frame()
        except Exception:
            # No image is available yet.
            return

        frame_count = frame.id
        if frame_count == self.last_frame_count:
            return
        self.last_frame_count = frame_count

        img = frame.data

        if self.log_scale_toggle.isChecked():
            view_img = np.log10(img / img.max() + 1e-10)
            levels = (-5, 0)
        else:
            view_img = img
            levels = (img.min() - 10, img.max() + 10)

        rect = QtCore.QRectF(self.grid.x.min(), self.grid.y.min(), self.grid.x.ptp(), self.grid.y.ptp())

        autoLevels = False
        self.image_box.setImage(view_img.T, autoLevels=autoLevels, levels=levels, rect=rect)

        # Update histogram
        y, x = np.histogram(img, 128, range=(-2**13, 2**16))
        self.hist.setData(x, np.log10(y + 1), stepMode=True, fillLevel=0, brush=(255, 255, 255, 255))

    def update(self):
        # If the camera is not running, do not update the screen.
        if not self.camera.is_running:
            return

        is_acquiring = self.camera.is_acquiring.get()[0] > 0
        frame_count = 0

        self.acquisition_toggle.setChecked(is_acquiring)

        try:
            frame = self.camera.images.get_latest_frame()
            frame_count = frame.id

            t = time.perf_counter()
            if self.fps_last_frame_id is not None:
                num_frames_since_last_update = frame.id - self.fps_last_frame_id
                time_since_last_update = t - self.fps_last_time

                self.fps = self.fps * 0.5 + 0.5 * (num_frames_since_last_update / time_since_last_update)

            self.fps_last_frame_id = frame.id
            self.fps_last_time = t
        except Exception:
            pass

        if is_acquiring:
            status_bar_message = f'Running at {self.fps:.1f} fps'
        else:
            status_bar_message = 'Stopped'
        status_bar_message += '; Device Temperature: %0.1f C' % self.camera.temperature.get()[0]

        status_bar_message += '; Frame #%d' % frame_count

        self.statusbar.showMessage(status_bar_message)

    def set_camera_exposure_time(self, exposure_time):
        try:
            self.camera.exposure_time = exposure_time.value() * 1e6
        except Exception:
            self.p.param('Exposure', 'ExposureTime').setValue(self.camera.exposure_time / 1e6)

    def set_camera_gain(self, gain):
        try:
            self.camera.gain = gain.value()
        except Exception:
            self.p.param('Exposure', 'Gain').setValue(self.camera.gain)

    def set_camera_width(self, width):
        try:
            self.camera.width = width.value()
        except Exception:
            self.p.param('Window', 'Width').setValue(self.camera.width)
        finally:
            self.grid = hcipy.make_uniform_grid((self.camera.width, self.camera.height), (self.camera.width, self.camera.height))

    def set_camera_height(self, height):
        try:
            self.camera.height = height.value()
        except Exception:
            self.p.param('Window', 'Height').setValue(self.camera.height)
        finally:
            self.grid = hcipy.make_uniform_grid((self.camera.width, self.camera.height), (self.camera.width, self.camera.height))

    def set_camera_offset_x(self, offset_x):
        try:
            self.camera.offset_x = offset_x.value()
        except Exception:
            self.p.param('Window', 'OffsetX').setValue(self.camera.offset_x)

    def set_camera_offset_y(self, offset_y):
        try:
            self.camera.offset_y = offset_y.value()
        except Exception:
            self.p.param('Window', 'OffsetY').setValue(self.camera.offset_y)
