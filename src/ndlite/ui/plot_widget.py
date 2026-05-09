from PyQt6.QtGui import QMouseEvent
from PyQt6.QtCore import Qt
import pyqtgraph as pg

class TrackpadPlotWidget(pg.PlotWidget):

#---------------------------------------------------------------------        

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton and ev.modifiers() == Qt.KeyboardModifier.AltModifier:
            new_ev = QMouseEvent(
                ev.type(),
                ev.position(),
                ev.globalPosition(),
                Qt.MouseButton.MiddleButton,
                ev.buttons() | Qt.MouseButton.MiddleButton,
                ev.modifiers()
            )
            super().mousePressEvent(new_ev)
        else:
            super().mousePressEvent(ev)

#---------------------------------------------------------------------        

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton and ev.modifiers() == Qt.KeyboardModifier.AltModifier:
            new_ev = QMouseEvent(
                ev.type(),
                ev.position(),
                ev.globalPosition(),
                Qt.MouseButton.MiddleButton,
                ev.buttons() & ~Qt.MouseButton.LeftButton,
                ev.modifiers()
            )
            super().mouseReleaseEvent(new_ev)
        else:
            super().mouseReleaseEvent(ev)
