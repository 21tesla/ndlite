from PyQt6.QtWidgets import QFileDialog, QMessageBox, QWidget, QHBoxLayout, QCheckBox, QLabel, QPushButton, QColorDialog
from PyQt6.QtGui import QColor, QFont
import pyqtgraph as pg
import nmrglue as ng
import numpy as np
import os
from pathlib import Path
import json
from ndlite.core.models.spectrum_model import SpectrumModel
from ndlite.ui.dialogs import SettingsDialog

class IOController:
    def __init__(self, main_window):
        self.mw = main_window

    def load_preferences(self):
        
        # Store preferences in an OS-appropriate user directory
        app_dir = Path.home() / ".nmrdraw_lite"
        app_dir.mkdir(parents=True, exist_ok=True)
        self.mw.prefs_file = str(app_dir / "nmrdraw_preferences.json")

        
        self.mw.prefs = {
            "baseline_1d": {"min": 0.1, "max": 100.0, "default": 5.0, "step": 0.1},
            "phase_p0": {"min": -180.0, "max": 180.0, "step": 0.1},
            "phase_p1": {"min": -360.0, "max": 360.0, "step": 0.1},
            "controls": {
                "base": {"label": "Baseline Multiplier", "min": 0.05, "max": 50.0, "default": 4.0, "is_int": False},
                "scale": {"label": "Contour Multiplier", "min": 1.05, "max": 2.5, "default": 1.3, "is_int": False},
                "count": {"label": "Number of Contours", "min": 1, "max": 25, "default": 15, "is_int": True},
                "offset": {"label": "1D Stack Offset", "min": 0.0, "max": 4.0, "default": 0.0, "is_int": False}
            }
        }
        
        if os.path.exists(self.mw.prefs_file):
            try:
                with open(self.mw.prefs_file, 'r') as f:
                    user_prefs = json.load(f)
                    for key, val in user_prefs.items():
                        if isinstance(val, dict) and key in self.mw.prefs:
                            self.mw.prefs[key].update(val)
                        else:
                            self.mw.prefs[key] = val
            except Exception as e:
                print(f"Error loading preferences: {e}. Using default values.")
        else:
            try:
                with open(self.mw.prefs_file, 'w') as f:
                    json.dump(self.mw.prefs, f, indent=4)
            except Exception as e:
                print(f"Error generating preferences file: {e}")

    def open_settings_dialog(self):
        dlg = SettingsDialog(self.mw.prefs, self.mw.prefs_file, self.mw)
        dlg.exec()

    def load_file_dialog(self):
        file_names, _ = QFileDialog.getOpenFileNames(self.mw, "Open NMRPipe File(s)", "", "NMRPipe (*.ft *.ft1 *.ft2 *.ft3)")
        if file_names:
            self.load_files(file_names)

    def load_files(self, file_names):
        if not file_names:
            return
            
        if hasattr(self.mw, 'file_groups'):
            for g in self.mw.file_groups:
                if g is not None: self.mw.plot_2d.removeItem(g)
        if hasattr(self.mw, 'file_curves_1d'):
            for c in self.mw.file_curves_1d:
                if c is not None: self.mw.plot_2d.removeItem(c)

        self.mw.file_groups = []
        self.mw.file_pools_2d = []
        self.mw.file_curves_1d = []
        self.mw.dic_list = []
        self.mw.raw_data_list = []
        self.mw.spectrum_colors = []
        self.mw.file_enabled_flags = [True] * len(file_names)
        self.mw.baseline_corrections = [None] * len(file_names) 

        self.mw.data_list_widget.clear()

        default_colors = [
            ('#0000FF', '#FF0000'),
            ('#008000', '#FF00FF'),
            ('#00FFFF', '#FFA500'),
            ('#800080', '#FFFF00'),
            ('#000000', '#888888')
        ]

        try:
            for i, file_name in enumerate(file_names):
                dic, data = self.mw.data_handler.load_file(file_name)
                self.mw.dic_list.append(dic)
                self.mw.raw_data_list.append(data)
                
                c_pos, c_neg = default_colors[i % len(default_colors)]
                self.mw.spectrum_colors.append([c_pos, c_neg])

                model = SpectrumModel(file_name, dic, data, c_pos, c_neg)

                def make_toggle_cb(idx):
                    return lambda state: self.mw.on_file_toggled(idx, state)
                    
                def make_color_cb(idx, m):
                    def cb():
                        self.mw.spectrum_colors[idx] = [m.color_pos, m.color_neg]
                        self.mw.recompute_contours()
                    return cb

                self.mw.data_list_widget.add_spectrum(
                    model,
                    make_toggle_cb(i),
                    make_color_cb(i, model)
                )

            self.mw.dic = self.mw.dic_list[0]
            self.mw.raw_data = self.mw.raw_data_list[0]
            ndim = self.mw.raw_data.ndim
            order = self.mw.dic.get('FDDIMORDER', [2, 1, 3, 4])
            is_1d = (ndim == 1)

            # Instead of self.mw.display_controls.set_1d_mode(is_1d)
            for key in ['base', 'scale', 'count']:
                lbl, sl, sb = self.mw.cont_widgets[key]
                lbl.setEnabled(not is_1d)
                sl.setEnabled(not is_1d)
                sb.setEnabled(not is_1d)

            lbl, sl, sb = self.mw.cont_widgets['offset']
            lbl.setEnabled(is_1d)
            sl.setEnabled(is_1d)
            sb.setEnabled(is_1d)
            
            if hasattr(self.mw, 'one_d_menu') and hasattr(self.mw, 'two_d_menu'):
                self.mw.one_d_menu.menuAction().setVisible(is_1d)
                self.mw.two_d_menu.menuAction().setVisible(not is_1d)
            self.mw.baseline_1d_container.setVisible(is_1d)

            if ndim == 1:
                orig_dim_x = int(order[0]) if len(order) > 0 else 2
                self.mw.label_x = self.mw.dic.get(f'FDF{orig_dim_x}LABEL', '1H')
                self.mw.label_y = "Intensity"
                self.mw.label_z = None

                uc_x = ng.pipe.make_uc(self.mw.dic, self.mw.raw_data, dim=0)
                self.mw.ppm_x, self.mw.lim_x = uc_x.ppm_scale(), uc_x.ppm_limits()
                self.mw.ppm_y, self.mw.lim_y = None, None
                
                self.mw.x_dim, self.mw.y_dim, self.mw.z_dim = 0, None, None
                self.mw.nz = 1
                self.mw.slice_x_idx = 0

                self.mw.plot_2d.setLabel('bottom', self.mw.label_x, units="ppm")
                self.mw.plot_2d.setLabel('left', self.mw.label_y, units="")
                self.mw.plot_2d.getViewBox().invertY(False)

            elif ndim == 3:
                self.mw.z_dim, self.mw.y_dim, self.mw.x_dim = 0, 1, 2

                orig_dim_x = int(order[0]) if len(order) > 0 else 2
                orig_dim_y = int(order[1]) if len(order) > 1 else 3
                orig_dim_z = int(order[2]) if len(order) > 2 else 1

                self.mw.label_x = self.mw.dic.get(f'FDF{orig_dim_x}LABEL', 'X')
                self.mw.label_y = self.mw.dic.get(f'FDF{orig_dim_y}LABEL', 'Y')
                self.mw.label_z = self.mw.dic.get(f'FDF{orig_dim_z}LABEL', 'Z')

                uc_z = ng.pipe.make_uc(self.mw.dic, self.mw.raw_data, dim=self.mw.z_dim)
                uc_y = ng.pipe.make_uc(self.mw.dic, self.mw.raw_data, dim=self.mw.y_dim)
                uc_x = ng.pipe.make_uc(self.mw.dic, self.mw.raw_data, dim=self.mw.x_dim)

                self.mw.ppm_z, self.mw.lim_z = uc_z.ppm_scale(), uc_z.ppm_limits()
                self.mw.ppm_y, self.mw.lim_y = uc_y.ppm_scale(), uc_y.ppm_limits()
                self.mw.ppm_x, self.mw.lim_x = uc_x.ppm_scale(), uc_x.ppm_limits()
                self.mw.nz = self.mw.raw_data.shape[self.mw.z_dim]

                self.mw.plot_2d.setLabel('bottom', self.mw.label_x, units="ppm")
                self.mw.plot_2d.setLabel('left', self.mw.label_y, units="ppm")
                self.mw.plot_2d.getViewBox().invertY(True)

            else:
                self.mw.y_dim, self.mw.x_dim = 0, 1

                orig_dim_x = int(order[0]) if len(order) > 0 else 2
                orig_dim_y = int(order[1]) if len(order) > 1 else 1

                self.mw.label_x = self.mw.dic.get(f'FDF{orig_dim_x}LABEL', 'X')
                self.mw.label_y = self.mw.dic.get(f'FDF{orig_dim_y}LABEL', 'Y')

                uc_plot_y = ng.pipe.make_uc(self.mw.dic, self.mw.raw_data, dim=self.mw.y_dim)
                uc_plot_x = ng.pipe.make_uc(self.mw.dic, self.mw.raw_data, dim=self.mw.x_dim)

                self.mw.z_dim = None
                self.mw.label_z = None
                self.mw.nz = 1
                self.mw.ppm_x, self.mw.lim_x = uc_plot_x.ppm_scale(), uc_plot_x.ppm_limits()
                self.mw.ppm_y, self.mw.lim_y = uc_plot_y.ppm_scale(), uc_plot_y.ppm_limits()

                self.mw.plot_2d.setLabel('bottom', self.mw.label_x, units="ppm")
                self.mw.plot_2d.setLabel('left', self.mw.label_y, units="ppm")
                self.mw.plot_2d.getViewBox().invertY(True)

            if ndim > 1:
                self.mw.slice_x_idx = 1
                
            for idx in range(len(file_names)):
                if is_1d:
                    c_pos, _ = self.mw.spectrum_colors[idx]
                    curve = pg.PlotDataItem(pen=pg.mkPen(c_pos, width=1))
                    self.mw.plot_2d.addItem(curve)
                    self.mw.file_curves_1d.append(curve)
                    self.mw.file_groups.append(None)
                    self.mw.file_pools_2d.append(None)
                else:
                    group = pg.ItemGroup()
                    self.mw.plot_2d.addItem(group)
                    self.mw.file_groups.append(group)
                    self.mw.file_pools_2d.append([])
                    self.mw.file_curves_1d.append(None)

            if ndim > 1:
                self.mw.h_pos = (self.mw.lim_y[0] + self.mw.lim_y[1]) / 2.0
                self.mw.v_pos = (self.mw.lim_x[0] + self.mw.lim_x[1]) / 2.0
                self.mw.hline.setPos(self.mw.h_pos)
                self.mw.vline.setPos(self.mw.v_pos)

            if self.mw.nz > 1:
                self.mw.slider_z.blockSignals(True)
                self.mw.spinbox_z.blockSignals(True)
                
                self.mw.slider_z.setMinimum(1)
                self.mw.slider_z.setMaximum(self.mw.nz)
                self.mw.spinbox_z.setRange(1, self.mw.nz)
                self.mw.spinbox_z.setSingleStep(1)
                
                init_val = (self.mw.nz // 2) + 1
                self.mw.slider_z.setValue(init_val)
                self.mw.spinbox_z.setValue(init_val)
                
                self.mw.slider_z.blockSignals(False)
                self.mw.spinbox_z.blockSignals(False)
                
                self.mw.z_container.show()
                self.mw._update_z_label()
            else:
                self.mw.z_container.hide()

            self.mw.trace_curve.setData([], [])
            if hasattr(self.mw, 'baseline_anchors'):
                self.mw.baseline_anchors.clear()
                self.mw.baseline_scatter.setData([])

            self.mw.phase_state = {
                'x': {'p0': 0.0, 'p1': 0.0},
                'y': {'p0': 0.0, 'p1': 0.0},
                'z': {'p0': 0.0, 'p1': 0.0}
            }
            if hasattr(self.mw, 'active_axis') and self.mw.active_axis:
                self.mw.update_phase_ui_from_state()

            self.mw._update_enabled_state()
            self.mw.recompute_contours()
            self.mw.set_mode(None)

            if ndim == 1:
                self.mw.plot_2d.setXRange(float(self.mw.lim_x[0]), float(self.mw.lim_x[1]))
                y_min = float(np.min(self.mw.raw_data))
                y_max = float(np.max(self.mw.raw_data))
                y_pad = abs(y_max - y_min) * 0.05 if y_max != y_min else 1.0
                self.mw.plot_2d.setYRange(y_min - y_pad, y_max + y_pad)
            else:
                self.mw.plot_2d.setXRange(float(self.mw.lim_x[0]), float(self.mw.lim_x[1]))
                self.mw.plot_2d.setYRange(float(self.mw.lim_y[0]), float(self.mw.lim_y[1]))

        except Exception as e:
            QMessageBox.critical(self.mw, "Error Loading Data", f"An error occurred while loading files:\n{e}")
