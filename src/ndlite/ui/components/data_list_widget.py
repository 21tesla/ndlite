from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, 
                             QLabel, QPushButton, QColorDialog, QGroupBox, 
                             QListWidget, QListWidgetItem, QMenu)
from PyQt6.QtGui import QColor, QFont, QCursor
from PyQt6.QtCore import Qt, pyqtSignal
import os

class DataListWidget(QGroupBox):
    remove_requested = pyqtSignal(int)
    selection_changed = pyqtSignal(int)
    peak_toggle_requested = pyqtSignal(int, bool)

    def __init__(self, parent=None):
        super().__init__("Data / Peaks", parent)
        self.init_ui()

#---------------------------------------------------------------------------------------

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        self.list_widget = QListWidget()
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        self.list_widget.currentRowChanged.connect(self.selection_changed.emit)
        self.list_widget.setMaximumHeight(150)
        
        # Style the list widget for a compact look
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                background-color: #f9f9f9;
            }
            QListWidget::item {
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #e0e0ff;
                color: black;
            }
        """)
        
        layout.addWidget(self.list_widget)
        self.setLayout(layout)

#---------------------------------------------------------------------------------------

    def clear(self):
        self.list_widget.clear()

#---------------------------------------------------------------------------------------

    def show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if item:
            index = self.list_widget.row(item)
            menu = QMenu(self)
            delete_action = menu.addAction("Delete Spectrum")
            
            action = menu.exec(self.list_widget.mapToGlobal(pos))
            if action == delete_action:
                self.remove_requested.emit(index)

#---------------------------------------------------------------------------------------

    def add_spectrum(self, model, toggle_callback, color_callback, peak_toggle_callback=None):
        item = QListWidgetItem(self.list_widget)
        
        row_widget = QWidget()
        row_widget.setMaximumHeight(24) 
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(4, 2, 4, 2)
        row_layout.setSpacing(8)

        # 1. Spectrum Visibility Checkbox
        chk_vis = QCheckBox()
        chk_vis.setToolTip("Toggle Spectrum Visibility")
        chk_vis.setChecked(model.enabled)
        chk_vis.stateChanged.connect(lambda state: toggle_callback(bool(state)))

        # 2. Peak Visibility Checkbox
        chk_peaks = QCheckBox()
        chk_peaks.setToolTip("Toggle Peak Visibility")
        # Ensure model has peaks_enabled or default to True
        peaks_enabled = getattr(model, 'peaks_enabled', True)
        chk_peaks.setChecked(peaks_enabled)
        if peak_toggle_callback:
            chk_peaks.stateChanged.connect(lambda state: peak_toggle_callback(bool(state)))

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

        row_layout.addWidget(chk_vis)
        row_layout.addWidget(chk_peaks) # Added second checkbox
        row_layout.addWidget(lbl)
        row_layout.addStretch()
        row_layout.addWidget(btn_pos)
        if model.is_1d:
            btn_neg.hide()
        else:
            row_layout.addWidget(btn_neg)

        item.setSizeHint(row_widget.sizeHint())
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, row_widget)
