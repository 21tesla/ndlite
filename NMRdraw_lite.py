#!/opt/homebrew/Caskroom/miniconda/base/bin/python

import sys
import os
import numpy as np
import nmrglue as ng
from scipy.signal import hilbert
from PyQt6.QtGui import QTransform, QColor, QFont, QMouseEvent
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QGridLayout, QPushButton, QFileDialog,
                             QLabel, QSlider, QGroupBox, QDoubleSpinBox, QSpinBox,
                             QScrollArea, QColorDialog, QCheckBox)
from PyQt6.QtCore import Qt
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
        elif mode is None:
            self.grp_phase.setEnabled(False)
            self.grp_phase.setTitle("Phase Correction")
            self.trace_curve.setVisible(False)
            if self.raw_data is not None:
                if self.raw_data.ndim == 1:
                    self.hline.setVisible(False)
                    self.vline.setVisible(False)
                    self.plot_2d.setTitle("1D Mode. Press 'x' to phase.")
                else:
                    self.hline.setVisible(True)
                    self.vline.setVisible(True)
                    if self.raw_data.ndim == 2:
                        self.plot_2d.setTitle(f"{self.label_x}={self.v_pos:.3f}, {self.label_y}={self.h_pos:.3f} | Press 'x' or 'y' to phase.")
                    else:
                        self.plot_2d.setTitle(f"{self.label_x}={self.v_pos:.3f}, {self.label_y}={self.h_pos:.3f} | Press 'x', 'y', 'z' to phase.")
            else:
                self.hline.setVisible(False)
                self.vline.setVisible(False)
                self.plot_2d.setTitle("Please load a file.")

    def on_mouse_moved(self, pos):
        if self.current_mode is not None or self.raw_data is None or self.raw_data.ndim == 1:
            return
        view_box = self.plot_2d.getViewBox()
        if view_box.sceneBoundingRect().contains(pos):
            mouse_point = view_box.mapSceneToView(pos)
            self.h_pos = mouse_point.y()
            self.v_pos = mouse_point.x()
            self.hline.setPos(self.h_pos)
            self.vline.setPos(self.v_pos)
            self.hline.setVisible(True)
            self.vline.setVisible(True)
            if self.raw_data.ndim == 2:
                self.plot_2d.setTitle(f"{self.label_x}={self.v_pos:.3f}, {self.label_y}={self.h_pos:.3f} | Press 'x' or 'y' to phase.")
            else:
                self.plot_2d.setTitle(f"{self.label_x}={self.v_pos:.3f}, {self.label_y}={self.h_pos:.3f} | Press 'x', 'y', 'z' to phase.")
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

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.set_mode(None)
            return
        text = event.text().lower()
        ndim = self.raw_data.ndim if self.raw_data is not None else 0

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
            
        # Optimization: Clean up memory / object pools from previous loads
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
                
            # Initialize appropriate object pools per file
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

        # Optimization: Disable bounding box recalculations during heavy loop
        self.plot_2d.getViewBox().disableAutoRange()

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
                
                y_data = plot_data + (idx * offset_val * (base_max * 0.1))
                c_pos, _ = self.spectrum_colors[orig_i % len(self.spectrum_colors)]
                
                # Update item via pool instead of clearing plot
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
            nx, ny = vis_data.shape
            
            # Optimization: Assign Transform exclusively to ItemGroup (Matrix Batching)
            scale_x = (self.lim_x[1] - self.lim_x[0]) / max(1, nx - 1)
            scale_y = (self.lim_y[1] - self.lim_y[0]) / max(1, ny - 1)
            tr = QTransform()
            tr.translate(self.lim_x[0], self.lim_y[0])
            tr.scale(scale_x, scale_y)
            group.setTransform(tr)

            base_level = vis_data.std() * base_mult
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

            # Optimization: Re-using pooled instances to prevent allocation/garbage collection
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

            # Hide any trailing, unused items in the active pool
            for i in range(pool_idx, len(pool)):
                pool[i].setVisible(False)

        self.update_live_trace()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    passed_files = [f for f in sys.argv[1:] if os.path.isfile(f)]
    viewer = NMRViewerApp(file_paths=passed_files)
    viewer.show()
    sys.exit(app.exec())
