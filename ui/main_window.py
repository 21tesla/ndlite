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
                             QScrollArea, QColorDialog, QCheckBox, QMessageBox, QDialog)
                             
from PyQt6.QtCore import Qt, QTimer

from ui.plot_widget import TrackpadPlotWidget
from ui.dialogs import HelpDialog
from core.data_handler import DataHandler
from core.peak_manager import PeakManager

#---------------------------------------------------------------------        


__version__ = "0.2.0"


#---------------------------------------------------------------------        

        
os.environ["LC_ALL"] = "en_US.UTF-8"
os.environ["LANG"] = "en_US.UTF-8"

pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
pg.setConfigOption('antialias', False)


#---------------------------------------------------------------------        


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

        # --- FIX: Instantiate managers BEFORE loading files ---
        self.peak_manager = PeakManager()
        self.data_handler = DataHandler()

        self.init_ui()
        self.create_menus()
        
        if file_paths:
            self.load_files(file_paths)
 
        QTimer.singleShot(2000, self.silent_update_check)       
        
        
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

        grp_file = QGroupBox("Data")
        v_file = QVBoxLayout()

        btn_load = QPushButton("Load NMRPipe File(s)")
        btn_load.clicked.connect(self.load_file_dialog)
        self.lbl_info = QLabel("No file loaded.")
        v_file.addWidget(btn_load)
        v_file.addWidget(self.lbl_info)

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
            self.update_peak_markers()

        def z_sl_released():
            self._update_enabled_state()
            self.recompute_contours()
            self.update_peak_markers()

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
        
        self.slider_1d_base = QSlider(Qt.Orientation.Horizontal)
        self.slider_1d_base.setMinimum(1)     # 0.01 * 100
        self.slider_1d_base.setMaximum(5000)  # 50.0 * 100
        self.slider_1d_base.setValue(400)     # 4.0 * 100
        
        self.spinbox_1d_base = QDoubleSpinBox()
        self.spinbox_1d_base.setRange(0.01, 50.0)
        self.spinbox_1d_base.setSingleStep(0.1)
        self.spinbox_1d_base.setDecimals(2)
        self.spinbox_1d_base.setValue(4.0)
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

        cont_params = [
            ("base", "Baseline Multiplier", 0.05, 50.0, 4.0, False),
            ("scale", "Contour Multiplier", 1.05, 2.5, 1.3, False),
            ("count", "Number of Contours", 1, 25, 15, True),
            ("offset", "1D Stack Offset", 0.0, 4.0, 0.0, False)
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
                        self.update_peak_markers()
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
                            self.update_peak_markers()

                elif self.current_mode == 'peak_delete':
                    x_range, y_range = view_box.viewRange()
                    dx_scale = max(abs(x_range[1] - x_range[0]), 1e-6)
                    dy_scale = max(abs(y_range[1] - y_range[0]), 1e-6)
                            
                    self.peak_manager.delete_nearest_peak(click_ppm_x, click_ppm_y, dx_scale, dy_scale)
                    self.update_peak_markers()
                    
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
            self.renumber_peaks()
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
            self.save_peaks()
            return

        if text == 'p':
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                if self.raw_data is not None:
                    if self.current_mode != 'peak_pick':
                        self.set_mode('peak_pick')
                    
                    # Delegate to manager
                    self.peak_manager.add_force_peak(self.v_pos, self.h_pos)
                    self.update_peak_markers()
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
                            
    def load_file_dialog(self):
        file_names, _ = QFileDialog.getOpenFileNames(self, "Open NMRPipe File(s)", "", "NMRPipe (*.ft *.ft1 *.ft2 *.ft3)")
        if file_names:
            self.load_files(file_names)

#---------------------------------------------------------------------        

    def load_files(self, file_names):
        if not file_names:
            return
            
        # 1. Clear existing items from the plot
        if hasattr(self, 'file_groups'):
            for g in self.file_groups:
                if g is not None: self.plot_2d.removeItem(g)
        if hasattr(self, 'file_curves_1d'):
            for c in self.file_curves_1d:
                if c is not None: self.plot_2d.removeItem(c)

        self.file_groups = []
        self.file_pools_2d = []
        self.file_curves_1d = []
        self.dic_list = []
        self.raw_data_list = []
        self.spectrum_colors = []
        self.file_enabled_flags = [True] * len(file_names)
        self.baseline_corrections = [None] * len(file_names) 

        # Clear the UI layout
        for i in reversed(range(self.file_layout.count())):
            widget = self.file_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        default_colors = [
            ('#0000FF', '#FF0000'),
            ('#008000', '#FF00FF'),
            ('#00FFFF', '#FFA500'),
            ('#800080', '#FFFF00'),
            ('#000000', '#888888')
        ]

        small_font = QFont()
        small_font.setPointSize(9)

        try:
            # 2. Load Data and Build File Rows
            for i, file_name in enumerate(file_names):
                dic, data = self.data_handler.load_file(file_name)
                self.dic_list.append(dic)
                self.raw_data_list.append(data)
                
                c_pos, c_neg = default_colors[i % len(default_colors)]
                self.spectrum_colors.append([c_pos, c_neg])

                row_widget = QWidget()
                row_widget.setMaximumHeight(18)
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(8)

                chk_box = QCheckBox()
                chk_box.setChecked(True)
                chk_box.stateChanged.connect(lambda state, idx=i: self.on_file_toggled(idx, bool(state)))

                lbl = QLabel(os.path.basename(file_name))
                lbl.setFont(small_font)

                btn_pos = QPushButton()
                btn_pos.setFixedSize(14, 14)
                btn_pos.setToolTip("Positive / 1D Trace Color")
                btn_pos.setStyleSheet(f"background-color: {c_pos}; border: 1px solid #aaa;")

                btn_neg = QPushButton()
                btn_neg.setFixedSize(14, 14)
                btn_neg.setToolTip("Negative Contour Color")
                btn_neg.setStyleSheet(f"background-color: {c_neg}; border: 1px solid #aaa;")

                def make_color_callback(idx, is_pos, btn):
                    def callback():
                        curr_color = self.spectrum_colors[idx][0 if is_pos else 1]
                        color = QColorDialog.getColor(initial=QColor(curr_color), parent=self, title="Select Color")
                        if color.isValid():
                            hex_color = color.name()
                            self.spectrum_colors[idx][0 if is_pos else 1] = hex_color
                            btn.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #aaa;")
                            self.recompute_contours()
                    return callback

                btn_pos.clicked.connect(make_color_callback(i, True, btn_pos))
                btn_neg.clicked.connect(make_color_callback(i, False, btn_neg))

                row_layout.addWidget(chk_box)
                row_layout.addWidget(lbl)
                row_layout.addStretch()
                row_layout.addWidget(btn_pos)
                if data.ndim == 1:
                    btn_neg.hide()
                else:
                    row_layout.addWidget(btn_neg)

                self.file_layout.addWidget(row_widget)

            # 3. Configure Dimensionality State
            self.dic = self.dic_list[0]
            self.raw_data = self.raw_data_list[0]
            ndim = self.raw_data.ndim
            order = self.dic.get('FDDIMORDER', [2, 1, 3, 4])
            is_1d = (ndim == 1)

            # 4. Toggle UI Components
            for key in ['base', 'scale', 'count']:
                lbl, sl, sb = self.cont_widgets[key]
                lbl.setEnabled(not is_1d)
                sl.setEnabled(not is_1d)
                sb.setEnabled(not is_1d)

            lbl, sl, sb = self.cont_widgets['offset']
            lbl.setEnabled(is_1d)
            sl.setEnabled(is_1d)
            sb.setEnabled(is_1d)

            # --- FIX: Completely hide irrelevant menus for a cleaner macOS native experience ---
            if hasattr(self, 'one_d_menu') and hasattr(self, 'two_d_menu'):
                self.one_d_menu.menuAction().setVisible(is_1d)
                self.two_d_menu.menuAction().setVisible(not is_1d)
            # -----------------------------------------------------------------------------------

            self.baseline_1d_container.setVisible(is_1d)

            # 5. Extract Coordinates
            if ndim == 1:
                orig_dim_x = int(order[0]) if len(order) > 0 else 2
                self.label_x = self.dic.get(f'FDF{orig_dim_x}LABEL', '1H')
                self.label_y = "Intensity"
                self.label_z = None

                uc_x = ng.pipe.make_uc(self.dic, self.raw_data, dim=0)
                self.ppm_x, self.lim_x = uc_x.ppm_scale(), uc_x.ppm_limits()
                self.ppm_y, self.lim_y = None, None
                
                self.x_dim, self.y_dim, self.z_dim = 0, None, None
                self.nz = 1
                self.slice_x_idx = 0

                self.plot_2d.setLabel('bottom', self.label_x, units="ppm")
                self.plot_2d.setLabel('left', self.label_y, units="")
                self.plot_2d.getViewBox().invertY(False)

            elif ndim == 3:
                self.z_dim, self.y_dim, self.x_dim = 0, 1, 2

                orig_dim_x = int(order[0]) if len(order) > 0 else 2
                orig_dim_y = int(order[1]) if len(order) > 1 else 3
                orig_dim_z = int(order[2]) if len(order) > 2 else 1

                self.label_x = self.dic.get(f'FDF{orig_dim_x}LABEL', 'X')
                self.label_y = self.dic.get(f'FDF{orig_dim_y}LABEL', 'Y')
                self.label_z = self.dic.get(f'FDF{orig_dim_z}LABEL', 'Z')

                uc_z = ng.pipe.make_uc(self.dic, self.raw_data, dim=self.z_dim)
                uc_y = ng.pipe.make_uc(self.dic, self.raw_data, dim=self.y_dim)
                uc_x = ng.pipe.make_uc(self.dic, self.raw_data, dim=self.x_dim)

                self.ppm_z, self.lim_z = uc_z.ppm_scale(), uc_z.ppm_limits()
                self.ppm_y, self.lim_y = uc_y.ppm_scale(), uc_y.ppm_limits()
                self.ppm_x, self.lim_x = uc_x.ppm_scale(), uc_x.ppm_limits()
                self.nz = self.raw_data.shape[self.z_dim]

                self.plot_2d.setLabel('bottom', self.label_x, units="ppm")
                self.plot_2d.setLabel('left', self.label_y, units="ppm")
                self.plot_2d.getViewBox().invertY(True)

            else:
                self.y_dim, self.x_dim = 0, 1

                orig_dim_x = int(order[0]) if len(order) > 0 else 2
                orig_dim_y = int(order[1]) if len(order) > 1 else 1

                self.label_x = self.dic.get(f'FDF{orig_dim_x}LABEL', 'X')
                self.label_y = self.dic.get(f'FDF{orig_dim_y}LABEL', 'Y')

                uc_plot_y = ng.pipe.make_uc(self.dic, self.raw_data, dim=self.y_dim)
                uc_plot_x = ng.pipe.make_uc(self.dic, self.raw_data, dim=self.x_dim)

                self.z_dim = None
                self.label_z = None
                self.nz = 1
                self.ppm_x, self.lim_x = uc_plot_x.ppm_scale(), uc_plot_x.ppm_limits()
                self.ppm_y, self.lim_y = uc_plot_y.ppm_scale(), uc_plot_y.ppm_limits()

                self.plot_2d.setLabel('bottom', self.label_x, units="ppm")
                self.plot_2d.setLabel('left', self.label_y, units="ppm")
                self.plot_2d.getViewBox().invertY(True)

            if ndim > 1:
                self.slice_x_idx = 1
                
            # 6. Initialize Plot Items
            for idx in range(len(file_names)):
                if is_1d:
                    c_pos, _ = self.spectrum_colors[idx]
                    curve = pg.PlotDataItem(pen=pg.mkPen(c_pos, width=1))
                    self.plot_2d.addItem(curve)
                    self.file_curves_1d.append(curve)
                    self.file_groups.append(None)
                    self.file_pools_2d.append(None)
                else:
                    group = pg.ItemGroup()
                    self.plot_2d.addItem(group)
                    self.file_groups.append(group)
                    self.file_pools_2d.append([])
                    self.file_curves_1d.append(None)

            self.lbl_info.setText(f"Loaded {len(file_names)} spectrum" if len(file_names) == 1 else f"Loaded {len(file_names)} spectra")

            # 7. Setup Navigators and Interactivity
            if ndim > 1:
                self.h_pos = (self.lim_y[0] + self.lim_y[1]) / 2.0
                self.v_pos = (self.lim_x[0] + self.lim_x[1]) / 2.0
                self.hline.setPos(self.h_pos)
                self.vline.setPos(self.v_pos)

            if self.nz > 1:
                self.slider_z.blockSignals(True)
                self.spinbox_z.blockSignals(True)
                
                self.slider_z.setMinimum(1)
                self.slider_z.setMaximum(self.nz)
                self.spinbox_z.setRange(1, self.nz)
                self.spinbox_z.setSingleStep(1)
                
                init_val = (self.nz // 2) + 1
                self.slider_z.setValue(init_val)
                self.spinbox_z.setValue(init_val)
                
                self.slider_z.blockSignals(False)
                self.spinbox_z.blockSignals(False)
                
                self.z_container.show()
                self._update_z_label()
            else:
                self.z_container.hide()

            # 8. Reset States
            self.trace_curve.setData([], [])
            if hasattr(self, 'baseline_anchors'):
                self.baseline_anchors.clear()
                self.baseline_scatter.setData([])

            self.phase_state = {
                'x': {'p0': 0.0, 'p1': 0.0},
                'y': {'p0': 0.0, 'p1': 0.0},
                'z': {'p0': 0.0, 'p1': 0.0}
            }
            if hasattr(self, 'active_axis') and self.active_axis:
                self.update_phase_ui_from_state()

            self._update_enabled_state()
            self.recompute_contours()
            self.set_mode(None)

            # 9. Explicit Mathematical Scaling
            if ndim == 1:
                self.plot_2d.setXRange(float(self.lim_x[0]), float(self.lim_x[1]))
                y_min = float(np.min(self.raw_data))
                y_max = float(np.max(self.raw_data))
                y_pad = abs(y_max - y_min) * 0.05 if y_max != y_min else 1.0
                self.plot_2d.setYRange(y_min - y_pad, y_max + y_pad)
            else:
                self.plot_2d.setXRange(float(self.lim_x[0]), float(self.lim_x[1]))
                self.plot_2d.setYRange(float(self.lim_y[0]), float(self.lim_y[1]))

        except Exception as e:
            self.lbl_info.setText(f"Error loading files: {e}")
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
    def create_menus(self):
        menubar = self.menuBar()
        # Ensures the menu is rendered in the macOS top system menubar
        menubar.setNativeMenuBar(True) 

        # ==========================================
        # 1. CREATE SHARED ACTIONS (Instantiate Once)
        # ==========================================
        save_peaks_action = QAction("Save Peaks", self)
        save_peaks_action.setShortcut("s")
        save_peaks_action.triggered.connect(self.save_peaks)

        auto_pick_action = QAction("Auto Pick", self)
        auto_pick_action.triggered.connect(self.auto_pick)

        show_peaks_action = QAction("Show Peaks", self)
        show_peaks_action.setShortcut("Shift+S")
        show_peaks_action.triggered.connect(self.show_peaks)
        
        hide_peaks_action = QAction("Hide Peaks", self)
        hide_peaks_action.setShortcut("Shift+H")
        hide_peaks_action.triggered.connect(self.hide_peaks)

        clear_peaks_action = QAction("Clear All Peaks", self)
        clear_peaks_action.triggered.connect(self.clear_peaks)
         
        renumber_peaks_action = QAction("Renumber Peaks", self)
        renumber_peaks_action.setShortcut("Shift+R")
        renumber_peaks_action.triggered.connect(self.renumber_peaks)

        # ==========================================
        # 2. BUILD MENUS
        # ==========================================

        # --- File Menu ---
        file_menu = menubar.addMenu("File")
        file_menu.addAction(save_peaks_action)
        
        export_menu = file_menu.addMenu("Export")
        
        export_spectrum_action = QAction("Spectrum", self)
        export_spectrum_action.triggered.connect(self.export_spectrum)
        export_menu.addAction(export_spectrum_action)
        
        export_peaks_action = QAction("Peaks + Spectrum", self)
        export_peaks_action.triggered.connect(self.export_peaks_spectrum)
        export_menu.addAction(export_peaks_action)


        # --- 1D Mode Menu ---
        self.one_d_menu = menubar.addMenu("1D-Mode")
        
        # 1. Baseline Sub-menu
        baseline_menu = self.one_d_menu.addMenu("Baseline")
        
        als_action = QAction("Auto-Correct Baseline (ALS)", self)
        als_action.triggered.connect(self.run_als_baseline)
        baseline_menu.addAction(als_action)
        
        interactive_base_action = QAction("Interactive Anchors", self)
        interactive_base_action.triggered.connect(self.start_interactive_baseline)
        baseline_menu.addAction(interactive_base_action)
        
        clear_base_action = QAction("Clear Baseline", self)
        clear_base_action.triggered.connect(self.clear_baseline)
        baseline_menu.addAction(clear_base_action)        

        self.one_d_menu.addSeparator()

        # 2. Auto Pick 
        self.one_d_menu.addAction(auto_pick_action)

        self.one_d_menu.addSeparator()

        # 3. Peak Functions Sub-menu
        peak_funcs_menu = self.one_d_menu.addMenu("Peak functions")
        peak_funcs_menu.addAction(show_peaks_action)
        peak_funcs_menu.addAction(hide_peaks_action)
        peak_funcs_menu.addAction(clear_peaks_action)
        peak_funcs_menu.addAction(renumber_peaks_action)

        self.one_d_menu.addSeparator()

        # 4. Fitting Sub-menu
        fit_menu = self.one_d_menu.addMenu("Fitting")
        
        fit_lor_action = QAction("Lorentzian", self)
        fit_lor_action.triggered.connect(lambda: self.fit_1d_peaks('lorentzian'))
        fit_menu.addAction(fit_lor_action)
        
        fit_gau_action = QAction("Gaussian", self)
        fit_gau_action.triggered.connect(lambda: self.fit_1d_peaks('gaussian'))
        fit_menu.addAction(fit_gau_action)
        
        fit_pvo_action = QAction("Pseudo-Voigt", self)
        fit_pvo_action.triggered.connect(lambda: self.fit_1d_peaks('pseudo_voigt'))
        fit_menu.addAction(fit_pvo_action)

        fit_menu.addSeparator()

        clear_fits_action = QAction("Clear Fits", self)
        clear_fits_action.triggered.connect(self.clear_1d_fits)
        fit_menu.addAction(clear_fits_action)

        self.one_d_menu.addSeparator()

        # 5. Save Peaks
        self.one_d_menu.addAction(save_peaks_action)


        # --- 2D/3D-Peaks Menu ---
        self.two_d_menu = menubar.addMenu("2D/3D-Mode")
        
        # Add shared peak actions to the 2D/3D menu
        self.two_d_menu.addAction(auto_pick_action)
        
        pick_peaks_action = QAction("Pick Peaks", self)
        pick_peaks_action.setShortcut("p")
        pick_peaks_action.triggered.connect(lambda: self.set_mode('peak_pick'))
        self.two_d_menu.addAction(pick_peaks_action)
        
        force_pick_action = QAction("Force Pick", self)
        force_pick_action.setShortcut("Shift+P")
        force_pick_action.triggered.connect(self.force_pick)
        self.two_d_menu.addAction(force_pick_action)

        self.two_d_menu.addAction(show_peaks_action)
        self.two_d_menu.addAction(hide_peaks_action)
        
        delete_peaks_action = QAction("Delete Peaks", self)
        delete_peaks_action.setShortcut("d")
        delete_peaks_action.triggered.connect(lambda: self.set_mode('peak_delete'))
        self.two_d_menu.addAction(delete_peaks_action)
        
        self.two_d_menu.addAction(clear_peaks_action)
        self.two_d_menu.addAction(renumber_peaks_action)
        self.two_d_menu.addAction(save_peaks_action)
                
 
        # --- Extras Menu ---
        extras_menu = menubar.addMenu("Extras")
        
        update_action = QAction("Check for Updates...", self)
        update_action.triggered.connect(self.check_for_updates)
        extras_menu.addAction(update_action)
        
        help_action = QAction("Help", self)
        help_action.setShortcut("h")
        help_action.triggered.connect(self.show_help_dialog)
        extras_menu.addAction(help_action)
        
#---------------------------------------------------------------------        
                
    def export_spectrum(self):
        self._export_with_mode('spectrum')

#---------------------------------------------------------------------        

    def export_peaks_spectrum(self):
        self._export_with_mode('peaks')

#---------------------------------------------------------------------        

    def _export_with_mode(self, mode):
        self.is_exporting = True
        
        # Store current visibility states so we can restore them exactly
        self._export_state = {
            'hline': self.hline.isVisible(),
            'vline': self.vline.isVisible(),
            'trace': self.trace_curve.isVisible(),
            'scatter': self.peaks_scatter.isVisible(),
            'texts': {pid: item.isVisible() for pid, item in self.peak_text_items.items()}
        }
        
        # Hide crosshairs, live trace, and the plot title
        self.hline.setVisible(False)
        self.vline.setVisible(False)
        self.trace_curve.setVisible(False)
        self.plot_2d.setTitle(" ")
        
        # Toggle peaks based on the selected menu option
        if mode == 'spectrum':
            self.hide_peaks()
        elif mode == 'peaks':
            self.show_peaks()
                
        # Trigger export dialog
        scene = self.plot_2d.scene()
        scene.contextMenuItem = self.plot_2d.getPlotItem()
        scene.showExportDialog()
        
        # Setup a robust timer to check when the dialog is closed
        if not hasattr(self, 'export_poll_timer'):
            self.export_poll_timer = QTimer(self)
            self.export_poll_timer.timeout.connect(self._check_export_dialog_closed)
        self.export_poll_timer.start(200)

#---------------------------------------------------------------------        

    def _check_export_dialog_closed(self):
        try:
            scene = self.plot_2d.scene()
            # Stop the timer and restore the UI once the dialog is no longer visible
            if not hasattr(scene, 'exportDialog') or scene.exportDialog is None or not scene.exportDialog.isVisible():
                self.export_poll_timer.stop()
                self._restore_export_state()
        except RuntimeError:
            # Failsafe in case the underlying C++ object is deleted abruptly
            self.export_poll_timer.stop()
            self._restore_export_state()

#---------------------------------------------------------------------        

    def _restore_export_state(self):
        self.is_exporting = False
        
        # Restore the exact visibility states from before the export
        if hasattr(self, '_export_state'):
            self.hline.setVisible(self._export_state.get('hline', False))
            self.vline.setVisible(self._export_state.get('vline', False))
            self.trace_curve.setVisible(self._export_state.get('trace', False))
            self.peaks_scatter.setVisible(self._export_state.get('scatter', True))
            
            for pid, item in self.peak_text_items.items():
                if pid in self._export_state['texts']:
                    item.setVisible(self._export_state['texts'][pid])
                
        # Trigger set_mode to safely restore the proper plot title
        self.set_mode(self.current_mode)
        
 #---------------------------------------------------------------------        
                                  
    def check_for_updates(self):
        # Replace with your actual GitHub repository details
        repo = "21tesla/NMRdraw_lite"
        url = f"https://api.github.com/repos/{repo}/releases/latest"
        
        try:
            # Create a context that uses certifi's updated certificates
            context = ssl.create_default_context(cafile=certifi.where())
        
            req = Request(url, headers={'User-Agent': 'NMRdraw_lite-Updater'})
            with urlopen(req, context=context) as response:

                data = json.loads(response.read().decode())
                
                # GitHub tags usually have a 'v' prefix (e.g., 'v1.1.0'). Strip it for comparison.
                latest_version = data['tag_name'].lstrip('v')
                release_url = data['html_url']

            # Helper function to convert "1.2.0" into a tuple of integers (1, 2, 0) for accurate math comparison
            def parse_version(v_string):
                return tuple(map(int, (v_string.split("."))))

            if parse_version(latest_version) > parse_version(__version__):
                reply = QMessageBox.question(
                    self, 
                    "Update Available",
                    f"A new version of NMRdraw_lite ({latest_version}) is available!\n"
                    f"You are currently running version {__version__}.\n\n"
                    f"Would you like to open your browser to download it?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    webbrowser.open(release_url)
            else:
                QMessageBox.information(self, "Up to Date", f"You are running the latest version ({__version__}).")

        except Exception as e:
            QMessageBox.warning(self, "Update Check Failed", f"Could not check GitHub for updates.\nError: {e}")

#---------------------------------------------------------------------        

    def save_peaks(self):
        if not self.peak_manager.picked_peaks:
            self.plot_2d.setTitle("No peaks to save.")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Peaks", "peaks.txt", "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                ndim = self.raw_data.ndim if self.raw_data is not None else 0
                
                def calc_pt(ppm_val, ppm_array):
                    if ppm_array is None or len(ppm_array) <= 1: return 0.0
                    return (ppm_val - ppm_array[0]) / (ppm_array[-1] - ppm_array[0]) * (len(ppm_array) - 1)

                def calc_volume(px, py, pz=None):
                    if self.raw_data is None: return 0.0
                    
                    x_idx = np.argmin(np.abs(self.ppm_x - px))
                    y_idx = np.argmin(np.abs(self.ppm_y - py)) if self.ppm_y is not None else 0
                    
                    wx, wy, wz = 5, 5, 2  # Integration window (matches refine_peak)
                    
                    start_x = max(0, x_idx - wx)
                    end_x = min(self.raw_data.shape[-1], x_idx + wx + 1)
                    
                    if ndim == 1:
                        return float(np.sum(self.raw_data[start_x:end_x]))
                    elif ndim == 2:
                        start_y = max(0, y_idx - wy)
                        end_y = min(self.raw_data.shape[0], y_idx + wy + 1)
                        return float(np.sum(self.raw_data[start_y:end_y, start_x:end_x]))
                    elif ndim >= 3:
                        if pz is None or self.ppm_z is None: return 0.0
                        z_idx = np.argmin(np.abs(self.ppm_z - pz))
                        start_y = max(0, y_idx - wy)
                        end_y = min(self.raw_data.shape[1], y_idx + wy + 1)
                        start_z = max(0, z_idx - wz)
                        end_z = min(self.raw_data.shape[0], z_idx + wz + 1)
                        return float(np.sum(self.raw_data[start_z:end_z, start_y:end_y, start_x:end_x]))
                    return 0.0

                with open(file_path, "w") as f:
                    if ndim == 1:
                        # Check if the first peak has been fitted
                        has_fits = 'fit_area' in self.peak_manager.picked_peaks[0] if self.peak_manager.picked_peaks else False
                        
                        if has_fits:
                            f.write(f"Index\t{self.label_x}_ppm\t{self.label_x}_pt\tFit_Type\tLinewidth\tArea_Integral\n")
                            for p in self.peak_manager.picked_peaks:
                                pt_x = calc_pt(p['ppm_x'], self.ppm_x)
                                f.write(f"{p['id']}\t{p['ppm_x']:.5f}\t{pt_x:.5f}\t{p.get('fit_type', 'none')}\t{abs(p.get('fit_wid', 0.0)):.5e}\t{p.get('fit_area', 0.0):.5e}\n")
                        else:
                            f.write(f"Index\t{self.label_x}_ppm\t{self.label_x}_pt\tVolume_Sum\n")
                            for p in self.peak_manager.picked_peaks:
                                pt_x = calc_pt(p['ppm_x'], self.ppm_x)
                                vol = calc_volume(p['ppm_x'], p['ppm_y'])
                                f.write(f"{p['id']}\t{p['ppm_x']:.5f}\t{pt_x:.5f}\t{vol:.5e}\n")
                                                            
                    elif ndim == 2:
                        f.write(f"Index\t{self.label_x}_ppm\t{self.label_y}_ppm\t{self.label_x}_pt\t{self.label_y}_pt\tVolume\n")
                        for p in self.peak_manager.picked_peaks:
                            pt_x = calc_pt(p['ppm_x'], self.ppm_x)
                            pt_y = calc_pt(p['ppm_y'], self.ppm_y)
                            vol = calc_volume(p['ppm_x'], p['ppm_y'])
                            f.write(f"{p['id']}\t{p['ppm_x']:.5f}\t{p['ppm_y']:.5f}\t{pt_x:.5f}\t{pt_y:.5f}\t{vol:.5e}\n")
                            
                    elif ndim >= 3:
                        lbl_z = self.label_z if self.label_z else "Z"
                        f.write(f"Index\t{self.label_x}_ppm\t{self.label_y}_ppm\t{lbl_z}_ppm\t{self.label_x}_pt\t{self.label_y}_pt\t{lbl_z}_pt\tVolume\n")
                        for p in self.peak_manager.picked_peaks:
                            pt_x = calc_pt(p['ppm_x'], self.ppm_x)
                            pt_y = calc_pt(p['ppm_y'], self.ppm_y)
                            ppm_z_val = p.get('ppm_z', 0.0)
                            pt_z = calc_pt(ppm_z_val, self.ppm_z) if self.ppm_z is not None else 0.0
                            vol = calc_volume(p['ppm_x'], p['ppm_y'], ppm_z_val)
                            f.write(f"{p['id']}\t{p['ppm_x']:.5f}\t{p['ppm_y']:.5f}\t{ppm_z_val:.5f}\t{pt_x:.5f}\t{pt_y:.5f}\t{pt_z:.5f}\t{vol:.5e}\n")

                self.plot_2d.setTitle(f"Success: Picked peaks saved to {os.path.basename(file_path)}")
            except Exception as e:
                self.plot_2d.setTitle(f"Error saving peaks: {e}")
                
                
#---------------------------------------------------------------------        
                
    def show_peaks(self):
        self.peaks_scatter.setVisible(True)
        for item in self.peak_text_items.values():
            item.setVisible(True)

#---------------------------------------------------------------------        

    def hide_peaks(self):
        self.peaks_scatter.setVisible(False)
        for item in self.peak_text_items.values():
            item.setVisible(False)

#---------------------------------------------------------------------        

    def force_pick(self):
        if self.raw_data is not None:
            if self.raw_data.ndim < 2:
                QMessageBox.information(self, "Feature in Progress", "Force Picking is only supported for 2D and 3D spectra.")
                return

            if self.current_mode != 'peak_pick':
                self.set_mode('peak_pick')

            current_z_idx = self.slider_z.value() - 1 if self.nz > 1 else None
            current_ppm_z = self.ppm_z[current_z_idx] if self.nz > 1 else None

            self.peak_manager.add_force_peak(self.v_pos, self.h_pos, ppm_z=current_ppm_z, closest_z_idx=current_z_idx)
            self.update_peak_markers()
        
#---------------------------------------------------------------------        
            
    def renumber_peaks(self):
        # Look at the manager's list!
        if not self.peak_manager.picked_peaks:
            self.plot_2d.setTitle("No peaks to renumber.")
            return
            
        # Clear existing text items from the plot to prevent overlapping numbers
        for pid, text_item in self.peak_text_items.items():
            self.plot_2d.removeItem(text_item)
        self.peak_text_items.clear()
        
        # Tell the manager to do the math
        self.peak_manager.renumber_peaks()
        
        # Redraw markers with the newly assigned IDs
        self.update_peak_markers()
        self.plot_2d.setTitle("Success: Peaks renumbered sequentially.")
        
#---------------------------------------------------------------------        

    def update_peak_markers(self):
        spots = []
        current_ids = set()
        peaks = self.peak_manager.picked_peaks 
        current_z_idx = self.slider_z.value() - 1 if self.nz > 1 else None

        # Create custom symbol: Open circle with an 'X' cross through it
        cross_circle = QPainterPath()
        cross_circle.addEllipse(-0.5, -0.5, 1.0, 1.0)
        cross_circle.moveTo(-0.5, -0.5)
        cross_circle.lineTo(0.5, 0.5)
        cross_circle.moveTo(-0.5, 0.5)
        cross_circle.lineTo(0.5, -0.5)
        
        for p in peaks:
            pid = p['id']

            # 3D Visibility Logic
            is_center_plane = True
            is_visible = True
            
            if self.nz > 1 and p.get('closest_z') is not None:
                z_diff = abs(p['closest_z'] - current_z_idx)
                if z_diff == 0:
                    is_center_plane = True
                elif z_diff <= 2:
                    is_center_plane = False
                else:
                    is_visible = False # Exists outside the n-2 to n+2 window

            if not is_visible:
                continue

            current_ids.add(pid)

            if is_center_plane:
                spots.append({
                    'pos': (p['ppm_x'], p['ppm_y']), 
                    'data': pid,
                    'brush': pg.mkBrush(255, 0, 0, 150),  # Solid red
                    'pen': pg.mkPen('k'),
                    'symbol': 'o'
                })
            else:
                spots.append({
                    'pos': (p['ppm_x'], p['ppm_y']), 
                    'data': pid,
                    'brush': pg.mkBrush(0, 0, 0, 0),      # Transparent
                    'pen': pg.mkPen(255, 0, 0, 150, width=1.5),
                    'symbol': cross_circle
                })

            if pid not in self.peak_text_items:
                text_item = pg.TextItem(text=str(pid), color=(0, 0, 0), anchor=(-0.2, 0.5)) 
                text_item.setPos(p['ppm_x'], p['ppm_y'])
                self.plot_2d.addItem(text_item)
                self.peak_text_items[pid] = text_item

        self.peaks_scatter.setData(spots)

        # Clean up deleted peaks OR peaks that have scrolled out of the visible Z-window
        ids_to_remove = set(self.peak_text_items.keys()) - current_ids
        for pid in ids_to_remove:
            self.plot_2d.removeItem(self.peak_text_items[pid])
            del self.peak_text_items[pid]            
            
#---------------------------------------------------------------------        

    def auto_pick(self):
        if not self.enabled_indices or not hasattr(self, 'vis_data_dict'):
            QMessageBox.warning(self, "No Data", "Please load a spectrum before auto-picking.")
            return
            
        orig_i = self.enabled_indices[0]
        vis_data = self.vis_data_dict.get(orig_i)
        raw_data = self.raw_data_list[orig_i]
                
        if vis_data is None:
            return

        # --- CRITICAL FIX: Route to the new 1D slider if ndim == 1 ---
        if raw_data.ndim == 1:
            base_mult = self.spinbox_1d_base.value()
        else:
            base_mult = self.cont_sliders['base'].value()
            
        noise_rmsd = self.data_handler.calculate_rmsd(vis_data)
        
        # Matches the 1.5x strictness modifier used for the red line
        threshold = noise_rmsd * base_mult * 1.5
        
        if self.peak_manager.picked_peaks:
            reply = QMessageBox.question(
                self, "Clear existing peaks?", 
                "Do you want to clear your current peak list before auto-picking?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.peak_manager.picked_peaks.clear()
                self.peak_manager.peak_counter = 0
                # --- FIX: Remove leftover fit lines from the old peaks ---
                self.clear_1d_fits()
                
        # Run the fast NumPy scan
        if raw_data.ndim == 3:
            self.peak_manager.auto_pick(raw_data, self.ppm_x, self.ppm_y, threshold, ppm_z=getattr(self, 'ppm_z', None))
        else:
            self.peak_manager.auto_pick(vis_data, self.ppm_x, self.ppm_y, threshold)
        
        # Redraw the UI
        self.update_peak_markers()
        self.plot_2d.setTitle(f"Success: Auto-picked {len(self.peak_manager.picked_peaks)} peaks above the baseline.")
    def clear_peaks(self):
        if not self.peak_manager.picked_peaks:
            self.plot_2d.setTitle("No peaks to clear.")
            return

        reply = QMessageBox.question(
            self, "Clear all peaks?", 
            "Are you sure you want to delete all picked peaks? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.peak_manager.clear_peaks()
            self.update_peak_markers()
            self.plot_2d.setTitle("Success: All peaks cleared.")
            
#---------------------------------------------------------------------        
           
    def silent_update_check(self):
        # Replace with your actual GitHub repository details
        repo = "21tesla/NMRdraw_lite"
        url = f"https://api.github.com/repos/{repo}/releases/latest"
        
        try:
            # GitHub's API requires a User-Agent header
            req = urllib.request.Request(url, headers={'User-Agent': 'NMRdraw_lite-App'})
            with urllib.request.urlopen(req, timeout=3) as response:
                data = json.loads(response.read().decode())
                
                # GitHub tags usually have a 'v' prefix (e.g., 'v1.1.0'). Strip it for comparison.
                latest_version = data['tag_name'].lstrip('v')
                release_url = data['html_url']

            # Helper function to convert "1.2.0" into a tuple of integers (1, 2, 0)
            def parse_version(v_string):
                return tuple(map(int, (v_string.split("."))))

            if parse_version(latest_version) > parse_version(__version__):
                reply = QMessageBox.question(
                    self, 
                    "Update Available",
                    f"A new version of NMRdraw_lite ({latest_version}) is available!\n"
                    f"You are currently running version {__version__}.\n\n"
                    f"Would you like to open your browser to download it?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    webbrowser.open(release_url)
            # Notice the lack of an 'else' block here. If they are up to date, it does nothing!

        except Exception:
            # We also fail silently on network errors so it doesn't bother the user on startup
            pass 

#---------------------------------------------------------------------        
            
    def _check_1d_baseline_validity(self):
        if self.raw_data is None or self.raw_data.ndim != 1:
            QMessageBox.warning(self, "Invalid Mode", "Baseline correction is only available for 1D spectra.")
            return False
            
        if len(self.enabled_indices) != 1:
            QMessageBox.warning(self, "Invalid Selection", "Please ensure exactly ONE 1D spectrum is enabled to perform baseline correction.")
            return False
            
        return True 
        
#---------------------------------------------------------------------        
        
    def run_als_baseline(self):
        if not self._check_1d_baseline_validity(): return
        
        orig_i = self.enabled_indices[0]
        data_1d = self.raw_data_list[orig_i]
        
        # Calculate the baseline using the handler
        baseline = self.data_handler.baseline_als(np.real(data_1d))
        
        # Store it non-destructively
        self.baseline_corrections[orig_i] = baseline
        
        self.recompute_contours()
        self.plot_2d.setTitle("Success: ALS Baseline correction applied.")
        
#---------------------------------------------------------------------        

    def start_interactive_baseline(self):
        if not self._check_1d_baseline_validity(): return
        
        self.baseline_anchors.clear()
        self.baseline_scatter.setData([])
        self.baseline_scatter.setVisible(True)
        self.set_mode('baseline_interactive')       

#---------------------------------------------------------------------        
        

    def clear_baseline(self):
        if not self._check_1d_baseline_validity(): return
        
        orig_i = self.enabled_indices[0]
        if hasattr(self, 'baseline_corrections') and self.baseline_corrections[orig_i] is not None:
            self.baseline_corrections[orig_i] = None
            self.recompute_contours()
            self.plot_2d.setTitle("Success: Baseline correction cleared.")
        else:
            self.plot_2d.setTitle("No baseline correction to clear.")     
            
            
#---------------------------------------------------------------------        

    def fit_1d_peaks(self, shape_type):
        if self.raw_data is None or self.raw_data.ndim != 1:
            QMessageBox.warning(self, "1D Only", "Rigorous peak fitting is currently only available for 1D spectra.")
            return
            
        if not self.peak_manager.picked_peaks:
            QMessageBox.warning(self, "No Peaks", "Please pick peaks before attempting to fit them.")
            return

        # --- FIX: Purge old visual curves and mathematical data before calculating new ones ---
        self.clear_1d_fits()
            
        orig_i = self.enabled_indices[0]
        y_data = self.vis_data_dict.get(orig_i) 
        if y_data is None: return
        x_data = self.ppm_x
        
        window_pts = 15
        
        # ... (The rest of your existing fit_1d_peaks loop stays exactly the same) ...        
        for p in self.peak_manager.picked_peaks:
            center_ppm = p['ppm_x']
            idx_center = np.argmin(np.abs(x_data - center_ppm))
            
            start_idx = max(0, idx_center - window_pts)
            end_idx = min(len(x_data), idx_center + window_pts + 1)
            
            x_fit = x_data[start_idx:end_idx]
            y_fit = y_data[start_idx:end_idx]
            
            # Intelligent initial guesses for the optimizer
            amp_guess = y_data[idx_center]
            cen_guess = center_ppm
            wid_guess = np.abs(x_data[0] - x_data[1]) * 4 # Guess width is ~4 data points
            
            try:
                # --- FIX: Apply mathematical bounds so the solver doesn't spiral to infinity ---
                amp_guess = max(1e-6, y_data[idx_center]) # Force positive guess
                
                # Bounds: ( [min_amp, min_cen, min_wid], [max_amp, max_cen, max_wid] )
                bounds_standard = ([0, -np.inf, 0], [np.inf, np.inf, np.inf]) 
                
                if shape_type == 'lorentzian':
                    popt, _ = curve_fit(self.data_handler.lorentzian, x_fit, y_fit, p0=[amp_guess, cen_guess, wid_guess], bounds=bounds_standard)
                    area = self.data_handler.calc_analytical_area(popt[0], popt[2], 'lorentzian')
                    p['fit_amp'], p['fit_cen'], p['fit_wid'] = popt
                    p['fit_eta'] = 1.0
                elif shape_type == 'gaussian':
                    popt, _ = curve_fit(self.data_handler.gaussian, x_fit, y_fit, p0=[amp_guess, cen_guess, wid_guess], bounds=bounds_standard)
                    area = self.data_handler.calc_analytical_area(popt[0], popt[2], 'gaussian')
                    p['fit_amp'], p['fit_cen'], p['fit_wid'] = popt
                    p['fit_eta'] = 0.0
                elif shape_type == 'pseudo_voigt':
                    bounds_pv = ([0, -np.inf, 0, 0.0], [np.inf, np.inf, np.inf, 1.0])
                    popt, _ = curve_fit(self.data_handler.pseudo_voigt, x_fit, y_fit, p0=[amp_guess, cen_guess, wid_guess, 0.5], bounds=bounds_pv)
                    area = self.data_handler.calc_analytical_area(popt[0], popt[2], 'pseudo_voigt', popt[3])
                    p['fit_amp'], p['fit_cen'], p['fit_wid'], p['fit_eta'] = popt

                # Update dictionary with rigorous mathematical data
                p['fit_area'] = abs(area)
                p['fit_type'] = shape_type
                
                # Snap the visual marker to the true mathematical center!
                p['ppm_x'] = p['fit_cen'] 
                
            except Exception as e:
                # If SciPy fails to converge, mark it so we don't crash the export
                p['fit_type'] = 'failed'
                p['fit_area'] = 0.0

        self.update_peak_markers()
        self.draw_1d_fits()
        self.plot_2d.setTitle(f"Success: Fitted {len(self.peak_manager.picked_peaks)} peaks using {shape_type.replace('_', '-').title()}.")

#---------------------------------------------------------------------        

    def draw_1d_fits(self):
        # Clear old fitted curves
        if hasattr(self, 'fit_curves'):
            for curve in self.fit_curves:
                self.plot_2d.removeItem(curve)
        self.fit_curves = []
        
        orig_i = self.enabled_indices[0]
        offset_val = self.cont_sliders['offset'].value()
        base_max = np.max(np.abs(self.current_slice_list[0])) if self.current_slice_list else 1.0
        y_offset = (self.enabled_indices.index(orig_i) * offset_val * (base_max * 0.1))

        # Draw a highlighted curve for every successfully fitted peak
        for p in self.peak_manager.picked_peaks:
            if p.get('fit_type') in ['lorentzian', 'gaussian', 'pseudo_voigt']:
                window_pts = 30 # Draw a wider window so the user can see the tails matching
                idx_center = np.argmin(np.abs(self.ppm_x - p['fit_cen']))
                start_idx = max(0, idx_center - window_pts)
                end_idx = min(len(self.ppm_x), idx_center + window_pts + 1)
                
                x_render = self.ppm_x[start_idx:end_idx]
                
                if p['fit_type'] == 'lorentzian':
                    y_render = self.data_handler.lorentzian(x_render, p['fit_amp'], p['fit_cen'], p['fit_wid'])
                elif p['fit_type'] == 'gaussian':
                    y_render = self.data_handler.gaussian(x_render, p['fit_amp'], p['fit_cen'], p['fit_wid'])
                else:
                    y_render = self.data_handler.pseudo_voigt(x_render, p['fit_amp'], p['fit_cen'], p['fit_wid'], p['fit_eta'])

                # Render the mathematical fit in thick magenta on top of the raw data
                fit_curve = pg.PlotDataItem(x=x_render, y=y_render + y_offset, pen=pg.mkPen('m', width=2, style=Qt.PenStyle.DashLine))
                self.plot_2d.addItem(fit_curve)
                self.fit_curves.append(fit_curve)  
                
                
#---------------------------------------------------------------------        

    def clear_1d_fits(self):
        """Removes fitted curves from the plot and scrubs fit data from peak dictionaries."""
        # 1. Remove the visual dashed lines
        if hasattr(self, 'fit_curves'):
            for curve in self.fit_curves:
                self.plot_2d.removeItem(curve)
        self.fit_curves = []
        
        # 2. Scrub the mathematical data so ghost fits don't export or re-render
        if hasattr(self, 'peak_manager') and self.peak_manager.picked_peaks:
            for p in self.peak_manager.picked_peaks:
                keys_to_remove = ['fit_type', 'fit_amp', 'fit_cen', 'fit_wid', 'fit_eta', 'fit_area']
                for k in keys_to_remove:
                    p.pop(k, None)  

#---------------------------------------------------------------------        
                    
                    
    def start_interactive_baseline(self):
        # --- FIX: Ensure anchors list and scatter plot exist before clearing ---
        if not hasattr(self, 'baseline_anchors'):
            self.baseline_anchors = []
            self.baseline_scatter = pg.ScatterPlotItem(size=10, pen=pg.mkPen('k'), brush=pg.mkBrush(0, 255, 0, 150))
            self.plot_2d.addItem(self.baseline_scatter)
            
        self.baseline_anchors.clear()
        self.baseline_scatter.setData([])
        self.set_mode('baseline_interactive')
        self.plot_2d.setTitle("Interactive Baseline: Left-click to add anchors, Right-click to exit.")                                              