from PyQt6.QtWidgets import QFileDialog, QMessageBox, QWidget, QHBoxLayout, QVBoxLayout, QCheckBox, QLabel, QPushButton, QColorDialog, QDialog, QComboBox
from PyQt6.QtGui import QColor, QFont, QFontDatabase
from PyQt6.QtCore import Qt
import pyqtgraph as pg
import nmrglue as ng
import numpy as np
import os
import subprocess
import tempfile
from pathlib import Path
import json
from ndlite.core.models.spectrum_model import SpectrumModel
from ndlite.ui.dialogs import SettingsDialog

from ndlite.core.peak_manager import PeakManager

class SpectrumInfoDialog(QDialog):
    def __init__(self, io_controller, parent=None):
        super().__init__(parent)
        self.io_controller = io_controller
        self.setWindowTitle("Spectrum Info")
        self.resize(600, 400)
        
        layout = QVBoxLayout(self)
        
        self.combo_box = QComboBox()
        for i in range(len(self.io_controller.mw.raw_data_list)):
            file_path = self.io_controller.mw.file_paths_list[i]
            model_name = os.path.basename(file_path)
            self.combo_box.addItem(model_name, userData=i)
            
        self.combo_box.currentIndexChanged.connect(self.update_info)
        layout.addWidget(self.combo_box)
        
        self.info_label = QLabel()
        
        fixed_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        fixed_font.setPointSize(10)
        self.info_label.setFont(fixed_font)
        
        self.info_label.setTextFormat(Qt.TextFormat.RichText)
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.info_label)
        
        # Select the initially enabled one, if any
        if hasattr(self.io_controller.mw, 'enabled_indices') and self.io_controller.mw.enabled_indices:
            start_index = self.io_controller.mw.enabled_indices[0]
            self.combo_box.setCurrentIndex(start_index)
            self.update_info(start_index)
        else:
            self.combo_box.setCurrentIndex(0)
            self.update_info(0)

    def update_info(self, index):
        if index < 0 or index >= len(self.io_controller.mw.raw_data_list):
            return
            
        dic = self.io_controller.mw.dic_list[index]
        data = self.io_controller.mw.raw_data_list[index]
        model = self.combo_box.itemText(index)

        ndim = int(dic.get('FDDIMCOUNT', data.ndim))
        
        # Determine 2DMODE
        fd2dphase = dic.get('FD2DPHASE', 0.0)
        mode_2d_str = "States" if fd2dphase == 2.0 else ("TPPI" if fd2dphase == 1.0 else ("Sequential" if fd2dphase == 0.0 else str(fd2dphase)))
        transposed_str = "Transposed" if dic.get('FDTRANSPOSED', 0.0) == 1.0 else "Not Transposed"
        
        quad_flag = dic.get('FDQUADFLAG', 0.0)
        quad_str = "Real" if quad_flag == 1.0 else ("Complex" if quad_flag == 0.0 else str(quad_flag))

        pipe_flag = int(dic.get('FDPIPEFLAG', 0.0))
        cube_flag = int(dic.get('FDCUBEFLAG', 0.0))
        file_count = int(dic.get('FDFILECOUNT', 1.0))

        # Reconstruct size like 710x96x80x1
        dim_sizes = []
        if ndim >= 1: dim_sizes.append(str(int(dic.get('FDSIZE', data.shape[-1]))))
        if ndim >= 2: dim_sizes.append(str(int(dic.get('FDSPECNUM', data.shape[-2] if data.ndim > 1 else 1))))
        if ndim >= 3: dim_sizes.append(str(int(dic.get('FDF3SIZE', data.shape[-3] if data.ndim > 2 else 1))))
        if ndim >= 4: dim_sizes.append(str(int(dic.get('FDF4SIZE', data.shape[-4] if data.ndim > 3 else 1))))
        while len(dim_sizes) < 4: dim_sizes.append("1")
        shape_str = "x".join(dim_sizes)
        
        is_stream = "3D Stream" if ndim == 3 and pipe_flag == 1 else ("2D Stream" if ndim == 2 and pipe_flag == 1 else "")

        # Extract dimension order from FDDIMORDER parameters
        dim_order_list = []
        for i in range(1, 5):
             val = dic.get(f'FDDIMORDER{i}')
             if val is not None:
                  dim_order_list.append(str(int(val)))
             elif dic.get('FDDIMORDER') is not None and i <= len(dic.get('FDDIMORDER')):
                  dim_order_list.append(str(int(dic['FDDIMORDER'][i-1])))
        
        dim_order_str = " ".join(dim_order_list[:ndim]) if dim_order_list else "Unknown"

        info_text = f"<pre>"
        info_text += f"FILE: {model}  DIM: {ndim}  QUAD: {quad_str}  2DMODE: {mode_2d_str} {transposed_str}\n"
        info_text += f"ORDER: {dim_order_str}  PIPE: {pipe_flag}  CUBE: {cube_flag}  FILES: {file_count}  {shape_str}  {is_stream}\n\n"
        info_text += f"               {'X-Axis':<14}{'Y-Axis':<14}{'Z-Axis':<14}\n\n"
        
        axes_data = []
        for i in range(3):
             if i < len(dim_order_list):
                  fdf_idx = dim_order_list[i]
             else:
                  fdf_idx = str(i+1) # Fallback
                  
             axes_data.append({
                 'size': dic.get(f'FDF{fdf_idx}FTSIZE', 0.0),
                 'apod': dic.get(f'FDF{fdf_idx}TDSIZE', 0.0),
                 'sw': dic.get(f'FDF{fdf_idx}SW', 0.0),
                 'obs': dic.get(f'FDF{fdf_idx}OBS', 0.0),
                 'orig': dic.get(f'FDF{fdf_idx}ORIG', 0.0),
                 'domain': "Freq" if dic.get(f'FDF{fdf_idx}FTFLAG', 0.0) == 1.0 else "Time",
                 'mode': "Real" if dic.get(f'FDF{fdf_idx}QUADFLAG', 0.0) == 1.0 else "Complex",
                 'name': dic.get(f'FDF{fdf_idx}LABEL', 'None')
             })

        def format_row(label, key, fmt):
             row = f"{label:<13}"
             for i in range(min(ndim, 3)):
                  val = axes_data[i][key]
                  if isinstance(val, float):
                       row += f"{val:{fmt}} "
                  elif isinstance(val, str):
                       row += f"{val:>13} "
             return row + "\n"

        info_text += format_row("DATA SIZE:", 'size', '>13.0f')
        info_text += format_row("APOD SIZE:", 'apod', '>13.0f')
        info_text += format_row("SW Hz:", 'sw', '>13.6f')
        info_text += format_row("OBS MHz:", 'obs', '>13.6f')
        info_text += format_row("ORIG Hz:", 'orig', '>13.6f')
        info_text += format_row("DOMAIN:", 'domain', '')
        info_text += format_row("MODE:", 'mode', '')
        info_text += format_row("NAME:", 'name', '')

        info_text += "</pre>"
        self.info_label.setText(info_text)

class IOController:
    def __init__(self, main_window):
        self.mw = main_window

    def load_preferences(self):
        
        # Store preferences in an OS-appropriate user directory
        app_dir = Path.home() / ".ndlite"
        app_dir.mkdir(parents=True, exist_ok=True)
        self.mw.prefs_file = str(app_dir / "ndlite_preferences.json")

        
        self.mw.prefs = {
            "baseline_1d": {"min": 0.1, "max": 100.0, "default": 5.0, "step": 0.1},
            "phase_p0": {"min": -180.0, "max": 180.0, "step": 0.1},
            "phase_p1": {"min": -360.0, "max": 360.0, "step": 0.1},
            "linewidth": 0.25,
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

    def install_cli(self):
        import sys
        if sys.platform != "darwin":
            return

        source_path = sys.executable
        target_path = "/usr/local/bin/ndlite"
        
        # Verify we are in a .app bundle
        if ".app" in source_path:
             app_dir = source_path.split(".app")[0] + ".app"
             potential_bin = os.path.join(app_dir, "Contents", "MacOS", "ndlite")
             if os.path.exists(potential_bin):
                 source_path = potential_bin
        else:
             # Fallback to the user suggested path if we are not sure but on darwin
             source_path = "/Applications/ndlite.app/Contents/MacOS/ndlite"
             if not os.path.exists(source_path):
                 QMessageBox.warning(self.mw, "CLI Installation", "This feature is only available when running ndlite as a macOS Application bundle.")
                 return

        # Create a shell script wrapper instead of a symlink
        # This ensures the binary can find its Info.plist relative to its real location.
        # We use a python one-liner to normalize all file paths to absolute paths
        # before passing them to the app.
        wrapper_content = f"""#!/bin/bash
# Normalize all arguments that are files to absolute paths
declare -a ABS_ARGS
for arg in "$@"; do
    if [[ -f "$arg" ]]; then
        ABS_ARGS+=("$(python3 -c 'import os, sys; print(os.path.abspath(sys.argv[1]))' "$arg")")
    else
        ABS_ARGS+=("$arg")
    fi
done
exec "{source_path}" "${{ABS_ARGS[@]}}"
"""
        
        fd, temp_path = tempfile.mkstemp()
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(wrapper_content)
            
            # Use AppleScript to move and set permissions
            # We use 'quoted form of' for the temp_path to handle spaces
            script = (
                f'do shell script "mkdir -p /usr/local/bin && '
                f'cp " & quoted form of "{temp_path}" & " {target_path} && '
                f'chmod 755 {target_path}" '
                f'with administrator privileges'
            )
            cmd = ["osascript", "-e", script]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                QMessageBox.information(self.mw, "CLI Installation", f"Successfully installed 'ndlite' to {target_path}.\n\nYou can now run 'ndlite' from the terminal.")
            else:
                if "User canceled" in result.stderr:
                    return
                QMessageBox.critical(self.mw, "CLI Installation", f"Failed to install command line version:\n{result.stderr}")
        except Exception as e:
            QMessageBox.critical(self.mw, "CLI Installation", f"An error occurred:\n{str(e)}")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def show_spectrum_info(self):
        if not self.mw.raw_data_list or not self.mw.dic_list:
            QMessageBox.information(self.mw, "Spectrum Info", "No spectrum loaded.")
            return

        dlg = SpectrumInfoDialog(self, self.mw)
        dlg.exec()

    def load_file_dialog(self):
        file_names, _ = QFileDialog.getOpenFileNames(self.mw, "Open NMRPipe File(s)", "", "NMRPipe (*.ft *.ft1 *.ft2 *.ft3)")
        if file_names:
            self.load_files(file_names)

    def add_file_dialog(self):
        file_names, _ = QFileDialog.getOpenFileNames(self.mw, "Add NMRPipe File(s)", "", "NMRPipe (*.ft *.ft1 *.ft2 *.ft3)")
        if file_names:
            self.add_files(file_names)

    def on_selection_changed(self, index):
        if 0 <= index < len(self.mw.raw_data_list):
            self.mw.active_index = index
            # Potentially update plot title or other UI elements to reflect active spectrum
            self.mw.plot_2d.setTitle(f"Active: {os.path.basename(self.mw.file_paths_list[index])}")

    def on_peak_toggled(self, index, enabled):
        if 0 <= index < len(self.mw.peak_enabled_flags):
            self.mw.peak_enabled_flags[index] = enabled
            self.mw.peak_controller.update_peak_markers()

    def remove_spectrum(self, index):
        if not (0 <= index < len(self.mw.raw_data_list)):
            return
            
        reply = QMessageBox.question(self.mw, 'Delete Spectrum', 
                                   f"Are you sure you want to remove this spectrum?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                   QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No:
            return

        # 1. Remove plot items
        if self.mw.file_groups[index] is not None:
            self.mw.plot_2d.removeItem(self.mw.file_groups[index])
        if self.mw.file_curves_1d[index] is not None:
            self.mw.plot_2d.removeItem(self.mw.file_curves_1d[index])
            
        if index < len(self.mw.peak_scatter_items) and self.mw.peak_scatter_items[index] is not None:
            self.mw.plot_2d.removeItem(self.mw.peak_scatter_items[index])
            for text_item in self.mw.peak_text_items[index].values():
                self.mw.plot_2d.removeItem(text_item)

        # 2. Pop from all lists
        self.mw.dic_list.pop(index)
        self.mw.raw_data_list.pop(index)
        self.mw.file_paths_list.pop(index)
        self.mw.spectrum_colors.pop(index)
        self.mw.file_enabled_flags.pop(index)
        self.mw.peak_enabled_flags.pop(index)
        self.mw.baseline_corrections.pop(index)
        self.mw.file_groups.pop(index)
        self.mw.file_pools_2d.pop(index)
        self.mw.file_curves_1d.pop(index)
        self.mw.peak_managers.pop(index)
        self.mw.peak_scatter_items.pop(index)
        self.mw.peak_text_items.pop(index)
        
        # 3. Update active pointers
        if not self.mw.raw_data_list:
            self.mw.dic = None
            self.mw.raw_data = None
            self.mw.current_slice = None
            self.mw.current_slice_list = []
            self.mw.enabled_indices = []
            self.mw.active_index = 0
            if hasattr(self.mw, 'menu_builder') and self.mw.menu_builder.add_spectrum_action:
                self.mw.menu_builder.add_spectrum_action.setEnabled(False)
            self.mw.plot_2d.setTitle("Please load a file.")
        else:
            self.mw.active_index = min(self.mw.active_index, len(self.mw.raw_data_list) - 1)
            self.mw.dic = self.mw.dic_list[0]
            self.mw.raw_data = self.mw.raw_data_list[0]
            
        # 4. Refresh the UI list (to fix closure indices)
        self.refresh_data_list()
        
        # 5. Recompute and update
        self.mw._update_enabled_state()
        self.mw.recompute_contours()
        self.mw.peak_controller.update_peak_markers()

    def refresh_data_list(self):
        self.mw.data_list_widget.clear()
        
        for i in range(len(self.mw.raw_data_list)):
            file_name = self.mw.file_paths_list[i]
            dic = self.mw.dic_list[i]
            data = self.mw.raw_data_list[i]
            c_pos, c_neg = self.mw.spectrum_colors[i]
            
            model = SpectrumModel(file_name, dic, data, c_pos, c_neg)
            model.enabled = self.mw.file_enabled_flags[i]
            model.peaks_enabled = self.mw.peak_enabled_flags[i]

            def create_callbacks(idx, m):
                toggle_cb = lambda state: self.mw.on_file_toggled(idx, state)
                peak_toggle_cb = lambda state: self.on_peak_toggled(idx, state)
                def color_cb():
                    self.mw.spectrum_colors[idx] = [m.color_pos, m.color_neg]
                    self.mw.recompute_contours()
                return toggle_cb, color_cb, peak_toggle_cb

            t_cb, c_cb, p_t_cb = create_callbacks(i, model)
            self.mw.data_list_widget.add_spectrum(model, t_cb, c_cb, p_t_cb)
        
        self.mw.data_list_widget.list_widget.setCurrentRow(self.mw.active_index)

    def add_files(self, file_names):
        if not file_names or not self.mw.raw_data_list:
            return

        current_ndim = self.mw.raw_data.ndim
        start_idx = len(self.mw.raw_data_list)
        
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
                
                if data.ndim != current_ndim:
                    QMessageBox.warning(self.mw, "Dimension Mismatch", f"Skipping {file_name}: Expected {current_ndim}D, got {data.ndim}D.")
                    continue

                self.mw.dic_list.append(dic)
                self.mw.raw_data_list.append(data)
                self.mw.file_paths_list.append(file_name)
                self.mw.file_enabled_flags.append(True)
                self.mw.peak_enabled_flags.append(True)
                self.mw.baseline_corrections.append(None)
                self.mw.peak_managers.append(PeakManager())
                self.mw.peak_scatter_items.append(None) # Will be created by update_peak_markers
                self.mw.peak_text_items.append({})
                
                c_idx = start_idx + i
                c_pos, c_neg = default_colors[c_idx % len(default_colors)]
                self.mw.spectrum_colors.append([c_pos, c_neg])

                model = SpectrumModel(file_name, dic, data, c_pos, c_neg)

                # Use a factory function to capture c_idx correctly in closures
                def create_callbacks(idx, m):
                    toggle_cb = lambda state: self.mw.on_file_toggled(idx, state)
                    peak_toggle_cb = lambda state: self.on_peak_toggled(idx, state)
                    def color_cb():
                        self.mw.spectrum_colors[idx] = [m.color_pos, m.color_neg]
                        self.mw.recompute_contours()
                    return toggle_cb, color_cb, peak_toggle_cb

                t_cb, c_cb, p_t_cb = create_callbacks(c_idx, model)
                self.mw.data_list_widget.add_spectrum(model, t_cb, c_cb, p_t_cb)

                if current_ndim == 1:
                    c_pos, _ = self.mw.spectrum_colors[c_idx]
                    curve = pg.PlotDataItem(pen=pg.mkPen(c_pos, width=self.mw.prefs.get('linewidth', 0.5)))
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

            self.mw._update_enabled_state()
            self.mw.recompute_contours()
            
        except Exception as e:
            QMessageBox.critical(self.mw, "Error Adding Data", f"An error occurred while adding files:\n{e}")

    def load_files(self, file_names):
        if not file_names:
            return
            
        if hasattr(self.mw, 'file_groups'):
            for g in self.mw.file_groups:
                if g is not None: self.mw.plot_2d.removeItem(g)
        if hasattr(self.mw, 'file_curves_1d'):
            for c in self.mw.file_curves_1d:
                if c is not None: self.mw.plot_2d.removeItem(c)
        
        if hasattr(self.mw, 'peak_scatter_items'):
            for scatter in self.mw.peak_scatter_items:
                if scatter is not None:
                    self.mw.plot_2d.removeItem(scatter)
        if hasattr(self.mw, 'peak_text_items'):
            for text_dict in self.mw.peak_text_items:
                for item in text_dict.values():
                    if item is not None:
                        self.mw.plot_2d.removeItem(item)

        self.mw.file_groups = []
        self.mw.file_pools_2d = []
        self.mw.file_curves_1d = []
        self.mw.dic_list = []
        self.mw.raw_data_list = []
        self.mw.file_paths_list = []
        self.mw.spectrum_colors = []
        self.mw.file_enabled_flags = [True] * len(file_names)
        self.mw.peak_enabled_flags = [True] * len(file_names)
        self.mw.baseline_corrections = [None] * len(file_names) 
        self.mw.peak_managers = [PeakManager() for _ in range(len(file_names))]
        self.mw.peak_scatter_items = []
        self.mw.peak_text_items = []
        self.mw.active_index = 0

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
                self.mw.file_paths_list.append(file_name)
                
                c_pos, c_neg = default_colors[i % len(default_colors)]
                self.mw.spectrum_colors.append([c_pos, c_neg])

                model = SpectrumModel(file_name, dic, data, c_pos, c_neg)

                def create_callbacks(idx, m):
                    toggle_cb = lambda state: self.mw.on_file_toggled(idx, state)
                    peak_toggle_cb = lambda state: self.on_peak_toggled(idx, state)
                    def color_cb():
                        self.mw.spectrum_colors[idx] = [m.color_pos, m.color_neg]
                        self.mw.recompute_contours()
                    return toggle_cb, color_cb, peak_toggle_cb

                t_cb, c_cb, p_t_cb = create_callbacks(i, model)
                self.mw.data_list_widget.add_spectrum(model, t_cb, c_cb, p_t_cb)

            self.mw.data_list_widget.list_widget.setCurrentRow(0)

            self.mw.dic = self.mw.dic_list[0]
            self.mw.raw_data = self.mw.raw_data_list[0]
            ndim = self.mw.raw_data.ndim

            # Enable "Add Spectrum" menu item
            if hasattr(self.mw, 'menu_builder') and self.mw.menu_builder.add_spectrum_action:
                self.mw.menu_builder.add_spectrum_action.setEnabled(True)

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
                    curve = pg.PlotDataItem(pen=pg.mkPen(c_pos, width=self.mw.prefs.get('linewidth', 0.5)))
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
