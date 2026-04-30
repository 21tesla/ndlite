#!/opt/homebrew/Caskroom/miniconda/base/bin/python

import sys
import os
import numpy as np
import nmrglue as ng
from scipy.signal import hilbert
from scipy.optimize import curve_fit

import pyqtgraph.exporters 

from PyQt6.QtGui import QTransform, QColor, QFont, QMouseEvent, QAction
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QGridLayout, QPushButton, QFileDialog,
                             QLabel, QSlider, QGroupBox, QDoubleSpinBox, QSpinBox,
                             QScrollArea, QColorDialog, QCheckBox, QMessageBox, QDialog)
                             
from PyQt6.QtCore import Qt, QTimer

import pyqtgraph as pg

os.environ["LC_ALL"] = "en_US.UTF-8"
os.environ["LANG"] = "en_US.UTF-8"

pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
pg.setConfigOption('antialias', False)

class TrackpadPlotWidget(pg.PlotWidget):
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

        self.init_ui()
        self.create_menus()
        if file_paths:
            self.load_files(file_paths)

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

        def z_sl_released():
            self._update_enabled_state()
            self.recompute_contours()

        self.slider_z.valueChanged.connect(z_sl_changed)
        self.spinbox_z.valueChanged.connect(z_sb_changed)
        self.slider_z.sliderReleased.connect(z_sl_released)

        h_z.addWidget(self.lbl_z)
        h_z.addWidget(self.slider_z)
        h_z.addWidget(self.spinbox_z)
        
        self.z_container.hide()
        v_file.addWidget(self.z_container)

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
                    spinbox.setValue(val / 10.0)
                    spinbox.blockSignals(False)
                    self.on_phase_changed(k, val / 10.0)

                def sb_changed(val):
                    slider.blockSignals(True)
                    slider.setValue(int(val * 10))
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
                        spinbox.setValue(val / 100.0)
                        spinbox.blockSignals(False)

                    def sb_changed(val):
                        slider.blockSignals(True)
                        slider.setValue(int(val * 100))
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
        self.trace_curve = pg.PlotDataItem(pen=pg.mkPen(color='#DAA520', width=2), autoDownsample=True, clipToView=True)
        self.plot_2d.addItem(self.hline)
        self.plot_2d.addItem(self.vline)
        self.plot_2d.addItem(self.trace_curve)

        self.peaks_scatter = pg.ScatterPlotItem(size=10, pen=pg.mkPen('k'), brush=pg.mkBrush(255, 0, 0, 150))
        self.plot_2d.addItem(self.peaks_scatter)
        self.picked_peaks = []
        self.peak_counter = 0
        self.peak_text_items = {}
        
        self.hline.setVisible(False)
        self.vline.setVisible(False)
        self.trace_curve.setVisible(False)

        main_layout.addWidget(self.plot_2d, stretch=1)

    def _update_z_label(self):
        if not self.raw_data_list or self.nz <= 1:
            return
        z_idx = self.slider_z.value() - 1
        z_ppm = self.ppm_z[z_idx] if hasattr(self, 'ppm_z') and self.ppm_z is not None else z_idx
        self.lbl_z.setText(f"{self.label_z or 'Z-Plane'}: {z_ppm:.2f} ppm")

    def set_mode(self, mode):
        if self.raw_data is not None and self.raw_data.ndim == 2 and mode == 'z_phase':
            return
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

    def on_mouse_clicked(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.hline.setVisible(False)
            self.vline.setVisible(False)
            self.trace_curve.setVisible(False)
            self.plot_2d.setTitle(" ")
            
        elif event.button() == Qt.MouseButton.LeftButton:
            if self.current_mode in ['peak_pick', 'peak_delete']:
                view_box = self.plot_2d.getViewBox()
                mouse_point = view_box.mapSceneToView(event.scenePos())
                click_ppm_x = mouse_point.x()
                click_ppm_y = mouse_point.y()
                
                if self.current_mode == 'peak_pick':
                    if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                        self.peak_counter += 1
                        self.picked_peaks.append({'id': self.peak_counter, 'ppm_x': click_ppm_x, 'ppm_y': click_ppm_y})
                        self.update_peak_markers()
                    else:
                        self.refine_peak(click_ppm_x, click_ppm_y)
                elif self.current_mode == 'peak_delete':
                    self.delete_nearest_peak(click_ppm_x, click_ppm_y)
                
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.set_mode(None)
            return
            
        # Add Shift-R for sequential renumbering
        if event.key() == Qt.Key.Key_R and (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.renumber_peaks()
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
                    self.peak_counter += 1
                    self.picked_peaks.append({'id': self.peak_counter, 'ppm_x': self.v_pos, 'ppm_y': self.h_pos})
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
                
                            
    def load_file_dialog(self):
        file_names, _ = QFileDialog.getOpenFileNames(self, "Open NMRPipe File(s)", "", "NMRPipe (*.ft *.ft1 *.ft2 *.ft3)")
        if file_names:
            self.load_files(file_names)

    def load_files(self, file_names):
        if not file_names:
            return
            
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
        for i in reversed(range(self.file_layout.count())):
            widget = self.file_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        self.spectrum_colors = []
        self.file_enabled_flags = [True] * len(file_names)

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
            for i, file_name in enumerate(file_names):
                dic, data = ng.pipe.read(file_name)
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

                short_name = os.path.basename(file_name)
                lbl = QLabel(short_name)
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

            self.dic = self.dic_list[0]
            self.raw_data = self.raw_data_list[0]
            ndim = self.raw_data.ndim
            order = self.dic.get('FDDIMORDER', [2, 1, 3, 4])
            is_1d = (ndim == 1)

            for key in ['base', 'scale', 'count']:
                lbl, sl, sb = self.cont_widgets[key]
                lbl.setEnabled(not is_1d)
                sl.setEnabled(not is_1d)
                sb.setEnabled(not is_1d)

            lbl, sl, sb = self.cont_widgets['offset']
            lbl.setEnabled(is_1d)
            sl.setEnabled(is_1d)
            sb.setEnabled(is_1d)

            if ndim == 1:
                orig_dim_x = int(order[0]) if len(order) > 0 else 2
                self.label_x = self.dic.get(f'FDF{orig_dim_x}LABEL', '1H')
                self.label_y = "Intensity"
                self.label_z = None

                uc_x = ng.pipe.make_uc(self.dic, self.raw_data, dim=0)
                self.ppm_x, self.lim_x = uc_x.ppm_scale(), uc_x.ppm_limits()
                self.ppm_y, self.lim_y = None, None
                self.x_dim = 0
                self.y_dim = None
                self.z_dim = None
                self.nz = 1
                self.slice_x_idx = 0

                self.plot_2d.setLabel('bottom', self.label_x, units="ppm")
                self.plot_2d.setLabel('left', self.label_y, units="")
                self.plot_2d.getViewBox().invertY(False)

            elif ndim == 3:
                self.z_dim = 0
                self.y_dim = 1
                self.x_dim = 2

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
                self.y_dim = 0
                self.x_dim = 1

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
                
            for idx in range(len(file_names)):
                if is_1d:
                    c_pos, _ = self.spectrum_colors[idx]
                    curve = pg.PlotDataItem(pen=pg.mkPen(c_pos, width=1), autoDownsample=True, clipToView=True)
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

            if len(file_names) == 1:
                self.lbl_info.setText(f"Loaded {len(file_names)} spectrum")
            else:
                self.lbl_info.setText(f"Loaded {len(file_names)} spectra")

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

            self._update_enabled_state()
            self.recompute_contours()
            self.set_mode(None)

            if ndim == 1:
                self.plot_2d.setXRange(self.lim_x[0], self.lim_x[1])
                self.plot_2d.autoRange(padding=0.05)
            else:
                self.plot_2d.setXRange(self.lim_x[0], self.lim_x[1])
                self.plot_2d.setYRange(self.lim_y[0], self.lim_y[1])

        except Exception as e:
            self.lbl_info.setText(f"Error loading files: {e}")

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

    def on_file_toggled(self, index, enabled):
        self.file_enabled_flags[index] = enabled
        if self.raw_data is not None:
            self._update_enabled_state()
            self.recompute_contours()

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

    def on_phase_changed(self, key, val):
        self.phase_state[self.active_axis][key] = val
        if self.raw_data is not None and self.raw_data.ndim == 1:
            self.recompute_contours()
        else:
            self.update_live_trace()

    def get_phase_vals(self, axis):
        return self.phase_state[axis]['p0'], self.phase_state[axis]['p1']

    def update_live_trace(self):
        if self.current_mode not in ['x_phase', 'y_phase', 'z_phase'] or self.current_slice is None:
            return
        y_idx = np.argmin(np.abs(self.ppm_y - self.h_pos)) if hasattr(self, 'ppm_y') and self.ppm_y is not None else 0
        x_idx = np.argmin(np.abs(self.ppm_x - self.v_pos))
        view_box = self.plot_2d.getViewBox()
        view_x_range, view_y_range = view_box.viewRange()
        x_p0, x_p1 = self.get_phase_vals('x')
        y_p0, y_p1 = self.get_phase_vals('y')
        z_p0, z_p1 = self.get_phase_vals('z') if self.nz > 1 else (0, 0)
        is_real = not np.iscomplexobj(self.raw_data)

        if self.current_mode == 'x_phase':
            trace = self.current_slice[:, y_idx] if self.slice_x_idx == 0 else self.current_slice[y_idx, :]
            if is_real: trace = hilbert(trace)
            trace = np.real(ng.process.proc_base.ps(trace, p0=x_p0, p1=x_p1))
            y_mid = (view_y_range[0] + view_y_range[1]) / 2.0
            scale = (abs(view_y_range[1] - view_y_range[0]) * 0.25) / (np.max(np.abs(trace)) + 1e-9)
            self.trace_curve.setData(self.ppm_x, y_mid - (trace * scale))

        elif self.current_mode == 'y_phase':
            trace = self.current_slice[x_idx, :] if self.slice_x_idx == 0 else self.current_slice[:, x_idx]
            if is_real: trace = hilbert(trace)
            trace = np.real(ng.process.proc_base.ps(trace, p0=y_p0, p1=y_p1))
            x_mid = (view_x_range[0] + view_x_range[1]) / 2.0
            scale = (abs(view_x_range[1] - view_x_range[0]) * 0.25) / (np.max(np.abs(trace)) + 1e-9)
            self.trace_curve.setData(x_mid + (trace * scale), self.ppm_y)

        elif self.current_mode == 'z_phase' and self.nz > 1:
            slices = [slice(None)] * 3
            slices[self.x_dim] = x_idx
            slices[self.y_dim] = y_idx
            trace = self.raw_data[tuple(slices)]
            if is_real: trace = hilbert(trace)
            trace = np.real(ng.process.proc_base.ps(trace, p0=z_p0, p1=z_p1))
            y_mid = (view_y_range[0] + view_y_range[1]) / 2.0
            scale = (abs(view_y_range[1] - view_y_range[0]) * 0.25) / (np.max(np.abs(trace)) + 1e-9)
            x_coords = np.linspace(view_x_range[0], view_x_range[1], self.nz)
            self.trace_curve.setData(x_coords, y_mid - (trace * scale))

    def recompute_contours(self):
        if not self.raw_data_list:
            return

        self.plot_2d.getViewBox().disableAutoRange()
        if not hasattr(self, 'vis_data_dict'):
            self.vis_data_dict = {}

        if not self.enabled_indices:
            self.trace_curve.setData([], [])
            for i in range(len(self.raw_data_list)):
                if self.raw_data.ndim == 1:
                    if self.file_curves_1d[i]: self.file_curves_1d[i].setVisible(False)
                else:
                    if self.file_groups[i]: self.file_groups[i].setVisible(False)
            return

        x_p0, x_p1 = self.get_phase_vals('x')
        y_p0, y_p1 = self.get_phase_vals('y')
        z_p0, z_p1 = self.get_phase_vals('z') if self.nz > 1 else (0, 0)
        
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
                plot_data = raw_data.copy()
                is_real = not np.iscomplexobj(raw_data)
                if x_p0 != 0 or x_p1 != 0:
                    if is_real: plot_data = hilbert(plot_data)
                    plot_data = np.real(ng.process.proc_base.ps(plot_data, p0=x_p0, p1=x_p1))
                else:
                    if not is_real: plot_data = np.real(plot_data)

                self.vis_data_dict[orig_i] = plot_data.copy()                
                
                y_data = plot_data + (idx * offset_val * (base_max * 0.1))
                c_pos, _ = self.spectrum_colors[orig_i % len(self.spectrum_colors)]
                
                curve.setData(x=self.ppm_x, y=y_data)
                curve.setPen(pg.mkPen(c_pos, width=1))
                curve.setVisible(True)
            return

        base_mult = self.cont_sliders['base'].value()
        scale_fact = self.cont_sliders['scale'].value()
        count = int(self.cont_sliders['count'].value())

        for orig_i in range(len(self.raw_data_list)):
            group = self.file_groups[orig_i]
            pool = self.file_pools_2d[orig_i]

            if orig_i not in self.enabled_indices:
                group.setVisible(False)
                continue

            group.setVisible(True)
            idx = self.enabled_indices.index(orig_i)
            c_slice = self.current_slice_list[idx]
            raw_data = self.raw_data_list[orig_i]  
            is_real = not np.iscomplexobj(raw_data)

            if raw_data.ndim == 3 and self.nz > 1 and (z_p0 != 0 or z_p1 != 0):
                tmp_data = raw_data.copy()
                if is_real: tmp_data = hilbert(tmp_data, axis=self.z_dim)
                tmp_data = np.swapaxes(tmp_data, self.z_dim, -1)
                tmp_data = ng.process.proc_base.ps(tmp_data, p0=z_p0, p1=z_p1)
                tmp_data = np.swapaxes(tmp_data, self.z_dim, -1)
                slices = [slice(None)] * 3
                slices[self.z_dim] = self.slider_z.value() - 1
                plot_data = np.real(tmp_data[tuple(slices)])
            else:
                plot_data = c_slice.copy()

            if x_p0 != 0 or x_p1 != 0:
                ax = 1 if self.slice_x_idx == 1 else 0
                if is_real: plot_data = hilbert(plot_data, axis=ax)
                if ax == 1: plot_data = np.real(ng.process.proc_base.ps(plot_data, p0=x_p0, p1=x_p1))
                else: plot_data = np.real(ng.process.proc_base.ps(plot_data.T, p0=x_p0, p1=x_p1).T)
            
            if y_p0 != 0 or y_p1 != 0:
                ax = 0 if self.slice_x_idx == 1 else 1
                if is_real: plot_data = hilbert(plot_data, axis=ax)
                if ax == 1: plot_data = np.real(ng.process.proc_base.ps(plot_data, p0=y_p0, p1=y_p1))
                else: plot_data = np.real(ng.process.proc_base.ps(plot_data.T, p0=y_p0, p1=y_p1).T)

            vis_data = plot_data.T if self.slice_x_idx == 1 else plot_data
            self.vis_data_dict[orig_i] = vis_data.copy()
            nx, ny = vis_data.shape
            
            ppm_x_span = self.ppm_x[-1] - self.ppm_x[0] if len(self.ppm_x) > 1 else 1.0
            ppm_y_span = self.ppm_y[-1] - self.ppm_y[0] if len(self.ppm_y) > 1 else 1.0
            scale_x = ppm_x_span / max(1, nx - 1)
            scale_y = ppm_y_span / max(1, ny - 1)
            
            tr = QTransform()
            tr.translate(self.ppm_x[0] - 0.5 * scale_x, self.ppm_y[0] - 0.5 * scale_y)
            tr.scale(scale_x, scale_y)
            group.setTransform(tr)
            
            noise_rmsd = self.calculate_rmsd(vis_data)
            base_level = noise_rmsd * base_mult
            
            factors = scale_fact ** np.arange(count)
            c_pos, c_neg = self.spectrum_colors[orig_i % len(self.spectrum_colors)]

            pos_levels = base_level * factors
            neg_levels = -base_level * factors
            
            v_max = vis_data.max()
            v_min = vis_data.min()
            pos_levels = [l for l in pos_levels if l <= v_max]
            neg_levels = [l for l in neg_levels if l >= v_min]

            all_levels = pos_levels + neg_levels
            is_pos = [True]*len(pos_levels) + [False]*len(neg_levels)

            pool_idx = 0
            for level, pos_flag in zip(all_levels, is_pos):
                pen_color = c_pos if pos_flag else c_neg
                pen = pg.mkPen(pen_color, width=1)
                
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
        
    def calculate_rmsd(self, data):
        flat_data = data.flatten()
        med = np.median(flat_data)
        mad = np.median(np.abs(flat_data - med))
        
        sigma = mad * 1.4826
        
        if sigma == 0:
            return np.std(flat_data)
        return sigma

    def refine_peak(self, click_ppm_x, click_ppm_y):
        if not self.enabled_indices or self.current_slice is None: 
            return

        orig_i = self.enabled_indices[0]
        if not hasattr(self, 'vis_data_dict') or orig_i not in self.vis_data_dict:
            return
            
        vis_data = self.vis_data_dict[orig_i]
        
        x_idx_center = np.argmin(np.abs(self.ppm_x - click_ppm_x))
        window = 5 

        if vis_data.ndim == 1:
            start_x = max(0, x_idx_center - window)
            end_x = min(len(self.ppm_x), x_idx_center + window + 1)
            
            local_data = vis_data[start_x:end_x]
            if local_data.size == 0: return
            
            center_idx = x_idx_center - start_x
            try:
                sign = 1 if local_data[center_idx] >= 0 else -1
            except IndexError:
                sign = 1
                
            max_loc = np.argmax(local_data) if sign > 0 else np.argmin(local_data)
            true_x_idx = start_x + max_loc

            offset = 0
            if 0 < true_x_idx < len(self.ppm_x) - 1:
                alpha = vis_data[true_x_idx - 1]
                beta = vis_data[true_x_idx]
                gamma = vis_data[true_x_idx + 1]
                denom = alpha - 2*beta + gamma
                if denom != 0:
                    offset = 0.5 * (alpha - gamma) / denom
            
            ppm_step = self.ppm_x[1] - self.ppm_x[0] if len(self.ppm_x) > 1 else 0
            refined_ppm_x = self.ppm_x[true_x_idx] + offset * ppm_step
            
            self.peak_counter += 1
            self.picked_peaks.append({'id': self.peak_counter, 'ppm_x': refined_ppm_x, 'ppm_y': click_ppm_y})
            self.update_peak_markers()

        elif vis_data.ndim == 2:
            y_idx_center = np.argmin(np.abs(self.ppm_y - click_ppm_y))
            
            start_x = max(0, x_idx_center - window)
            end_x = min(len(self.ppm_x), x_idx_center + window + window + 1)
            start_y = max(0, y_idx_center - window)
            end_y = min(len(self.ppm_y), y_idx_center + window + 1)

            local_data = vis_data[start_x:end_x, start_y:end_y]
            if local_data.size == 0: return

            center_x_local = x_idx_center - start_x
            center_y_local = y_idx_center - start_y
            try:
                sign = 1 if local_data[center_x_local, center_y_local] >= 0 else -1
            except IndexError:
                sign = 1

            if sign > 0:
                max_idx = np.unravel_index(np.argmax(local_data), local_data.shape)
            else:
                max_idx = np.unravel_index(np.argmin(local_data), local_data.shape)

            true_x_idx = start_x + max_idx[0]
            true_y_idx = start_y + max_idx[1]

            offset_x = 0
            if 0 < true_x_idx < len(self.ppm_x) - 1:
                alpha = vis_data[true_x_idx - 1, true_y_idx]
                beta  = vis_data[true_x_idx, true_y_idx]
                gamma = vis_data[true_x_idx + 1, true_y_idx]
                denom = alpha - 2*beta + gamma
                if denom != 0: offset_x = 0.5 * (alpha - gamma) / denom

            offset_y = 0
            if 0 < true_y_idx < len(self.ppm_y) - 1:
                alpha = vis_data[true_x_idx, true_y_idx - 1]
                beta  = vis_data[true_x_idx, true_y_idx]
                gamma = vis_data[true_x_idx, true_y_idx + 1]
                denom = alpha - 2*beta + gamma
                if denom != 0: offset_y = 0.5 * (alpha - gamma) / denom

            ppm_step_x = self.ppm_x[1] - self.ppm_x[0] if len(self.ppm_x) > 1 else 0
            ppm_step_y = self.ppm_y[1] - self.ppm_y[0] if len(self.ppm_y) > 1 else 0

            refined_ppm_x = self.ppm_x[true_x_idx] + offset_x * ppm_step_x
            refined_ppm_y = self.ppm_y[true_y_idx] + offset_y * ppm_step_y

            self.peak_counter += 1
            self.picked_peaks.append({'id': self.peak_counter, 'ppm_x': refined_ppm_x, 'ppm_y': refined_ppm_y})
            self.update_peak_markers()
            
    def update_peak_markers(self):
        spots = []
        current_ids = set()
        
        for p in self.picked_peaks:
            pid = p['id']
            current_ids.add(pid)
            spots.append({'pos': (p['ppm_x'], p['ppm_y']), 'data': pid})

            if pid not in self.peak_text_items:
                text_item = pg.TextItem(text=str(pid), color=(0, 0, 0), anchor=(-0.2, 0.5)) 
                text_item.setPos(p['ppm_x'], p['ppm_y'])
                self.plot_2d.addItem(text_item)
                self.peak_text_items[pid] = text_item

        self.peaks_scatter.setData(spots)

        ids_to_remove = set(self.peak_text_items.keys()) - current_ids
        for pid in ids_to_remove:
            self.plot_2d.removeItem(self.peak_text_items[pid])
            del self.peak_text_items[pid]

    def delete_nearest_peak(self, click_x, click_y):
        if not self.picked_peaks:
            return
            
        vb = self.plot_2d.getViewBox()
        x_range, y_range = vb.viewRange()
        dx_scale = max(abs(x_range[1] - x_range[0]), 1e-6)
        dy_scale = max(abs(y_range[1] - y_range[0]), 1e-6)
        
        best_idx = -1
        min_dist = float('inf')
        
        for i, p in enumerate(self.picked_peaks):
            dx = (p['ppm_x'] - click_x) / dx_scale
            dy = (p['ppm_y'] - click_y) / dy_scale
            dist = dx**2 + dy**2
            if dist < min_dist:
                min_dist = dist
                best_idx = i
                
        if min_dist < 0.01 and best_idx != -1:
            del self.picked_peaks[best_idx]
            self.update_peak_markers()

    def renumber_peaks(self):
        if not self.picked_peaks:
            self.plot_2d.setTitle("No peaks to renumber.")
            return
            
        # Clear existing text items from the plot to prevent overlapping numbers
        for pid, text_item in self.peak_text_items.items():
            self.plot_2d.removeItem(text_item)
        self.peak_text_items.clear()
        
        # Renumber sequentially
        for i, p in enumerate(self.picked_peaks):
            p['id'] = i + 1
            
        # Update the global counter to match the new highest ID
        self.peak_counter = len(self.picked_peaks)
        
        # Redraw markers with the newly assigned IDs
        self.update_peak_markers()
        self.plot_2d.setTitle("Success: Peaks renumbered sequentially.")
        
    def show_help_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("NMRdraw_lite Shortcuts")
        dlg.setFixedSize(600, 450) 
        
        layout = QVBoxLayout(dlg)
        
        help_text = """
        <div style='font-size: 12px; line-height: 1.4;'>
            <h3>NMRdraw_lite Shortcuts</h3>
            <table width="100%">
                <tr><td width="120"><b>h</b></td><td>Show this help message</td></tr>
                <tr><td><b>p</b></td><td>Peak Pick mode (Click near a peak to snap to max/min)</td></tr>
                <tr><td><b>Shift + p</b></td><td>Force pick peak exactly at current crosshair</td></tr>
                <tr><td><b>d</b></td><td>Peak Delete mode (Click near a peak to remove)</td></tr>
                <tr><td><b>Shift + r</b></td><td>Renumber peaks sequentially</td></tr>
                <tr><td><b>s</b></td><td>Save peak list to file</td></tr>
                <tr><td><b>x, y, z</b></td><td>Phase along respective axis</td></tr>
                <tr><td><b>Esc</b></td><td>Exit current mode / return to default</td></tr>
            </table>
            <hr>
            <h3>Mouse Controls</h3>
            <table width="100%">
                <tr><td width="120"><b>Alt + Left Drag</b></td><td>Pan spectrum (simulates Middle-Click)</td></tr>
                <tr><td><b>Right Click</b></td><td>Hide crosshairs</td></tr>
            </table>
        </div>
        """
        
        lbl = QLabel(help_text)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setWordWrap(True)
        layout.addWidget(lbl)
        
        btn = QPushButton("Close")
        btn.clicked.connect(dlg.accept)
        layout.addWidget(btn)
        
        dlg.exec()
                
    def create_menus(self):
        menubar = self.menuBar()
        # Ensures the menu is rendered in the macOS top system menubar
        menubar.setNativeMenuBar(True) 

        # --- File Menu ---
        file_menu = menubar.addMenu("File")
        
        save_peaks_action = QAction("Save Peaks", self)
        save_peaks_action.setShortcut("s")
        save_peaks_action.triggered.connect(self.save_peaks)
        file_menu.addAction(save_peaks_action)
        
        # New Export Sub-menu
        export_menu = file_menu.addMenu("Export")
        
        export_spectrum_action = QAction("Spectrum", self)
        export_spectrum_action.triggered.connect(self.export_spectrum)
        export_menu.addAction(export_spectrum_action)
        
        export_peaks_action = QAction("Peaks + Spectrum", self)
        export_peaks_action.triggered.connect(self.export_peaks_spectrum)
        export_menu.addAction(export_peaks_action)
        
                
        # --- Peaks Menu ---
        peaks_menu = menubar.addMenu("Peaks")
        
        auto_pick_action = QAction("Auto Pick", self)
        auto_pick_action.triggered.connect(self.auto_pick)
        peaks_menu.addAction(auto_pick_action)
        
        pick_peaks_action = QAction("Pick Peaks", self)
        pick_peaks_action.setShortcut("p")
        pick_peaks_action.triggered.connect(lambda: self.set_mode('peak_pick'))
        peaks_menu.addAction(pick_peaks_action)
        
        force_pick_action = QAction("Force Pick", self)
        force_pick_action.setShortcut("Shift+P")
        force_pick_action.triggered.connect(self.force_pick)
        peaks_menu.addAction(force_pick_action)

        # New Show/Hide Actions
        show_peaks_action = QAction("Show Peaks", self)
        show_peaks_action.setShortcut("Shift+S")
        show_peaks_action.triggered.connect(self.show_peaks)
        peaks_menu.addAction(show_peaks_action)
        
        hide_peaks_action = QAction("Hide Peaks", self)
        hide_peaks_action.setShortcut("Shift+H")
        hide_peaks_action.triggered.connect(self.hide_peaks)
        peaks_menu.addAction(hide_peaks_action)
        
        delete_peaks_action = QAction("Delete Peaks", self)
        delete_peaks_action.setShortcut("d")
        delete_peaks_action.triggered.connect(lambda: self.set_mode('peak_delete'))
        peaks_menu.addAction(delete_peaks_action)
        
        renumber_peaks_action = QAction("Renumber Peaks", self)
        renumber_peaks_action.setShortcut("Shift+R")
        renumber_peaks_action.triggered.connect(self.renumber_peaks)
        peaks_menu.addAction(renumber_peaks_action)
        
        peaks_menu.addAction(save_peaks_action)
                
        # --- Extras Menu ---
        extras_menu = menubar.addMenu("Extras")
        
        help_action = QAction("Help", self)
        help_action.setShortcut("h")
        help_action.triggered.connect(self.show_help_dialog)
        extras_menu.addAction(help_action)
        
    def export_spectrum(self):
        self._export_with_mode('spectrum')

    def export_peaks_spectrum(self):
        self._export_with_mode('peaks')

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
        
                        
    def auto_pick(self):
        # Placeholder for future development
        QMessageBox.information(self, "Feature in Progress", "Auto Peak Picking will be implemented in a future update.")

    def force_pick(self):
        if self.raw_data is not None:
            if self.current_mode != 'peak_pick':
                self.set_mode('peak_pick')
            self.peak_counter += 1
            self.picked_peaks.append({'id': self.peak_counter, 'ppm_x': self.v_pos, 'ppm_y': self.h_pos})
            self.update_peak_markers()
            
    def save_peaks(self):
        if not self.picked_peaks:
            self.plot_2d.setTitle("No peaks to save.")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Peaks", "peaks.txt", "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                ndim = self.raw_data.ndim if self.raw_data is not None else 0
                
                # Helper function to calculate exact fractional point
                def calc_pt(ppm_val, ppm_array):
                    if ppm_array is None or len(ppm_array) <= 1: return 0.0
                    return (ppm_val - ppm_array[0]) / (ppm_array[-1] - ppm_array[0]) * (len(ppm_array) - 1)

                with open(file_path, "w") as f:
                    if ndim == 1:
                        f.write(f"Index\t{self.label_x}_ppm\t{self.label_x}_pt\n")
                        for p in self.picked_peaks:
                            pt_x = calc_pt(p['ppm_x'], self.ppm_x)
                            f.write(f"{p['id']}\t{p['ppm_x']:.5f}\t{pt_x:.5f}\n")
                    else:
                        f.write(f"Index\t{self.label_x}_ppm\t{self.label_y}_ppm\t{self.label_x}_pt\t{self.label_y}_pt\n")
                        for p in self.picked_peaks:
                            pt_x = calc_pt(p['ppm_x'], self.ppm_x)
                            pt_y = calc_pt(p['ppm_y'], self.ppm_y)
                            f.write(f"{p['id']}\t{p['ppm_x']:.5f}\t{p['ppm_y']:.5f}\t{pt_x:.5f}\t{pt_y:.5f}\n")
                self.plot_2d.setTitle(f"Success: Picked peaks saved to {os.path.basename(file_path)}")
            except Exception as e:
                self.plot_2d.setTitle(f"Error saving peaks: {e}")                

    def show_peaks(self):
        self.peaks_scatter.setVisible(True)
        for item in self.peak_text_items.values():
            item.setVisible(True)

    def hide_peaks(self):
        self.peaks_scatter.setVisible(False)
        for item in self.peak_text_items.values():
            item.setVisible(False)
                                                    
if __name__ == "__main__":
    app = QApplication(sys.argv)
    passed_files = [f for f in sys.argv[1:] if os.path.isfile(f)]
    viewer = NMRViewerApp(file_paths=passed_files)
    viewer.show()
    sys.exit(app.exec())
