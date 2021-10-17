import os
import sys
import time
import random
import functools
import yaml

from xml.dom import minidom

from pyqtgraph.Qt import QtGui, QtCore, QtWidgets, QtSvg
import qdarkstyle
import numpy as np

from camera_viewer import CameraViewer

class IconButton(QtGui.QPushButton):
    def __init__(self, icon_fname, relative_position, tooltip, parent):
        super().__init__(parent)

        self.icon_fname = icon_fname
        self.relative_position = relative_position

        self.icon_renderer = QtSvg.QSvgRenderer('assets/icon_%s.svg' % icon_fname)

        self.setToolTip(tooltip)

        self.setSizePolicy(QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed))

        self.shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        self.shadow.setColor(QtGui.QColor('#70000000'))
        self.set_elevation(6)

        self.setGraphicsEffect(self.shadow)

        self.pressed.connect(functools.partial(self.set_elevation, 3))
        self.released.connect(functools.partial(self.set_elevation, 6))
        self.clicked.connect(lambda: print('clicked ' + tooltip))

    def set_elevation(self, elevation):
        self.shadow.setBlurRadius(1.5 * elevation)
        self.shadow.setOffset(0.6 * elevation, 0.6 * elevation)

        self._elevation = elevation

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        rect = QtCore.QRectF(0, 0, painter.device().width(), painter.device().height())

        # Draw button background.
        brush = QtGui.QBrush()
        brush.setColor(QtGui.QColor('black'))
        brush.setStyle(QtCore.Qt.SolidPattern)

        painter.fillRect(rect, brush)

        # Draw button icon.
        self.icon_renderer.render(painter, rect)

class Parts(QtWidgets.QMainWindow):
    def __init__(self, labels, bench_display):
        super().__init__(bench_display)

        self.bench_display = bench_display

        self.setWindowFlags(QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        self.checkboxes = []

        layout = QtGui.QVBoxLayout()
        for label in labels:
            checkbox = QtGui.QCheckBox(label, self)
            checkbox.setChecked(label in self.bench_display.active_layers)
            checkbox.stateChanged.connect(functools.partial(self.state_changed, label))
            layout.addWidget(checkbox)

        self.widget = QtWidgets.QWidget()
        self.widget.setLayout(layout)
        self.setCentralWidget(self.widget)
        self.setWindowTitle('Bench tools')

    def state_changed(self, label, state):
        if state:
            self.bench_display.active_layers.append(label)
        else:
            self.bench_display.active_layers.remove(label)

        self.bench_display.update()

class BenchDisplay(QtGui.QWidget):
    def __init__(self, testbed):
        super().__init__()

        self.testbed = testbed

        schematic_fname = 'assets/hicat_schematic.svg'

        # Parse svg schematic for layer names to id conversion.
        self.layer_ids = {}
        doc = minidom.parse(schematic_fname)

        for e in doc.getElementsByTagName('g'):
            if e.getAttribute('inkscape:groupmode') == 'layer':
                key = e.getAttribute('inkscape:label')
                value = e.getAttribute('id')

                self.layer_ids[key] = value

        print(self.layer_ids)

        # Load in svg schematic.
        self.svg_renderer = QtSvg.QSvgRenderer(schematic_fname)
        self.active_layers = ['Background', 'Outline', 'Light pre-beam-dump', 'Light coronagraphic', 'Optical elements', 'DMs', 'Cameras']#, 'Buttons']

        with open('assets/button_info.yml') as f:
            self.button_infos = yaml.safe_load(f.read())

        self.buttons = []
        for info in self.button_infos:
            button = IconButton(info['icon'], info['relative_position'], info['tooltip'], self)

            if not hasattr(self, 'open_' + info['opens']):
                raise ValueError(f'Viewer {info["opens"]} is not known.')
            button.clicked.connect(functools.partial(getattr(self, 'open_' + info['opens']), info['device_name']))
            button.clicked.connect(self.start_tools)

            self.buttons.append(button)

        self.schematic_size = self.svg_renderer.boundsOnElement(self.layer_ids['Outline'])

    def open_camera_viewer(self, device_name, event):
        print('Opening camera viewer for', device_name)

        cam = getattr(self.testbed, device_name)
        viewer = CameraViewer(cam, self)
        viewer.show()

    def open_environment_viewer(self, device_name, event):
        print('Opening environment viewer for', device_name)

    def open_stage_viewer(self, device_name, event):
        print('Opening stage viewer for', device_name)

    def open_dm_viewer(self, device_name, event):
        print('Opening DM viewer for', device_name)

    def open_light_source_viewer(self, device_name, event):
        print('Opening light source viewer for', device_name)

    def start_tools(self, e):
        self.tool = Parts(list(self.layer_ids.keys()), self)
        self.tool.show()

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QtGui.QPainter(self)
        scaling = min(painter.device().width() / self.schematic_size.width(), painter.device().height() / self.schematic_size.height())

        for layer_name in self.active_layers:
            layer_id = self.layer_ids[layer_name]

            bounding_rect = self.svg_renderer.boundsOnElement(layer_id)
            this_rect = QtCore.QRectF(bounding_rect.x() * scaling, bounding_rect.y() * scaling, bounding_rect.width() * scaling, bounding_rect.height() * scaling)

            self.svg_renderer.render(painter, layer_id, this_rect)

    def resizeEvent(self, event):
        super().resizeEvent(event)

        scaling = min(self.width() / self.schematic_size.width(), self.height() / self.schematic_size.height())

        # Set positions and sizes of buttons.
        for button in self.buttons:
            pos = button.relative_position
            button.move(pos[0] * self.schematic_size.width() * scaling, pos[1] * self.schematic_size.height() * scaling)
            button.resize(scaling * 35, scaling * 35)
