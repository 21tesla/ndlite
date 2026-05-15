from PyQt6.QtWidgets import QFileDialog, QMessageBox
from PyQt6.QtGui import QPainterPath
import pyqtgraph as pg
import numpy as np
import os

class PeakController:
    def __init__(self, main_window):
        self.mw = main_window

    def save_peaks(self):
        if not self.mw.peak_manager.picked_peaks:
            self.mw.plot_2d.setTitle("No peaks to save.")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self.mw, "Save Peaks", "peaks.txt", "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                ndim = self.mw.raw_data.ndim if self.mw.raw_data is not None else 0
                
                def calc_pt(ppm_val, ppm_array):
                    if ppm_array is None or len(ppm_array) <= 1: return 0.0
                    return (ppm_val - ppm_array[0]) / (ppm_array[-1] - ppm_array[0]) * (len(ppm_array) - 1)

                def calc_volume(px, py, pz=None):
                    if self.mw.raw_data is None: return 0.0
                    
                    x_idx = np.argmin(np.abs(self.mw.ppm_x - px))
                    y_idx = np.argmin(np.abs(self.mw.ppm_y - py)) if self.mw.ppm_y is not None else 0
                    
                    wx, wy, wz = 5, 5, 2  # Integration window
                    
                    start_x = max(0, x_idx - wx)
                    end_x = min(self.mw.raw_data.shape[-1], x_idx + wx + 1)
                    
                    if ndim == 1:
                        return float(np.sum(self.mw.raw_data[start_x:end_x]))
                    elif ndim == 2:
                        start_y = max(0, y_idx - wy)
                        end_y = min(self.mw.raw_data.shape[0], y_idx + wy + 1)
                        return float(np.sum(self.mw.raw_data[start_y:end_y, start_x:end_x]))
                    elif ndim >= 3:
                        if pz is None or self.mw.ppm_z is None: return 0.0
                        z_idx = np.argmin(np.abs(self.mw.ppm_z - pz))
                        start_y = max(0, y_idx - wy)
                        end_y = min(self.mw.raw_data.shape[1], y_idx + wy + 1)
                        start_z = max(0, z_idx - wz)
                        end_z = min(self.mw.raw_data.shape[0], z_idx + wz + 1)
                        return float(np.sum(self.mw.raw_data[start_z:end_z, start_y:end_y, start_x:end_x]))
                    return 0.0

                with open(file_path, "w") as f:
                    if ndim == 1:
                        has_fits = 'fit_area' in self.mw.peak_manager.picked_peaks[0] if self.mw.peak_manager.picked_peaks else False
                        
                        if has_fits:
                            f.write(f"Index\t{self.mw.label_x}_ppm\t{self.mw.label_x}_pt\tFit_Type\tLinewidth\tArea_Integral\n")
                            for p in self.mw.peak_manager.picked_peaks:
                                pt_x = calc_pt(p['ppm_x'], self.mw.ppm_x)
                                f.write(f"{p['id']}\t{p['ppm_x']:.5f}\t{pt_x:.5f}\t{p.get('fit_type', 'none')}\t{abs(p.get('fit_wid', 0.0)):.5e}\t{p.get('fit_area', 0.0):.5e}\n")
                        else:
                            f.write(f"Index\t{self.mw.label_x}_ppm\t{self.mw.label_x}_pt\tVolume_Sum\n")
                            for p in self.mw.peak_manager.picked_peaks:
                                pt_x = calc_pt(p['ppm_x'], self.mw.ppm_x)
                                vol = calc_volume(p['ppm_x'], p['ppm_y'])
                                f.write(f"{p['id']}\t{p['ppm_x']:.5f}\t{pt_x:.5f}\t{vol:.5e}\n")
                                                            
                    elif ndim == 2:
                        f.write(f"Index\t{self.mw.label_x}_ppm\t{self.mw.label_y}_ppm\t{self.mw.label_x}_pt\t{self.mw.label_y}_pt\tVolume\n")
                        for p in self.mw.peak_manager.picked_peaks:
                            pt_x = calc_pt(p['ppm_x'], self.mw.ppm_x)
                            pt_y = calc_pt(p['ppm_y'], self.mw.ppm_y)
                            vol = calc_volume(p['ppm_x'], p['ppm_y'])
                            f.write(f"{p['id']}\t{p['ppm_x']:.5f}\t{p['ppm_y']:.5f}\t{pt_x:.5f}\t{pt_y:.5f}\t{vol:.5e}\n")
                            
                    elif ndim >= 3:
                        lbl_z = self.mw.label_z if self.mw.label_z else "Z"
                        f.write(f"Index\t{self.mw.label_x}_ppm\t{self.mw.label_y}_ppm\t{lbl_z}_ppm\t{self.mw.label_x}_pt\t{self.mw.label_y}_pt\t{lbl_z}_pt\tVolume\n")
                        for p in self.mw.peak_manager.picked_peaks:
                            pt_x = calc_pt(p['ppm_x'], self.mw.ppm_x)
                            pt_y = calc_pt(p['ppm_y'], self.mw.ppm_y)
                            ppm_z_val = p.get('ppm_z', 0.0)
                            pt_z = calc_pt(ppm_z_val, self.mw.ppm_z) if self.mw.ppm_z is not None else 0.0
                            vol = calc_volume(p['ppm_x'], p['ppm_y'], ppm_z_val)
                            f.write(f"{p['id']}\t{p['ppm_x']:.5f}\t{p['ppm_y']:.5f}\t{ppm_z_val:.5f}\t{pt_x:.5f}\t{pt_y:.5f}\t{pt_z:.5f}\t{vol:.5e}\n")

                self.mw.plot_2d.setTitle(f"Success: Picked peaks saved to {os.path.basename(file_path)}")
            except Exception as e:
                self.mw.plot_2d.setTitle(f"Error saving peaks: {e}")

    def show_peaks(self):
        self.mw.peaks_scatter.setVisible(True)
        for item in self.mw.peak_text_items.values():
            item.setVisible(True)

    def hide_peaks(self):
        self.mw.peaks_scatter.setVisible(False)
        for item in self.mw.peak_text_items.values():
            item.setVisible(False)

    def force_pick(self, x=None, y=None):
        if self.mw.raw_data is not None:
            if self.mw.current_mode != 'peak_pick':
                self.mw.set_mode('peak_pick')

            pos_x = x if x is not None else self.mw.v_pos
            pos_y = y if y is not None else self.mw.h_pos

            current_z_idx = self.mw.slider_z.value() - 1 if self.mw.nz > 1 else None
            current_ppm_z = self.mw.ppm_z[current_z_idx] if self.mw.nz > 1 else None

            self.mw.peak_manager.add_force_peak(pos_x, pos_y, ppm_z=current_ppm_z, closest_z_idx=current_z_idx)
            self.update_peak_markers()

    def renumber_peaks(self):
        if not self.mw.peak_manager.picked_peaks:
            self.mw.plot_2d.setTitle("No peaks to renumber.")
            return
            
        for pid, text_item in self.mw.peak_text_items.items():
            self.mw.plot_2d.removeItem(text_item)
        self.mw.peak_text_items.clear()
        
        self.mw.peak_manager.renumber_peaks()
        self.update_peak_markers()
        self.mw.plot_2d.setTitle("Success: Peaks renumbered sequentially.")

    def update_peak_markers(self):
        spots = []
        current_ids = set()
        peaks = self.mw.peak_manager.picked_peaks 
        current_z_idx = self.mw.slider_z.value() - 1 if self.mw.nz > 1 else None

        cross_circle = QPainterPath()
        cross_circle.addEllipse(-0.5, -0.5, 1.0, 1.0)
        cross_circle.moveTo(-0.5, -0.5)
        cross_circle.lineTo(0.5, 0.5)
        cross_circle.moveTo(-0.5, 0.5)
        cross_circle.lineTo(0.5, -0.5)
        
        for p in peaks:
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
                    'brush': pg.mkBrush(255, 0, 0, 150),
                    'pen': pg.mkPen('k'),
                    'symbol': 'o'
                })
            else:
                spots.append({
                    'pos': (p['ppm_x'], p['ppm_y']), 
                    'data': pid,
                    'brush': pg.mkBrush(0, 0, 0, 0),
                    'pen': pg.mkPen(255, 0, 0, 150, width=1.5),
                    'symbol': cross_circle
                })

            if pid not in self.mw.peak_text_items:
                text_item = pg.TextItem(text=str(pid), color=(0, 0, 0), anchor=(-0.2, 0.5)) 
                text_item.setPos(p['ppm_x'], p['ppm_y'])
                self.mw.plot_2d.addItem(text_item)
                self.mw.peak_text_items[pid] = text_item
            else:
                self.mw.peak_text_items[pid].setPos(p['ppm_x'], p['ppm_y'])

        self.mw.peaks_scatter.setData(spots)

        ids_to_remove = set(self.mw.peak_text_items.keys()) - current_ids
        for pid in ids_to_remove:
            self.mw.plot_2d.removeItem(self.mw.peak_text_items[pid])
            del self.mw.peak_text_items[pid]

    def auto_pick(self):
        if not self.mw.enabled_indices or not hasattr(self.mw, 'vis_data_dict'):
            QMessageBox.warning(self.mw, "No Data", "Please load a spectrum before auto-picking.")
            return
            
        orig_i = self.mw.enabled_indices[0]
        vis_data = self.mw.vis_data_dict.get(orig_i)
        raw_data = self.mw.raw_data_list[orig_i]
                
        if vis_data is None:
            return

        if raw_data.ndim == 1:
            base_mult = self.mw.spinbox_1d_base.value()
        else:
            base_mult = self.mw.cont_sliders['base'].value()
            
        noise_rmsd = self.mw.data_handler.calculate_rmsd(vis_data)
        threshold = noise_rmsd * base_mult * 1.5
        
        if self.mw.peak_manager.picked_peaks:
            reply = QMessageBox.question(
                self.mw, "Clear existing peaks?", 
                "Do you want to clear your current peak list before auto-picking?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.mw.peak_manager.picked_peaks.clear()
                self.mw.peak_manager.peak_counter = 0
                self.mw.fitting_controller.clear_1d_fits()
                
        if raw_data.ndim == 3:
            self.mw.peak_manager.auto_pick(raw_data, self.mw.ppm_x, self.mw.ppm_y, threshold, ppm_z=getattr(self.mw, 'ppm_z', None))
        else:
            self.mw.peak_manager.auto_pick(vis_data, self.mw.ppm_x, self.mw.ppm_y, threshold)
        
        self.update_peak_markers()
        self.mw.plot_2d.setTitle(f"Success: Auto-picked {len(self.mw.peak_manager.picked_peaks)} peaks above the baseline.")

    def clear_peaks(self):
        if not self.mw.peak_manager.picked_peaks:
            self.mw.plot_2d.setTitle("No peaks to clear.")
            return

        reply = QMessageBox.question(
            self.mw, "Clear all peaks?", 
            "Are you sure you want to delete all picked peaks? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.mw.peak_manager.clear_peaks()
            self.update_peak_markers()
            self.mw.plot_2d.setTitle("Success: All peaks cleared.")
