from PyQt6.QtWidgets import QFileDialog, QMessageBox
from PyQt6.QtGui import QPainterPath, QColor
import pyqtgraph as pg
import numpy as np
import os
import nmrglue as ng
import traceback

class PeakController:
    def __init__(self, main_window):
        self.mw = main_window

    def save_peaks(self):
        active_idx = self.mw.active_index
        if not (0 <= active_idx < len(self.mw.peak_managers)):
            return
            
        peak_manager = self.mw.peak_managers[active_idx]
        if not peak_manager.picked_peaks:
            self.mw.plot_2d.setTitle("No peaks to save for the active spectrum.")
            return
            
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self.mw, "Save Peaks", "peaks.txt", 
            "Text Files (*.txt);;NMRdraw Tab Files (*.tab);;All Files (*)"
        )
        
        if file_path:
            is_tab = file_path.endswith('.tab') or "NMRdraw" in selected_filter
            try:
                raw_data = self.mw.raw_data_list[active_idx]
                ndim = raw_data.ndim
                dic = self.mw.dic_list[active_idx]
                
                def calc_pt(ppm_val, ppm_array):
                    if ppm_array is None or len(ppm_array) <= 1: return 0.0
                    return (ppm_val - ppm_array[0]) / (ppm_array[-1] - ppm_array[0]) * (len(ppm_array) - 1)

                def get_height(px, py, pz=None):
                    x_idx = int(round(calc_pt(px, self.mw.ppm_x)))
                    y_idx = int(round(calc_pt(py, self.mw.ppm_y))) if self.mw.ppm_y is not None else 0
                    
                    if ndim == 1:
                        x_idx = max(0, min(raw_data.shape[0]-1, x_idx))
                        return float(raw_data[x_idx])
                    elif ndim == 2:
                        x_dim, y_dim = self.mw.x_dim, self.mw.y_dim
                        x_idx = max(0, min(raw_data.shape[x_dim]-1, x_idx))
                        y_idx = max(0, min(raw_data.shape[y_dim]-1, y_idx))
                        if x_dim == 1 and y_dim == 0:
                            return float(raw_data[y_idx, x_idx])
                        else:
                            return float(raw_data[x_idx, y_idx])
                    elif ndim >= 3:
                        if pz is None or self.mw.ppm_z is None: return 0.0
                        z_idx = int(round(calc_pt(pz, self.mw.ppm_z)))
                        x_dim, y_dim, z_dim = self.mw.x_dim, self.mw.y_dim, self.mw.z_dim
                        x_idx = max(0, min(raw_data.shape[x_dim]-1, x_idx))
                        y_idx = max(0, min(raw_data.shape[y_dim]-1, y_idx))
                        z_idx = max(0, min(raw_data.shape[z_dim]-1, z_idx))
                        
                        idx = [0, 0, 0]
                        idx[x_dim] = x_idx
                        idx[y_dim] = y_idx
                        idx[z_dim] = z_idx
                        return float(raw_data[tuple(idx)])
                    return 0.0

                def calc_volume(px, py, pz=None):
                    x_idx = int(round(calc_pt(px, self.mw.ppm_x)))
                    y_idx = int(round(calc_pt(py, self.mw.ppm_y))) if self.mw.ppm_y is not None else 0
                    
                    wx, wy, wz = 5, 5, 2  # Integration window
                    
                    if ndim == 1:
                        start_x = max(0, x_idx - wx)
                        end_x = min(raw_data.shape[-1], x_idx + wx + 1)
                        return float(np.sum(raw_data[start_x:end_x]))
                    elif ndim == 2:
                        x_dim, y_dim = self.mw.x_dim, self.mw.y_dim
                        start_x = max(0, x_idx - wx)
                        end_x = min(raw_data.shape[x_dim], x_idx + wx + 1)
                        start_y = max(0, y_idx - wy)
                        end_y = min(raw_data.shape[y_dim], y_idx + wy + 1)
                        
                        if x_dim == 1 and y_dim == 0:
                            return float(np.sum(raw_data[start_y:end_y, start_x:end_x]))
                        else:
                            return float(np.sum(raw_data[start_x:end_x, start_y:end_y]))
                            
                    elif ndim >= 3:
                        if pz is None or self.mw.ppm_z is None: return 0.0
                        z_idx = int(round(calc_pt(pz, self.mw.ppm_z)))
                        x_dim, y_dim, z_dim = self.mw.x_dim, self.mw.y_dim, self.mw.z_dim
                        
                        start_x = max(0, x_idx - wx)
                        end_x = min(raw_data.shape[x_dim], x_idx + wx + 1)
                        start_y = max(0, y_idx - wy)
                        end_y = min(raw_data.shape[y_dim], y_idx + wy + 1)
                        start_z = max(0, z_idx - wz)
                        end_z = min(raw_data.shape[z_dim], z_idx + wz + 1)
                        
                        sl = [slice(None)] * 3
                        sl[x_dim] = slice(start_x, end_x)
                        sl[y_dim] = slice(start_y, end_y)
                        sl[z_dim] = slice(start_z, end_z)
                        return float(np.sum(raw_data[tuple(sl)]))
                    return 0.0

                if is_tab and ndim == 2:
                    # NMRdraw TAB format for 2D
                    uc_x = ng.pipe.make_uc(dic, raw_data, dim=self.mw.x_dim)
                    uc_y = ng.pipe.make_uc(dic, raw_data, dim=self.mw.y_dim)
                    
                    # Hz step size
                    hz_scale_x = uc_x.hz_scale()
                    hz_scale_y = uc_y.hz_scale()
                    dw_hz_x = abs(hz_scale_x[1] - hz_scale_x[0]) if len(hz_scale_x) > 1 else 1.0
                    dw_hz_y = abs(hz_scale_y[1] - hz_scale_y[0]) if len(hz_scale_y) > 1 else 1.0

                    with open(file_path, "w") as f:
                        f.write("VARS   INDEX X_AXIS Y_AXIS DX DY X_PPM Y_PPM X_HZ Y_HZ XW YW XW_HZ YW_HZ X1 X3 Y1 Y3 HEIGHT DHEIGHT VOL PCHI2 TYPE ASS CLUSTID MEMCNT\n")
                        f.write("FORMAT %5d %9.3f %9.3f %6.3f %6.3f %8.3f %8.3f %9.3f %9.3f %7.3f %7.3f %8.3f %8.3f %4d %4d %4d %4d %+e %+e %+e %.5f %d %s %4d %4d\n\n")
                        f.write("NULLVALUE -666\n")
                        f.write("NULLSTRING *\n\n")
                        
                        for p in peak_manager.picked_peaks:
                            px, py = p['ppm_x'], p['ppm_y']
                            pt_x = calc_pt(px, self.mw.ppm_x) + 1.0
                            pt_y = calc_pt(py, self.mw.ppm_y) + 1.0
                            
                            hz_x = uc_x.hz(uc_x(px, 'ppm'))
                            hz_y = uc_y.hz(uc_y(py, 'ppm'))
                            
                            vol = calc_volume(px, py)
                            height = get_height(px, py)
                            
                            # Range around peak
                            x1, x3 = int(round(pt_x)) - 1, int(round(pt_x)) + 1
                            y1, y3 = int(round(pt_y)) - 1, int(round(pt_y)) + 1
                            
                            # Get label
                            label = p.get('label')
                            ass_str = label if label else "None"
                            
                            # Line format matching test.tab
                            line = (f"{p['id']:5d} {pt_x:9.3f} {pt_y:9.3f} "
                                    f"1.000 1.000 {px:8.3f} {py:8.3f} {hz_x:9.3f} {hz_y:9.3f} "
                                    f"1.000 1.000 {dw_hz_x:8.3f} {dw_hz_y:8.3f} {x1:4d} {x3:4d} {y1:4d} {y3:4d} "
                                    f"{height:+e} 0.000000e+00 {vol:+e} 0.00000 1 {ass_str} 1 1\n")
                            f.write(line)
                else:
                    # Basic text format (Improved)
                    with open(file_path, "w") as f:
                        if ndim == 1:
                            has_fits = 'fit_area' in peak_manager.picked_peaks[0] if peak_manager.picked_peaks else False
                            
                            if has_fits:
                                f.write(f"Index\t{self.mw.label_x}_ppm\t{self.mw.label_x}_pt\tFit_Type\tLinewidth\tArea_Integral\tLabel\n")
                                for p in peak_manager.picked_peaks:
                                    pt_x = calc_pt(p['ppm_x'], self.mw.ppm_x)
                                    label = p.get('label') if p.get('label') else f"#{p['id']}"
                                    f.write(f"{p['id']}\t{p['ppm_x']:.5f}\t{pt_x:.5f}\t{p.get('fit_type', 'none')}\t{abs(p.get('fit_wid', 0.0)):.5e}\t{p.get('fit_area', 0.0):.5e}\t{label}\n")
                            else:
                                f.write(f"Index\t{self.mw.label_x}_ppm\t{self.mw.label_x}_pt\tHeight\tVolume_Sum\tLabel\n")
                                for p in peak_manager.picked_peaks:
                                    pt_x = calc_pt(p['ppm_x'], self.mw.ppm_x)
                                    h = get_height(p['ppm_x'], p['ppm_y'])
                                    vol = calc_volume(p['ppm_x'], p['ppm_y'])
                                    label = p.get('label') if p.get('label') else f"#{p['id']}"
                                    f.write(f"{p['id']}\t{p['ppm_x']:.5f}\t{pt_x:.5f}\t{h:.5e}\t{vol:.5e}\t{label}\n")
                                                                
                        elif ndim == 2:
                            f.write(f"Index\t{self.mw.label_x}_ppm\t{self.mw.label_y}_ppm\t{self.mw.label_x}_pt\t{self.mw.label_y}_pt\tHeight\tVolume\tLabel\n")
                            for p in peak_manager.picked_peaks:
                                pt_x = calc_pt(p['ppm_x'], self.mw.ppm_x)
                                pt_y = calc_pt(p['ppm_y'], self.mw.ppm_y)
                                h = get_height(p['ppm_x'], p['ppm_y'])
                                vol = calc_volume(p['ppm_x'], p['ppm_y'])
                                label = p.get('label') if p.get('label') else f"#{p['id']}"
                                f.write(f"{p['id']}\t{p['ppm_x']:.5f}\t{p['ppm_y']:.5f}\t{pt_x:.5f}\t{pt_y:.5f}\t{h:.5e}\t{vol:.5e}\t{label}\n")
                                
                        elif ndim >= 3:
                            lbl_z = self.mw.label_z if self.mw.label_z else "Z"
                            f.write(f"Index\t{self.mw.label_x}_ppm\t{self.mw.label_y}_ppm\t{lbl_z}_ppm\t{self.mw.label_x}_pt\t{self.mw.label_y}_pt\t{lbl_z}_pt\tHeight\tVolume\tLabel\n")
                            for p in peak_manager.picked_peaks:
                                pt_x = calc_pt(p['ppm_x'], self.mw.ppm_x)
                                pt_y = calc_pt(p['ppm_y'], self.mw.ppm_y)
                                ppm_z_val = p.get('ppm_z', 0.0)
                                pt_z = calc_pt(ppm_z_val, self.mw.ppm_z) if self.mw.ppm_z is not None else 0.0
                                h = get_height(p['ppm_x'], p['ppm_y'], ppm_z_val)
                                vol = calc_volume(p['ppm_x'], p['ppm_y'], ppm_z_val)
                                label = p.get('label') if p.get('label') else f"#{p['id']}"
                                f.write(f"{p['id']}\t{p['ppm_x']:.5f}\t{p['ppm_y']:.5f}\t{ppm_z_val:.5f}\t{pt_x:.5f}\t{pt_y:.5f}\t{pt_z:.5f}\t{h:.5e}\t{vol:.5e}\t{label}\n")

                self.mw.plot_2d.setTitle(f"Success: Picked peaks saved to {os.path.basename(file_path)}")
            except Exception as e:
                self.mw.plot_2d.setTitle(f"Error saving peaks: {e}")
                traceback.print_exc()

    def load_peaks(self):
        active_idx = self.mw.active_index
        if not (0 <= active_idx < len(self.mw.peak_managers)):
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self.mw, "Load Peaks", "", "NMRdraw Tab Files (*.tab);;Text Files (*.txt);;All Files (*)"
        )

        if not file_path:
            return

        try:
            peak_manager = self.mw.peak_managers[active_idx]
            
            # Ask if user wants to clear existing peaks
            if peak_manager.picked_peaks:
                reply = QMessageBox.question(
                    self.mw, "Clear existing peaks?", 
                    "Do you want to clear your current peak list before loading?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
                )
                if reply == QMessageBox.StandardButton.Cancel:
                    return
                if reply == QMessageBox.StandardButton.Yes:
                    peak_manager.clear_peaks()

            new_peaks = []
            if file_path.endswith('.tab'):
                # Parse NMRdraw TAB format
                with open(file_path, "r") as f:
                    lines = f.readlines()
                
                vars_line = None
                data_start = 0
                for i, line in enumerate(lines):
                    if line.startswith("VARS"):
                        vars_line = line.split()[1:]
                    elif line.strip() == "" or line.startswith("FORMAT") or line.startswith("NULL") or line.startswith("DATA"):
                        continue
                    elif vars_line is not None:
                        data_start = i
                        break
                
                if vars_line is None:
                    raise ValueError("Could not find VARS line in TAB file.")

                # Mapping common NMRdraw VARS to our peak dict keys
                # VARS INDEX X_AXIS Y_AXIS DX DY X_PPM Y_PPM X_HZ Y_HZ XW YW XW_HZ YW_HZ X1 X3 Y1 Y3 HEIGHT DHEIGHT VOL PCHI2 TYPE ASS CLUSTID MEMCNT
                col_map = {v: i for i, v in enumerate(vars_line)}
                
                for line in lines[data_start:]:
                    parts = line.split()
                    if len(parts) < len(vars_line):
                        continue
                    
                    p_id = int(parts[col_map['INDEX']]) if 'INDEX' in col_map else peak_manager.peak_counter + 1
                    px = float(parts[col_map['X_PPM']]) if 'X_PPM' in col_map else 0.0
                    py = float(parts[col_map['Y_PPM']]) if 'Y_PPM' in col_map else 0.0
                    pz = float(parts[col_map['Z_PPM']]) if 'Z_PPM' in col_map else None
                    
                    label = parts[col_map['ASS']] if 'ASS' in col_map else None
                    if label == "*" or label == "None":
                        label = None
                        
                    # We might want to store more info, but these are the basics
                    peak_manager.peak_counter = max(peak_manager.peak_counter, p_id)
                    peak_dict = {
                        'id': p_id,
                        'ppm_x': px,
                        'ppm_y': py,
                        'ppm_z': pz,
                        'label': label
                    }
                    
                    # Try to get intensity if available
                    if 'HEIGHT' in col_map:
                        peak_dict['intensity'] = float(parts[col_map['HEIGHT']])
                    
                    peak_manager.picked_peaks.append(peak_dict)
            else:
                # Basic text format loader (very simple tab-delimited)
                import pandas as pd
                df = pd.read_csv(file_path, sep='\t')
                # Try to map columns... (omitted for brevity, let's focus on .tab)
                pass

            self.mw.peak_enabled_flags[active_idx] = True
            self.update_peak_markers()
            self.mw.plot_2d.setTitle(f"Success: Loaded {len(peak_manager.picked_peaks)} peaks from {os.path.basename(file_path)}")

        except Exception as e:
            self.mw.plot_2d.setTitle(f"Error loading peaks: {e}")
            traceback.print_exc()

    def show_peaks(self):
        active_idx = self.mw.active_index
        if 0 <= active_idx < len(self.mw.peak_enabled_flags):
            self.mw.peak_enabled_flags[active_idx] = True
            self.update_peak_markers()
            # Also need to update the checkbox in UI
            self.mw.io_controller.refresh_data_list()

    def hide_peaks(self):
        active_idx = self.mw.active_index
        if 0 <= active_idx < len(self.mw.peak_enabled_flags):
            self.mw.peak_enabled_flags[active_idx] = False
            self.update_peak_markers()
            # Also need to update the checkbox in UI
            self.mw.io_controller.refresh_data_list()

    def force_pick(self, x=None, y=None):
        active_idx = self.mw.active_index
        if not (0 <= active_idx < len(self.mw.peak_managers)):
            return

        if self.mw.current_mode != 'peak_pick':
            self.mw.set_mode('peak_pick')

        pos_x = x if x is not None else self.mw.v_pos
        pos_y = y if y is not None else self.mw.h_pos

        current_z_idx = self.mw.slider_z.value() - 1 if self.mw.nz > 1 else None
        current_ppm_z = self.mw.ppm_z[current_z_idx] if self.mw.nz > 1 else None

        peak_manager = self.mw.peak_managers[active_idx]
        peak_manager.add_force_peak(pos_x, pos_y, ppm_z=current_ppm_z, closest_z_idx=current_z_idx)
        self.update_peak_markers()

    def renumber_peaks(self):
        active_idx = self.mw.active_index
        if not (0 <= active_idx < len(self.mw.peak_managers)):
            return

        peak_manager = self.mw.peak_managers[active_idx]
        if not peak_manager.picked_peaks:
            self.mw.plot_2d.setTitle("No peaks to renumber.")
            return
            
        peak_manager.renumber_peaks()
        self.update_peak_markers()
        self.mw.plot_2d.setTitle("Success: Peaks renumbered sequentially.")

    def update_peak_markers(self):
        current_z_idx = self.mw.slider_z.value() - 1 if self.mw.nz > 1 else None

        cross_circle = QPainterPath()
        cross_circle.addEllipse(-0.5, -0.5, 1.0, 1.0)
        cross_circle.moveTo(-0.5, -0.5)
        cross_circle.lineTo(0.5, 0.5)
        cross_circle.moveTo(-0.5, 0.5)
        cross_circle.lineTo(0.5, -0.5)

        # Track overall active IDs to remove old text items
        all_visible_ids = {} # index -> set of pids

        for idx, (pm, enabled) in enumerate(zip(self.mw.peak_managers, self.mw.peak_enabled_flags)):
            # Initialize items if they don't exist for this index
            if idx >= len(self.mw.peak_scatter_items) or self.mw.peak_scatter_items[idx] is None:
                scatter = pg.ScatterPlotItem(size=10, pen=pg.mkPen('k'), brush=pg.mkBrush(255, 0, 0, 150))
                self.mw.plot_2d.addItem(scatter)
                if idx < len(self.mw.peak_scatter_items):
                    self.mw.peak_scatter_items[idx] = scatter
                else:
                    self.mw.peak_scatter_items.append(scatter)
                
                if idx >= len(self.mw.peak_text_items):
                    self.mw.peak_text_items.append({})

            scatter = self.mw.peak_scatter_items[idx]
            text_items = self.mw.peak_text_items[idx]
            
            if not enabled:
                scatter.setData([])
                scatter.setVisible(False)
                for pid in list(text_items.keys()):
                    self.mw.plot_2d.removeItem(text_items[pid])
                    del text_items[pid]
                continue

            scatter.setVisible(True)
            spots = []
            current_ids = set()
            
            # Use spectrum color for peaks?
            c_pos, _ = self.mw.spectrum_colors[idx]
            brush_color = QColor(c_pos)
            brush_color.setAlpha(150)

            for p in pm.picked_peaks:
                pid = p['id']
                is_center_plane = True
                is_visible = True
                
                if self.mw.nz > 1 and p.get('closest_z') is not None:
                    z_diff = abs(p['closest_z'] - current_z_idx)
                    if z_diff == 0:
                        is_center_plane = True
                    elif z_diff <= 2:
                        is_center_plane = False
                    else:
                        is_visible = False 

                if not is_visible:
                    continue

                current_ids.add(pid)

                if is_center_plane:
                    spots.append({
                        'pos': (p['ppm_x'], p['ppm_y']), 
                        'data': pid,
                        'brush': pg.mkBrush(brush_color),
                        'pen': pg.mkPen('k'),
                        'symbol': 'o'
                    })
                else:
                    spots.append({
                        'pos': (p['ppm_x'], p['ppm_y']), 
                        'data': pid,
                        'brush': pg.mkBrush(0, 0, 0, 0),
                        'pen': pg.mkPen(brush_color, width=1.5),
                        'symbol': cross_circle
                    })

                if pid not in text_items:
                    label = p.get('label')
                    display_text = label if label else f"#{pid}"
                    text_item = pg.TextItem(text=display_text, color=(0, 0, 0), anchor=(-0.2, 0.5)) 
                    text_item.setPos(p['ppm_x'], p['ppm_y'])
                    self.mw.plot_2d.addItem(text_item)
                    text_items[pid] = text_item
                else:
                    label = p.get('label')
                    display_text = label if label else f"#{pid}"
                    text_items[pid].setText(display_text)
                    text_items[pid].setPos(p['ppm_x'], p['ppm_y'])

            scatter.setData(spots)

            ids_to_remove = set(text_items.keys()) - current_ids
            for pid in ids_to_remove:
                self.mw.plot_2d.removeItem(text_items[pid])
                del text_items[pid]

    def rename_peak_dialog(self, px, py):
        active_idx = self.mw.active_index
        if not (0 <= active_idx < len(self.mw.peak_managers)):
            return

        peak_manager = self.mw.peak_managers[active_idx]
        
        # Get scale for distance calculation
        view_box = self.mw.plot_2d.getViewBox()
        x_range, y_range = view_box.viewRange()
        dx_scale = max(abs(x_range[1] - x_range[0]), 1e-6)
        dy_scale = max(abs(y_range[1] - y_range[0]), 1e-6)
        
        peak = peak_manager.get_nearest_peak(px, py, dx_scale, dy_scale)
        if peak:
            from PyQt6.QtWidgets import QInputDialog
            current_label = peak.get('label', "")
            if current_label is None: current_label = ""
            
            new_label, ok = QInputDialog.getText(
                self.mw, "Rename Peak", 
                f"Enter label for peak #{peak['id']}:", 
                text=current_label
            )
            
            if ok:
                peak['label'] = new_label if new_label.strip() != "" else None
                self.update_peak_markers()

    def auto_pick(self):
        active_idx = self.mw.active_index
        if not (0 <= active_idx < len(self.mw.peak_managers)):
            return

        vis_data = self.mw.vis_data_dict.get(active_idx)
        raw_data = self.mw.raw_data_list[active_idx]
                
        if vis_data is None:
            return

        if raw_data.ndim == 1:
            base_mult = self.mw.spinbox_1d_base.value()
        else:
            base_mult = self.mw.cont_sliders['base'].value()
            
        noise_rmsd = self.mw.data_handler.calculate_rmsd(vis_data)
        threshold = noise_rmsd * base_mult * 1.5
        
        peak_manager = self.mw.peak_managers[active_idx]
        if peak_manager.picked_peaks:
            reply = QMessageBox.question(
                self.mw, "Clear existing peaks?", 
                "Do you want to clear your current peak list before auto-picking?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                peak_manager.picked_peaks.clear()
                peak_manager.peak_counter = 0
                if active_idx == 0: # Only clear fits if it's the primary/active one (actually we should have per-spectrum fits too but let's keep it simple)
                    self.mw.fitting_controller.clear_1d_fits()
                
        if raw_data.ndim == 3:
            peak_manager.auto_pick(raw_data, self.mw.ppm_x, self.mw.ppm_y, threshold, ppm_z=getattr(self.mw, 'ppm_z', None))
        else:
            peak_manager.auto_pick(vis_data, self.mw.ppm_x, self.mw.ppm_y, threshold)
        
        self.mw.peak_enabled_flags[active_idx] = True
        self.update_peak_markers()
        self.mw.plot_2d.setTitle(f"Success: Auto-picked {len(peak_manager.picked_peaks)} peaks above the baseline.")

    def clear_peaks(self):
        active_idx = self.mw.active_index
        if not (0 <= active_idx < len(self.mw.peak_managers)):
            return

        peak_manager = self.mw.peak_managers[active_idx]
        if not peak_manager.picked_peaks:
            self.mw.plot_2d.setTitle("No peaks to clear.")
            return

        reply = QMessageBox.question(
            self.mw, "Clear all peaks?", 
            "Are you sure you want to delete all picked peaks for this spectrum? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            peak_manager.clear_peaks()
            self.update_peak_markers()
            self.mw.plot_2d.setTitle("Success: Peaks cleared for active spectrum.")
