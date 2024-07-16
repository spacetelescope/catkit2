from PyQt5 import QtCore, QtWidgets, QtGui


class Toggle(QtWidgets.QCheckBox):
    _transparent_pen = QtGui.QPen(QtCore.Qt.transparent)

    def __init__(self, parent=None, unchecked_color=QtCore.Qt.lightGray, checked_color='#007ACC', handle_color=QtCore.Qt.white):
        super().__init__(parent)

        self._bar_unchecked_brush = QtGui.QBrush(QtGui.QColor(unchecked_color).darker(150))
        self._bar_checked_brush = QtGui.QBrush(QtGui.QColor(checked_color).darker(150))

        self._handle_unchecked_brush = QtGui.QBrush(QtGui.QColor(unchecked_color).lighter(150))
        self._handle_checked_brush = QtGui.QBrush(QtGui.QColor(checked_color).lighter(150))

        self._handle_position = 0

        self.stateChanged.connect(self.handle_state_change)

        self.setFixedSize(40, 25)

        self.animation = QtCore.QPropertyAnimation(self, b"handle_position", self)
        self.animation.setEasingCurve(QtCore.QEasingCurve.InOutCubic)
        self.animation.setDuration(200)

    @QtCore.pyqtSlot(int)
    def handle_state_change(self, value):
        self.animation.stop()
        if value:
            self.animation.setEndValue(1)
        else:
            self.animation.setEndValue(0)
        self.animation.start()

    def sizeHint(self):
        return QtCore.QSize(40, 30)

    def hitButton(self, pos: QtCore.QPoint):
        return self.bar_rect().contains(pos)

    def bar_rect(self):
        content_rect = self.contentsRect()
        bar_rect = QtCore.QRectF(
            0, 0,
            0.75 * content_rect.width(), 0.55 * content_rect.height()
        )
        bar_rect.moveCenter(content_rect.center())

        return bar_rect

    def paintEvent(self, e):
        handle_scale = 1

        bar_rect = self.bar_rect()

        p = QtGui.QPainter()
        p.begin(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)

        rounding = bar_rect.height() / 2
        handle_radius = 1.3 * rounding

        # The handle will move along this line.
        trailLength = bar_rect.width() - 2 * rounding
        xPos = bar_rect.x() + rounding + trailLength * self._handle_position

        p.setPen(self._transparent_pen)
        p.setBrush(self._bar_checked_brush if self.isChecked() else self._bar_unchecked_brush)
        p.drawRoundedRect(bar_rect, rounding, rounding)
        p.setBrush(self._handle_checked_brush if self.isChecked() else self._handle_unchecked_brush)

        p.drawEllipse(QtCore.QPointF(xPos, bar_rect.center().y()), handle_scale * handle_radius, handle_scale * handle_radius)

        p.end()

    @QtCore.pyqtProperty(float)
    def handle_position(self):
        return self._handle_position

    @handle_position.setter
    def handle_position(self, pos):
        self._handle_position = pos
        self.update()


if __name__ == '__main__':
    import qtvscodestyle as qtvsc
    from qtvscodestyle.base import _load_stylesheet, _RESOURCES_BASE_DIR

    class Window(QtWidgets.QMainWindow):
        def __init__(self):
            super().__init__()

            toggle = Toggle()

            container = QtWidgets.QWidget()
            layout = QtWidgets.QHBoxLayout()
            layout.addWidget(toggle)
            container.setLayout(layout)

            self.setCentralWidget(container)

    app = QtWidgets.QApplication([])
    app.setStyleSheet(_load_stylesheet(qtvsc.Theme.DARK_VS, {}, output_svg_path=_RESOURCES_BASE_DIR))

    w = Window()
    w.show()
    app.exec_()
