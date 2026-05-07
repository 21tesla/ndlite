from PyQt6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QHBoxLayout, QCheckBox, QLabel, QPushButton, QColorDialog
from PyQt6.QtGui import QColor, QFont
import os

from PyQt6.QtWidgets import QGroupBox
from PyQt6.QtCore import Qt

class DataListWidget(QGroupBox):

    def __init__(self, parent=None):
        super().__init__("Data", parent)
        self.init_ui()

#---------------------------------------------------------------------------------------

    def init_ui(self):
        v_file = QVBoxLayout()
        self.file_scroll = QScrollArea()
        self.file_scroll.setWidgetResizable(True)
        self.file_scroll.setMaximumHeight(150)
        self.file_container = QWidget()
        self.file_layout = QVBoxLayout(self.file_container)
        self.file_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.file_layout.setContentsMargins(2, 2, 2, 2)
        self.file_layout.setSpacing(4)
        self.file_scroll.setWidget(self.file_container)
        v_file.addWidget(self.file_scroll)
        self.setLayout(v_file)

#---------------------------------------------------------------------------------------

    def clear(self):
        for i in reversed(range(self.file_layout.count())):
            widget = self.file_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

#---------------------------------------------------------------------------------------

    def add_spectrum(self, model, toggle_callback, color_callback):
        row_widget = QWidget()
        row_widget.setMaximumHeight(18)
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        chk_box = QCheckBox()
        chk_box.setChecked(model.enabled)
        chk_box.stateChanged.connect(lambda state: toggle_callback(bool(state)))

        lbl = QLabel(os.path.basename(model.file_path))
        small_font = QFont()
        small_font.setPointSize(9)
        lbl.setFont(small_font)

        btn_pos = QPushButton()
        btn_pos.setFixedSize(14, 14)
        btn_pos.setToolTip("Positive / 1D Trace Color")
        btn_pos.setStyleSheet(f"background-color: {model.color_pos}; border: 1px solid #aaa;")

        btn_neg = QPushButton()
        btn_neg.setFixedSize(14, 14)
        btn_neg.setToolTip("Negative Contour Color")
        btn_neg.setStyleSheet(f"background-color: {model.color_neg}; border: 1px solid #aaa;")

        def make_color_callback(is_pos, btn):
            def callback():
                curr_color = model.color_pos if is_pos else model.color_neg
                color = QColorDialog.getColor(initial=QColor(curr_color), parent=self, title="Select Color")
                if color.isValid():
                    hex_color = color.name()
                    if is_pos:
                        model.color_pos = hex_color
                    else:
                        model.color_neg = hex_color
                    btn.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #aaa;")
                    color_callback()
            return callback

        btn_pos.clicked.connect(make_color_callback(True, btn_pos))
        btn_neg.clicked.connect(make_color_callback(False, btn_neg))

        row_layout.addWidget(chk_box)
        row_layout.addWidget(lbl)
        row_layout.addStretch()
        row_layout.addWidget(btn_pos)
        if model.is_1d:
            btn_neg.hide()
        else:
            row_layout.addWidget(btn_neg)

        self.file_layout.addWidget(row_widget)
