import sys
import os
import numpy as np
import nmrglue as ng
import json
import ssl
import certifi 
import urllib.request
from urllib.request import urlopen, Request
import webbrowser

from scipy.signal import hilbert
from scipy.optimize import curve_fit

import pyqtgraph.exporters 
import pyqtgraph as pg

from PyQt6.QtGui import QTransform, QColor, QFont, QMouseEvent, QAction, QPainterPath
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QGridLayout, QPushButton, QFileDialog,
                             QLabel, QSlider, QGroupBox, QDoubleSpinBox, QSpinBox,
                             QScrollArea, QColorDialog, QCheckBox, QMessageBox, QDialog,
                             QTableWidget, QTableWidgetItem, QHeaderView, QDialogButtonBox)

from PyQt6.QtCore import Qt, QTimer, qInstallMessageHandler, QtMsgType

from ui.plot_widget import TrackpadPlotWidget
from ui.dialogs import HelpDialog
from core.data_handler import DataHandler
from core.peak_manager import PeakManager

from ui.components.data_list_widget import DataListWidget
from ui.components.phase_control_widget import PhaseControlWidget
from ui.components.display_control_widget import DisplayControlWidget
from ui.components.menu_builder import MenuBuilder
from ui.controllers.fitting_controller import FittingController
from ui.controllers.baseline_controller import BaselineController
from ui.controllers.peak_controller import PeakController
from ui.controllers.io_controller import IOController
from ui.exporter import Exporter
from core.updater import Updater
from core.models.spectrum_model import SpectrumModel

#---------------------------------------------------------------------        


__version__ = "0.3.0"


#---------------------------------------------------------------------        

        
os.environ["LC_ALL"] = "en_US.UTF-8"
os.environ["LANG"] = "en_US.UTF-8"

pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
pg.setConfigOption('antialias', False)

GLOBAL_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


#---------------------------------------------------------------------        


class SettingsDialog(QDialog):
    def __init__(self, prefs, prefs_file, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.resize(400, 500)
        self.prefs = prefs
        self.prefs_file = prefs_file
        self.flat_prefs = self.flatten_dict(self.prefs)
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Setting", "Value"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        
        self.table.setRowCount(len(self.flat_prefs))
        
        for row, (key, value) in enumerate(self.flat_prefs.items()):
            # Setting Name (Read-only)
            key_item = QTableWidgetItem(key)
            key_item.setFlags(key_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, key_item)
            
            # Setting Value (Editable)
            val_item = QTableWidgetItem(str(value))
            # Store the original type so we can cast it back upon saving
            val_item.setData(Qt.ItemDataRole.UserRole, type(value).__name__)
            self.table.setItem(row, 1, val_item)
            
        layout.addWidget(self.table)
        
        # Save / Cancel Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.save_settings)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def flatten_dict(self, d, parent_key='', sep='.'):
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self.flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)

    def unflatten_dict(self, d, sep='.'):
        result_dict = dict()
        for k, v in d.items():
            parts = k.split(sep)
            d_ref = result_dict
            for part in parts[:-1]:
                if part not in d_ref:
                    d_ref[part] = dict()
                d_ref = d_ref[part]
            d_ref[parts[-1]] = v
        return result_dict

    def save_settings(self):
        updated_flat = {}
        try:
            for row in range(self.table.rowCount()):
                key = self.table.item(row, 0).text()
                val_item = self.table.item(row, 1)
                str_val = val_item.text()
                orig_type = val_item.data(Qt.ItemDataRole.UserRole)
                
                # Safely cast back to the original type
                if orig_type == 'int':
                    updated_flat[key] = int(str_val)
                elif orig_type == 'float':
                    updated_flat[key] = float(str_val)
                elif orig_type == 'bool':
                    updated_flat[key] = str_val.lower() in ('true', '1', 'yes')
                else:
                    updated_flat[key] = str_val
                    
            nested_prefs = self.unflatten_dict(updated_flat)
            
            with open(self.prefs_file, 'w') as f:
                json.dump(nested_prefs, f, indent=4)
                
            self.parent().prefs = nested_prefs
            self.accept()
            
            QMessageBox.information(self, "Settings Saved", "Preferences saved successfully.\n\nPlease restart the application for UI changes to fully take effect.")
            
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Input", f"Could not save settings due to a type conversion error:\n{e}\n\nPlease ensure numbers remain as numbers.")
            
            

class NMRViewerApp(QMainWindow):
    def __init__(self, file_paths=None):
        super().__init__()
        self.setWindowTitle("NMRdraw_lite")
        self.resize(1400, 1000)

        self.dic_list = []
        self.raw_data_list = []
        self.current_slice_list = []
        self.spectrum_colors = []
        self.file_enabled_flags = []
        self.enabled_indices = []

        self.dic = None
        self.raw_data = None
        self.current_slice = None

        self.nz, self.nx, self.ny = 1, 1, 1
        self.x_dim, self.y_dim, self.z_dim = 1, 0, None
        self.slice_x_idx = 1
        self.ppm_x, self.ppm_y, self.ppm_z = None, None, None
        self.lim_x, self.lim_y, self.lim_z = None, None, None
        self.label_x, self.label_y, self.label_z = "X", "Y", "Z"

        self.h_pos = 0.0
        self.v_pos = 0.0

        # Optimization: Object pooling arrays
        self.file_groups = []
        self.file_pools_2d = []
        self.file_curves_1d = []
        
        self.current_mode = None
        self.active_axis = 'x'
        self.phase_state = {
            'x': {'p0': 0.0, 'p1': 0.0},
            'y': {'p0': 0.0, 'p1': 0.0},
            'z': {'p0': 0.0, 'p1': 0.0}
        }
        self.phase_ui = {}
        self.cont_sliders = {}
        self.cont_widgets = {}

        self.io_controller = IOController(self)
        self.io_controller.load_preferences()

        self.peak_manager = PeakManager()
        self.exporter = Exporter(self)
        self.updater = Updater(self)
        self.fitting_controller = FittingController(self)
        self.baseline_controller = BaselineController(self)
        self.peak_controller = PeakController(self)
        self.data_handler = DataHandler()

        self.init_ui()
        self.menu_builder = MenuBuilder(self)
        self.menu_builder.build()
        
        if file_paths:
            self.io_controller.load_files(file_paths)
 
        QTimer.singleShot(2000, self.updater.silent_update_check)       
        
        
#---------------------------------------------------------------------        

    def show_help_dialog(self):
        dlg = HelpDialog(self)

        dlg.exec()

#---------------------------------------------------------------------        

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        top_panel = QWidget()
        top_layout = QHBoxLayout(top_panel)

        # Data List
        v_file = QVBoxLayout()
        self.data_list_widget = DataListWidget()
        v_file.addWidget(self.data_list_widget)

        # Z-Plane Controls
        self.z_container = QWidget()
        h_z = QHBoxLayout(self.z_container)
        h_z.setContentsMargins(0, 0, 0, 0)
        
        self.lbl_z = QLabel("Z-Plane:")
        self.lbl_z.setMinimumWidth(120)
        
        self.slider_z = QSlider(Qt.Orientation.Horizontal)
        self.spinbox_z = QSpinBox()
        self.spinbox_z.setMinimumWidth(80)

        def z_sl_changed(val):
            self.spinbox_z.blockSignals(True)
            self.spinbox_z.setValue(val)
            self.spinbox_z.blockSignals(False)
            self._update_z_label()

        def z_sb_changed(val):
            self.slider_z.blockSignals(True)
            self.slider_z.setValue(val)
            self.slider_z.blockSignals(False)
            self._update_z_label()
            self._update_enabled_state()
            self.recompute_contours()
            self.peak_controller.update_peak_markers()

        def z_sl_released():
            self._update_enabled_state()
            self.recompute_contours()
            self.peak_controller.update_peak_markers()

        self.slider_z.valueChanged.connect(z_sl_changed)
        self.spinbox_z.valueChanged.connect(z_sb_changed)
        self.slider_z.sliderReleased.connect(z_sl_released)

        h_z.addWidget(self.lbl_z)
        h_z.addWidget(self.slider_z)
        h_z.addWidget(self.spinbox_z)
        
        self.z_container.hide()
        v_file.addWidget(self.z_container)

        # --- NEW: 1D Baseline Threshold Controls ---
        self.baseline_1d_container = QWidget()
        h_b1d = QHBoxLayout(self.baseline_1d_container)
        h_b1d.setContentsMargins(0, 0, 0, 0)
        
        self.lbl_b1d = QLabel("1D Baseline:")
        self.lbl_b1d.setMinimumWidth(120)
        
        # Load from prefs
        b1d_prefs = self.prefs["baseline_1d"]
        b1d_min = b1d_prefs["min"]
        b1d_max = b1d_prefs["max"]
        b1d_def = b1d_prefs["default"]
        b1d_step = b1d_prefs["step"]
        
        self.slider_1d_base = QSlider(Qt.Orientation.Horizontal)
        self.slider_1d_base.setMinimum(int(b1d_min * 100)) 
        self.slider_1d_base.setMaximum(int(b1d_max * 100))  
        self.slider_1d_base.setValue(int(b1d_def * 100))     
        
        self.spinbox_1d_base = QDoubleSpinBox()
        self.spinbox_1d_base.setRange(b1d_min, b1d_max)
        self.spinbox_1d_base.setSingleStep(b1d_step)
        self.spinbox_1d_base.setDecimals(2)
        self.spinbox_1d_base.setValue(b1d_def)
        self.spinbox_1d_base.setMinimumWidth(80)
        self.spinbox_1d_base.setKeyboardTracking(False)
        
        def b1d_sl_changed(val):
            self.spinbox_1d_base.blockSignals(True)
            try:
                self.spinbox_1d_base.setValue(round(val / 100.0, 2))
            finally:
                self.spinbox_1d_base.blockSignals(False)

        def b1d_sb_changed(val):
            self.slider_1d_base.blockSignals(True)
            try:
                self.slider_1d_base.setValue(int(round(val * 100)))
            finally:
                self.slider_1d_base.blockSignals(False)
            self.recompute_contours()

        self.slider_1d_base.valueChanged.connect(b1d_sl_changed)
        self.spinbox_1d_base.valueChanged.connect(b1d_sb_changed)
        self.slider_1d_base.sliderReleased.connect(self.recompute_contours)

        h_b1d.addWidget(self.lbl_b1d)
        h_b1d.addWidget(self.slider_1d_base)
        h_b1d.addWidget(self.spinbox_1d_base)
        
        self.baseline_1d_container.hide()
        v_file.addWidget(self.baseline_1d_container)
        # -----------------------------------------

        grp_file = QWidget()
        grp_file.setLayout(v_file)
        top_layout.addWidget(grp_file)
        self.grp_phase = QGroupBox("Phase Correction")
        self.grp_phase.setEnabled(False)
        grid_phase = QGridLayout()

        params = [
            ("p0", "P0 Phase", -180, 180, 0.1),
            ("p1", "P1 Phase", -360, 360, 0.1)
        ]
        for row, (key, label, vmin, vmax, step) in enumerate(params):
            lbl = QLabel(label)
            sl = QSlider(Qt.Orientation.Horizontal)
            sl.setMinimum(int(vmin * 10))
            sl.setMaximum(int(vmax * 10))
            sl.setValue(0)
            sb = QDoubleSpinBox()
            sb.setRange(vmin, vmax)
            sb.setSingleStep(step)
            sb.setDecimals(1)
            sb.setValue(0.0)
            sb.setMinimumWidth(80)

            def make_connections(k, slider, spinbox):
                spinbox.setKeyboardTracking(False)
                
                def sl_changed(val):
                    spinbox.blockSignals(True)
                    try:
                        # Safely round back to exact float
                        spinbox.setValue(round(val / 10.0, 1))
                    finally:
                        spinbox.blockSignals(False)
                    self.on_phase_changed(k, val / 10.0)

                def sb_changed(val):
                    slider.blockSignals(True)
                    try:
                        # Safely round to int to prevent desync
                        slider.setValue(int(round(val * 10)))
                    finally:
                        slider.blockSignals(False)
                    self.on_phase_changed(k, val)
                    self.recompute_contours()

                slider.valueChanged.connect(sl_changed)
                spinbox.valueChanged.connect(sb_changed)
                slider.sliderReleased.connect(self.recompute_contours)
            make_connections(key, sl, sb)

            grid_phase.addWidget(lbl, row, 0)
            grid_phase.addWidget(sl, row, 1)
            grid_phase.addWidget(sb, row, 2)
            self.phase_ui[key] = (sl, sb)
                        
        self.grp_phase.setLayout(grid_phase)
        top_layout.addWidget(self.grp_phase)

        grp_cont = QGroupBox("Display Controls")
        grid_cont = QGridLayout()

        # Load from prefs
        c_prefs = self.prefs["controls"]
        
        cont_params = [
            ("base", c_prefs["base"]["label"], c_prefs["base"]["min"], c_prefs["base"]["max"], c_prefs["base"]["default"], c_prefs["base"]["is_int"]),
            ("scale", c_prefs["scale"]["label"], c_prefs["scale"]["min"], c_prefs["scale"]["max"], c_prefs["scale"]["default"], c_prefs["scale"]["is_int"]),
            ("count", c_prefs["count"]["label"], c_prefs["count"]["min"], c_prefs["count"]["max"], c_prefs["count"]["default"], c_prefs["count"]["is_int"]),
            ("offset", c_prefs["offset"]["label"], c_prefs["offset"]["min"], c_prefs["offset"]["max"], c_prefs["offset"]["default"], c_prefs["offset"]["is_int"])
            ]
        
        for row, (key, label, vmin, vmax, vdef, is_int) in enumerate(cont_params):
            lbl = QLabel(label)
            sl = QSlider(Qt.Orientation.Horizontal)

            if is_int:
                sl.setMinimum(int(vmin))
                sl.setMaximum(int(vmax))
                sl.setValue(int(vdef))
                sb = QSpinBox()
                sb.setRange(int(vmin), int(vmax))
                sb.setSingleStep(1)
                sb.setValue(int(vdef))
                sb.setMinimumWidth(80)

                def make_conn_int(k, slider, spinbox):
                    spinbox.setKeyboardTracking(False)
                    
                    def sl_changed(val):
                        spinbox.blockSignals(True)
                        spinbox.setValue(val)
                        spinbox.blockSignals(False)

                    def sb_changed(val):
                        slider.blockSignals(True)
                        slider.setValue(val)
                        slider.blockSignals(False)
                        self.recompute_contours()

                    slider.valueChanged.connect(sl_changed)
                    spinbox.valueChanged.connect(sb_changed)
                    slider.sliderReleased.connect(self.recompute_contours)
                make_conn_int(key, sl, sb)
            else:
                sl.setMinimum(int(vmin * 100))
                sl.setMaximum(int(vmax * 100))
                sl.setValue(int(vdef * 100))
                sb = QDoubleSpinBox()
                sb.setRange(vmin, vmax)
                sb.setSingleStep(0.1)
                sb.setDecimals(2)
                sb.setValue(vdef)
                sb.setMinimumWidth(80)

                def make_conn_float(k, slider, spinbox):
                    spinbox.setKeyboardTracking(False)
                    
                    def sl_changed(val):
                        spinbox.blockSignals(True)
                        try:
                            # Safely round back to the exact double value
                            spinbox.setValue(round(val / 100.0, 2))
                        finally:
                            spinbox.blockSignals(False)

                    def sb_changed(val):
                        slider.blockSignals(True)
                        try:
                            # Safely round to int to prevent truncation desync at bounds
                            slider.setValue(int(round(val * 100)))
                        finally:
                            slider.blockSignals(False)
                        self.recompute_contours()

                    slider.valueChanged.connect(sl_changed)
                    spinbox.valueChanged.connect(sb_changed)
                    slider.sliderReleased.connect(self.recompute_contours)
                make_conn_float(key, sl, sb)
                
                
            grid_cont.addWidget(lbl, row, 0)
            grid_cont.addWidget(sl, row, 1)
            grid_cont.addWidget(sb, row, 2)
            self.cont_sliders[key] = sb
            self.cont_widgets[key] = (lbl, sl, sb)
        grp_cont.setLayout(grid_cont)
        top_layout.addWidget(grp_cont)

        main_layout.addWidget(top_panel, stretch=0)

        self.plot_2d = TrackpadPlotWidget(title="Please load a file.")
        self.plot_2d.setLabel('bottom', "X-Axis", units="ppm")
        self.plot_2d.setLabel('left', "Y-Axis", units="ppm")
        self.plot_2d.getViewBox().invertY(True)
        self.plot_2d.getViewBox().invertX(True)
        self.plot_2d.getViewBox().sigRangeChanged.connect(self.update_live_trace)
        self.plot_2d.scene().sigMouseMoved.connect(self.on_mouse_moved)
        self.plot_2d.scene().sigMouseClicked.connect(self.on_mouse_clicked)

        # Optimization: Width=1 for fast, cosmetic rendering
        self.hline = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('g', width=2))
        self.vline = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('g', width=2))
        # --- NEW: Visual indicator for the 1D Auto-Pick noise floor ---
        self.threshold_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('r', style=Qt.PenStyle.DashLine, width=1))
        
        self.trace_curve = pg.PlotDataItem(pen=pg.mkPen(color='#DAA520', width=2))
        
        self.plot_2d.addItem(self.hline)
        self.plot_2d.addItem(self.vline)
        self.plot_2d.addItem(self.threshold_line) # Add to plot
        self.plot_2d.addItem(self.trace_curve)

        self.peaks_scatter = pg.ScatterPlotItem(size=10, pen=pg.mkPen('k'), brush=pg.mkBrush(255, 0, 0, 150))
        self.plot_2d.addItem(self.peaks_scatter)
        self.peak_text_items = {}
        
        self.hline.setVisible(False)
        self.vline.setVisible(False)
        self.threshold_line.setVisible(False) # Hide by default
        self.trace_curve.setVisible(False)
        
        main_layout.addWidget(self.plot_2d, stretch=1)

#---------------------------------------------------------------------        

    def _update_z_label(self):
        if not self.raw_data_list or self.nz <= 1:
            return
        z_idx = self.slider_z.value() - 1
        z_ppm = self.ppm_z[z_idx] if hasattr(self, 'ppm_z') and self.ppm_z is not None else z_idx
        self.lbl_z.setText(f"{self.label_z or 'Z-Plane'}: {z_ppm:.2f} ppm")

#---------------------------------------------------------------------        

    def set_mode(self, mode):
        if self.raw_data is not None and self.raw_data.ndim == 2 and mode == 'z_phase':
            return

        if mode in ['peak_pick', 'peak_delete']:
            if self.raw_data is None or self.raw_data.ndim < 2: # Changed from != 2 to < 2
                QMessageBox.information(self, "Feature in Progress", f"Peak picking is currently only supported for 2D and 3D spectra.")
                mode = None 
         
        self.current_mode = mode
            
        if mode == 'x_phase':
            self.active_axis = 'x'
            self.grp_phase.setEnabled(True)
            self.update_phase_ui_from_state()
            if self.raw_data is not None and self.raw_data.ndim == 1:
                self.hline.setVisible(False)
                self.vline.setVisible(False)
                self.trace_curve.setVisible(False)
                self.plot_2d.setTitle("Phasing 1D Spectrum. Press Esc to exit.")
            else:
                self.hline.setVisible(True)
                self.vline.setVisible(True)
                self.trace_curve.setVisible(True)
                self.plot_2d.setTitle("Phasing X-Axis. Press Esc to exit.")
                self.update_live_trace()
        elif mode == 'y_phase':
            self.active_axis = 'y'
            self.grp_phase.setEnabled(True)
            self.update_phase_ui_from_state()
            self.hline.setVisible(True)
            self.vline.setVisible(True)
            self.trace_curve.setVisible(True)
            self.plot_2d.setTitle("Phasing Y-Axis. Press Esc to exit.")
            self.update_live_trace()
        elif mode == 'z_phase':
            if self.nz == 1:
                self.plot_2d.setTitle("No Z-Axis found in dataset.")
                self.current_mode = None
                return
            self.active_axis = 'z'
            self.grp_phase.setEnabled(True)
            self.update_phase_ui_from_state()
            self.hline.setVisible(True)
            self.vline.setVisible(True)
            self.trace_curve.setVisible(True)
            self.plot_2d.setTitle("Phasing Z-Axis. Press Esc to exit.")
            self.update_live_trace()
        elif mode == 'peak_pick':
            self.active_axis = None
            self.grp_phase.setEnabled(False)
            self.hline.setVisible(True)
            self.vline.setVisible(True)
            self.plot_2d.setTitle("Peak Picking Mode. Click near a peak to refine. Press Esc to exit.")
        elif mode == 'peak_delete':
            self.active_axis = None
            self.grp_phase.setEnabled(False)
            self.hline.setVisible(True)
            self.vline.setVisible(True)
            self.plot_2d.setTitle("Delete Mode: Click near a peak to remove it. Press Esc to exit.")
        elif mode == 'baseline_interactive':
            self.active_axis = None
            self.grp_phase.setEnabled(False)
            self.hline.setVisible(False)
            self.vline.setVisible(False)
            self.plot_2d.setTitle("Baseline Mode: Click noise floor to add anchors. Press 'Enter' to apply fit, 'Esc' to cancel.")

        elif mode is None:
            self.grp_phase.setEnabled(False)
            self.grp_phase.setTitle("Phase Correction")
            self.trace_curve.setVisible(False)
            if self.raw_data is not None:
                if self.raw_data.ndim == 1:
                    self.hline.setVisible(False)
                    self.vline.setVisible(False)
                    self.plot_2d.setTitle("1D Mode. Press 'x' to phase. | 'h' for help")
                else:
                    self.hline.setVisible(True)
                    self.vline.setVisible(True)
                    if self.raw_data.ndim == 2:
                        self.plot_2d.setTitle(f"{self.label_x}={self.v_pos:.3f}, {self.label_y}={self.h_pos:.3f} | Press 'x' or 'y' to phase. | 'h' for help")
                    else:
                        self.plot_2d.setTitle(f"{self.label_x}={self.v_pos:.3f}, {self.label_y}={self.h_pos:.3f} | Press 'x', 'y', 'z' to phase. | 'h' for help")
            else:
                self.hline.setVisible(False)
                self.vline.setVisible(False)
                self.plot_2d.setTitle("Please load a file.")

#---------------------------------------------------------------------        
                
    def on_mouse_moved(self, pos):
        # Freeze crosshair updates while the export dialog is active
        if getattr(self, 'is_exporting', False):
            return
            
        if (self.current_mode is not None and self.current_mode not in ['peak_pick', 'peak_delete']) or self.raw_data is None:
            return
            
        if self.raw_data.ndim == 1 and self.current_mode not in ['peak_pick', 'peak_delete']:
            return
            
        view_box = self.plot_2d.getViewBox()
        if view_box.sceneBoundingRect().contains(pos):
            mouse_point = view_box.mapSceneToView(pos)
            self.h_pos = mouse_point.y()
            self.v_pos = mouse_point.x()
            self.hline.setPos(self.h_pos)
            self.vline.setPos(self.v_pos)
            
            self.hline.setVisible(self.raw_data.ndim > 1)
            self.vline.setVisible(True)
            
            if self.current_mode == 'peak_pick':
                if self.raw_data.ndim == 1:
                    self.plot_2d.setTitle(f"Peak Pick: {self.label_x}={self.v_pos:.3f} | Shift-Click or Shift-P to force pick")
                else:
                    self.plot_2d.setTitle(f"Peak Pick: {self.label_x}={self.v_pos:.3f}, {self.label_y}={self.h_pos:.3f} | Shift-Click or Shift-P to force")
            elif self.current_mode == 'peak_delete':
                if self.raw_data.ndim == 1:
                    self.plot_2d.setTitle(f"Peak Delete: {self.label_x}={self.v_pos:.3f} | Click to delete")
                else:
                    self.plot_2d.setTitle(f"Peak Delete: {self.label_x}={self.v_pos:.3f}, {self.label_y}={self.h_pos:.3f} | Click to delete")
            elif self.raw_data.ndim == 2:
                self.plot_2d.setTitle(f"{self.label_x}={self.v_pos:.3f}, {self.label_y}={self.h_pos:.3f} | Press 'x' or 'y' to phase. | 'h' for help")
            elif self.raw_data.ndim >= 3:
                self.plot_2d.setTitle(f"{self.label_x}={self.v_pos:.3f}, {self.label_y}={self.h_pos:.3f} | Press 'x', 'y', 'z' to phase. | 'h' for help")
        else:
            self.hline.setVisible(False)
            self.vline.setVisible(False)
            self.plot_2d.setTitle(" ")

#---------------------------------------------------------------------        

    def on_mouse_clicked(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.hline.setVisible(False)
            self.vline.setVisible(False)
            self.trace_curve.setVisible(False)
            self.plot_2d.setTitle(" ")
            
        elif event.button() == Qt.MouseButton.LeftButton:
            if self.current_mode in ['peak_pick', 'peak_delete', 'baseline_interactive']:
                
                view_box = self.plot_2d.getViewBox()
                mouse_point = view_box.mapSceneToView(event.scenePos())
                click_ppm_x = mouse_point.x()
                click_ppm_y = mouse_point.y()
                
                if self.current_mode == 'peak_pick':
                    current_z_idx = self.slider_z.value() - 1 if hasattr(self, 'nz') and self.nz > 1 else None
                    current_ppm_z = self.ppm_z[current_z_idx] if hasattr(self, 'nz') and self.nz > 1 else None

                    if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                        self.peak_manager.add_force_peak(click_ppm_x, click_ppm_y, ppm_z=current_ppm_z, closest_z_idx=current_z_idx)
                        self.peak_controller.update_peak_markers()
                    else:
                        if self.enabled_indices and hasattr(self, 'vis_data_dict'):
                            orig_i = self.enabled_indices[0]
                            vis_data = self.vis_data_dict.get(orig_i)

                            base_mult = self.cont_sliders['base'].value()
                            noise_rmsd = self.data_handler.calculate_rmsd(vis_data)
                            threshold = noise_rmsd * base_mult

                            data_to_pass = self.raw_data if self.raw_data.ndim == 3 else vis_data

                            self.peak_manager.refine_peak(
                                click_ppm_x, click_ppm_y, 
                                data_to_pass, self.ppm_x, self.ppm_y, threshold,
                                click_z_idx=current_z_idx, ppm_z=getattr(self, 'ppm_z', None)
                            )
                            self.peak_controller.update_peak_markers()

                elif self.current_mode == 'peak_delete':
                    x_range, y_range = view_box.viewRange()
                    dx_scale = max(abs(x_range[1] - x_range[0]), 1e-6)
                    dy_scale = max(abs(y_range[1] - y_range[0]), 1e-6)
                            
                    self.peak_manager.delete_nearest_peak(click_ppm_x, click_ppm_y, dx_scale, dy_scale)
                    self.peak_controller.update_peak_markers()
                    
                elif self.current_mode == 'baseline_interactive':
                    orig_i = self.enabled_indices[0]
                    vis_data = self.vis_data_dict.get(orig_i)
                    x_idx = np.argmin(np.abs(self.ppm_x - click_ppm_x))
                    true_y = vis_data[x_idx]
                    
                    self.baseline_anchors.append((self.ppm_x[x_idx], true_y))
                    self.baseline_scatter.setData([{'pos': (pt[0], pt[1])} for pt in self.baseline_anchors])
                    
                                                    
#---------------------------------------------------------------------        
                                    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.set_mode(None)
            return
            
        # Add Shift-R for sequential renumbering
        if event.key() == Qt.Key.Key_R and (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.peak_controller.renumber_peaks()
            return
            
        if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            if self.current_mode == 'baseline_interactive':
                if len(self.baseline_anchors) < 3:
                    self.plot_2d.setTitle("Error: Please select at least 3 anchor points.")
                    return
                
                # Unpack anchors and sort by ppm
                self.baseline_anchors.sort(key=lambda pt: pt[0])
                x_pts, y_pts = zip(*self.baseline_anchors)
                
                # Fit a cubic polynomial (degree 3) through the anchor points
                poly_coeffs = np.polyfit(x_pts, y_pts, 3)
                poly_func = np.poly1d(poly_coeffs)
                
                # Generate the full baseline curve
                baseline = poly_func(self.ppm_x)
                orig_i = self.enabled_indices[0]
                
                # Store it non-destructively
                self.baseline_corrections[orig_i] = baseline
                
                self.baseline_scatter.setVisible(False)
                self.baseline_anchors.clear()
                self.set_mode(None)
                self.recompute_contours()
                self.plot_2d.setTitle("Success: Interactive Polynomial Baseline applied.")
            return            
            
        text = event.text().lower()
        ndim = self.raw_data.ndim if self.raw_data is not None else 0

        if text == 'd':
            self.set_mode('peak_delete')
            return

        if text == 'h':
            self.show_help_dialog()
            return

        if text == 's':
            self.peak_controller.save_peaks()
            return

        if text == 'p':
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                if self.raw_data is not None:
                    if self.current_mode != 'peak_pick':
                        self.set_mode('peak_pick')
                    
                    # Delegate to manager
                    self.peak_manager.add_force_peak(self.v_pos, self.h_pos)
                    self.peak_controller.update_peak_markers()
            else:
                self.set_mode('peak_pick')
            return
            
                                    
        if ndim == 1:
            if text == 'x':
                self.set_mode('x_phase')
        elif ndim == 2:
            if text == 'x':
                self.set_mode('x_phase')
            elif text == 'y':
                self.set_mode('y_phase')
        elif ndim >= 3 and self.nz > 1:
            if text == 'x':
                self.set_mode('x_phase')
            elif text == 'y':
                self.set_mode('y_phase')
            elif text == 'z':
                self.set_mode('z_phase')
                

#---------------------------------------------------------------------        
                            
    def _update_enabled_state(self):
        if not self.raw_data_list:
            return
            
        self.current_slice_list = []
        self.enabled_indices = []
        
        for i in range(len(self.raw_data_list)):
            if self.file_enabled_flags[i]:
                self.enabled_indices.append(i)
                data = self.raw_data_list[i]
                
                if self.nz > 1 and data.ndim == 3:
                    z_idx = (self.slider_z.value() - 1) if hasattr(self, 'slider_z') and self.nz > 1 else 0
                    slices = [slice(None)] * 3
                    slices[self.z_dim] = z_idx
                    self.current_slice_list.append(data[tuple(slices)])
                elif data.ndim in (1, 2):
                    self.current_slice_list.append(data)
                    
        self.current_slice = next(iter(self.current_slice_list), None) if self.current_slice_list else None
        
        
#---------------------------------------------------------------------        

    def on_file_toggled(self, index, enabled):
        self.file_enabled_flags[index] = enabled
        if self.raw_data is not None:
            self._update_enabled_state()
            self.recompute_contours()

#---------------------------------------------------------------------        

    def update_phase_ui_from_state(self):
        self.grp_phase.setTitle(f"Phase Correction ({self.active_axis.upper()}-Axis)")
        state = self.phase_state[self.active_axis]
        for key, val in state.items():
            sl, sb = self.phase_ui[key]
            sl.blockSignals(True)
            sb.blockSignals(True)
            sl.setValue(int(val * 10))
            sb.setValue(val)
            sl.blockSignals(False)
            sb.blockSignals(False)

#---------------------------------------------------------------------        

    def on_phase_changed(self, key, val):
        self.phase_state[self.active_axis][key] = val
        if self.raw_data is not None and self.raw_data.ndim == 1:
            self.recompute_contours()
        else:
            self.update_live_trace()

#---------------------------------------------------------------------        

    def get_phase_vals(self, axis):
        return self.phase_state[axis]['p0'], self.phase_state[axis]['p1']

#---------------------------------------------------------------------        

    def update_live_trace(self):
        if self.current_mode not in ['x_phase', 'y_phase', 'z_phase'] or self.current_slice is None:
            return
            
        # FIX: Abort live trace updating for 1D spectra since they don't have crosshairs
        if self.current_slice.ndim == 1:
            return
            
        y_idx = np.argmin(np.abs(self.ppm_y - self.h_pos)) if hasattr(self, 'ppm_y') and self.ppm_y is not None else 0
        x_idx = np.argmin(np.abs(self.ppm_x - self.v_pos))
        view_box = self.plot_2d.getViewBox()
        view_x_range, view_y_range = view_box.viewRange()
        
        x_p0, x_p1 = self.get_phase_vals('x')
        y_p0, y_p1 = self.get_phase_vals('y')
        z_p0, z_p1 = self.get_phase_vals('z') if hasattr(self, 'nz') and self.nz > 1 else (0, 0)
        is_real = not np.iscomplexobj(self.raw_data)

        if self.current_mode == 'x_phase':
            trace = self.current_slice[:, y_idx] if self.slice_x_idx == 0 else self.current_slice[y_idx, :]
            trace = self.data_handler.phase_1d(trace, x_p0, x_p1, is_real)
            
            y_mid = (view_y_range[0] + view_y_range[1]) / 2.0
            scale = (abs(view_y_range[1] - view_y_range[0]) * 0.25) / (np.max(np.abs(trace)) + 1e-9)
            self.trace_curve.setData(self.ppm_x, y_mid - (trace * scale))

        elif self.current_mode == 'y_phase':
            trace = self.current_slice[x_idx, :] if self.slice_x_idx == 0 else self.current_slice[:, x_idx]
            trace = self.data_handler.phase_1d(trace, y_p0, y_p1, is_real)
            
            x_mid = (view_x_range[0] + view_x_range[1]) / 2.0
            scale = (abs(view_x_range[1] - view_x_range[0]) * 0.25) / (np.max(np.abs(trace)) + 1e-9)
            self.trace_curve.setData(x_mid + (trace * scale), self.ppm_y)

        elif self.current_mode == 'z_phase' and hasattr(self, 'nz') and self.nz > 1:
            slices = [slice(None)] * 3
            slices[self.x_dim], slices[self.y_dim] = x_idx, y_idx
            trace = self.raw_data[tuple(slices)]
            
            trace = self.data_handler.phase_1d(trace, z_p0, z_p1, is_real)
            
            y_mid = (view_y_range[0] + view_y_range[1]) / 2.0
            scale = (abs(view_y_range[1] - view_y_range[0]) * 0.25) / (np.max(np.abs(trace)) + 1e-9)
            x_coords = np.linspace(view_x_range[0], view_x_range[1], self.nz)
            self.trace_curve.setData(x_coords, y_mid - (trace * scale))
            
            
#---------------------------------------------------------------------        

    def recompute_contours(self):
        if not self.raw_data_list:
            return

        self.plot_2d.getViewBox().disableAutoRange()
        if not hasattr(self, 'vis_data_dict'):
            self.vis_data_dict = {}

        if not self.enabled_indices:
            self.trace_curve.setData([], [])
            for i in range(len(self.raw_data_list)):
                if self.raw_data.ndim == 1 and self.file_curves_1d[i]: 
                    self.file_curves_1d[i].setVisible(False)
                elif self.file_groups[i]: 
                    self.file_groups[i].setVisible(False)
            return

        x_p0, x_p1 = self.get_phase_vals('x')
        y_p0, y_p1 = self.get_phase_vals('y')
        z_p0, z_p1 = self.get_phase_vals('z') if hasattr(self, 'nz') and self.nz > 1 else (0, 0)
        
        if self.raw_data.ndim == 1:
            offset_val = self.cont_sliders['offset'].value()
            base_max = np.max(np.abs(self.current_slice_list[0])) if self.current_slice_list else 1.0
            
            for orig_i in range(len(self.raw_data_list)):
                curve = self.file_curves_1d[orig_i]
                if orig_i not in self.enabled_indices:
                    curve.setVisible(False)
                    continue
                    
                idx = self.enabled_indices.index(orig_i)
                raw_data = self.raw_data_list[orig_i]
                is_real = not np.iscomplexobj(raw_data)
                
                if x_p0 != 0 or x_p1 != 0:
                    plot_data = self.data_handler.phase_1d(raw_data.copy(), x_p0, x_p1, is_real)
                else:
                    plot_data = np.real(raw_data.copy()) if not is_real else raw_data.copy()

                if hasattr(self, 'baseline_corrections') and self.baseline_corrections[orig_i] is not None:
                    plot_data -= self.baseline_corrections[orig_i]

                # OPTIMIZATION: Removed redundant .copy()
                self.vis_data_dict[orig_i] = plot_data               
                y_data = plot_data + (idx * offset_val * (base_max * 0.1))
                c_pos, _ = self.spectrum_colors[orig_i % len(self.spectrum_colors)]
                
                curve.setData(x=self.ppm_x, y=y_data)
                curve.setPen(pg.mkPen(c_pos, width=1))
                curve.setVisible(True)

            # --- NEW: Update and display the 1D Auto-Pick threshold line ---
            if self.enabled_indices:
                primary_i = self.enabled_indices[0]
                vis_data = self.vis_data_dict[primary_i]
                
                # CORRECTION: Read from the new 1D spinbox, not the 2D contour slider
                base_mult = self.spinbox_1d_base.value() 
                noise_rmsd = self.data_handler.calculate_rmsd(vis_data)
                
                # Matches the 1.5x strictness modifier used in auto_pick
                threshold = noise_rmsd * base_mult * 1.5 
                
                self.threshold_line.setPos(threshold)
                self.threshold_line.setVisible(True)
            else:
                self.threshold_line.setVisible(False)
                
            return

        # --- IMPORTANT: Hide the line if we are in 2D/3D mode ---
        if hasattr(self, 'threshold_line'):
            self.threshold_line.setVisible(False)            
            
        base_mult = self.cont_sliders['base'].value()
        scale_fact = self.cont_sliders['scale'].value()
        count = int(self.cont_sliders['count'].value())

        for orig_i in range(len(self.raw_data_list)):
            group, pool = self.file_groups[orig_i], self.file_pools_2d[orig_i]

            if orig_i not in self.enabled_indices:
                group.setVisible(False)
                continue

            group.setVisible(True)
            idx = self.enabled_indices.index(orig_i)
            raw_data = self.raw_data_list[orig_i]  
            is_real = not np.iscomplexobj(raw_data)

            # 1. Z-Plane Phasing
            if raw_data.ndim == 3 and hasattr(self, 'nz') and self.nz > 1 and (z_p0 != 0 or z_p1 != 0):
                target_idx = self.slider_z.value() - 1
                plot_data = self.data_handler.phase_z_plane(raw_data, z_p0, z_p1, self.z_dim, target_idx, is_real)
            else:
                plot_data = self.current_slice_list[idx].copy()

            # 2. X and Y Phasing
            vis_data = self.data_handler.phase_2d(plot_data, x_p0, x_p1, y_p0, y_p1, self.slice_x_idx, is_real)
            
            # OPTIMIZATION: Removed redundant .copy()
            self.vis_data_dict[orig_i] = vis_data
            
            # 3. Calculate View Transforms
            nx, ny = vis_data.shape
            scale_x = (self.ppm_x[-1] - self.ppm_x[0] if len(self.ppm_x) > 1 else 1.0) / max(1, nx - 1)
            scale_y = (self.ppm_y[-1] - self.ppm_y[0] if len(self.ppm_y) > 1 else 1.0) / max(1, ny - 1)
            
            tr = QTransform()
            tr.translate(self.ppm_x[0] - 0.5 * scale_x, self.ppm_y[0] - 0.5 * scale_y)
            tr.scale(scale_x, scale_y)
            group.setTransform(tr)
            
            # 4. Fetch Contour Levels
            all_levels, is_pos = self.data_handler.get_contour_levels(vis_data, base_mult, scale_fact, count)
            c_pos, c_neg = self.spectrum_colors[orig_i % len(self.spectrum_colors)]

            # 5. Draw
            pool_idx = 0
            for level, pos_flag in zip(all_levels, is_pos):
                pen = pg.mkPen(c_pos if pos_flag else c_neg, width=1)
                
                if pool_idx < len(pool):
                    item = pool[pool_idx]
                    item.setData(vis_data, level=level)
                    item.setPen(pen)
                    item.setVisible(True)
                else:
                    item = pg.IsocurveItem(data=vis_data, level=level, pen=pen)
                    group.addItem(item)
                    pool.append(item)
                pool_idx += 1

            for i in range(pool_idx, len(pool)):
                pool[i].setVisible(False)

        self.update_live_trace()
         
#---------------------------------------------------------------------        
