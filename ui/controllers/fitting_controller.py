import numpy as np
from scipy.optimize import curve_fit
from PyQt6.QtCore import Qt
import pyqtgraph as pg

class FittingController:
    def __init__(self, main_window):
        self.main_window = main_window
        self.fit_curves = []

    def fit_1d_peaks(self, shape_type):
        if not self.main_window._check_1d_baseline_validity():
            return
            
        if not self.main_window.peak_manager.picked_peaks:
            return

        self.clear_1d_fits()
            
        orig_i = self.main_window.enabled_indices[0]
        y_data = self.main_window.vis_data_dict.get(orig_i) 
        if y_data is None: return
        x_data = self.main_window.ppm_x
        
        window_pts = 15
        
        for p in self.main_window.peak_manager.picked_peaks:
            center_ppm = p['ppm_x']
            idx_center = np.argmin(np.abs(x_data - center_ppm))
            
            start_idx = max(0, idx_center - window_pts)
            end_idx = min(len(x_data), idx_center + window_pts + 1)
            
            x_fit = x_data[start_idx:end_idx]
            y_fit = y_data[start_idx:end_idx]
            
            amp_guess = max(1e-6, y_data[idx_center])
            cen_guess = center_ppm
            wid_guess = np.abs(x_data[0] - x_data[1]) * 4
            
            try:
                bounds_standard = ([0, -np.inf, 0], [np.inf, np.inf, np.inf]) 
                
                if shape_type == 'lorentzian':
                    popt, _ = curve_fit(self.main_window.data_handler.lorentzian, x_fit, y_fit, p0=[amp_guess, cen_guess, wid_guess], bounds=bounds_standard)
                    area = self.main_window.data_handler.calc_analytical_area(popt[0], popt[2], 'lorentzian')
                    p['fit_amp'], p['fit_cen'], p['fit_wid'] = popt
                    p['fit_eta'] = 1.0
                elif shape_type == 'gaussian':
                    popt, _ = curve_fit(self.main_window.data_handler.gaussian, x_fit, y_fit, p0=[amp_guess, cen_guess, wid_guess], bounds=bounds_standard)
                    area = self.main_window.data_handler.calc_analytical_area(popt[0], popt[2], 'gaussian')
                    p['fit_amp'], p['fit_cen'], p['fit_wid'] = popt
                    p['fit_eta'] = 0.0
                elif shape_type == 'pseudo_voigt':
                    bounds_pv = ([0, -np.inf, 0, 0.0], [np.inf, np.inf, np.inf, 1.0])
                    popt, _ = curve_fit(self.main_window.data_handler.pseudo_voigt, x_fit, y_fit, p0=[amp_guess, cen_guess, wid_guess, 0.5], bounds=bounds_pv)
                    area = self.main_window.data_handler.calc_analytical_area(popt[0], popt[2], 'pseudo_voigt', popt[3])
                    p['fit_amp'], p['fit_cen'], p['fit_wid'], p['fit_eta'] = popt

                p['fit_area'] = abs(area)
                p['fit_type'] = shape_type
                p['ppm_x'] = p['fit_cen'] 
                
            except Exception as e:
                p['fit_type'] = 'failed'
                p['fit_area'] = 0.0

        self.main_window.update_peak_markers()
        self.draw_1d_fits()
        self.main_window.plot_2d.setTitle(f"Success: Fitted {len(self.main_window.peak_manager.picked_peaks)} peaks using {shape_type.replace('_', '-').title()}.")

    def draw_1d_fits(self):
        for curve in self.fit_curves:
            self.main_window.plot_2d.removeItem(curve)
        self.fit_curves = []
        
        orig_i = self.main_window.enabled_indices[0]
        offset_val = self.main_window.display_controls.get_value('offset')
        base_max = np.max(np.abs(self.main_window.current_slice_list[0])) if self.main_window.current_slice_list else 1.0
        y_offset = (self.main_window.enabled_indices.index(orig_i) * offset_val * (base_max * 0.1))

        for p in self.main_window.peak_manager.picked_peaks:
            if p.get('fit_type') in ['lorentzian', 'gaussian', 'pseudo_voigt']:
                window_pts = 30
                idx_center = np.argmin(np.abs(self.main_window.ppm_x - p['fit_cen']))
                start_idx = max(0, idx_center - window_pts)
                end_idx = min(len(self.main_window.ppm_x), idx_center + window_pts + 1)
                
                x_render = self.main_window.ppm_x[start_idx:end_idx]
                
                if p['fit_type'] == 'lorentzian':
                    y_render = self.main_window.data_handler.lorentzian(x_render, p['fit_amp'], p['fit_cen'], p['fit_wid'])
                elif p['fit_type'] == 'gaussian':
                    y_render = self.main_window.data_handler.gaussian(x_render, p['fit_amp'], p['fit_cen'], p['fit_wid'])
                else:
                    y_render = self.main_window.data_handler.pseudo_voigt(x_render, p['fit_amp'], p['fit_cen'], p['fit_wid'], p['fit_eta'])

                fit_curve = pg.PlotDataItem(x=x_render, y=y_render + y_offset, pen=pg.mkPen('m', width=2, style=Qt.PenStyle.DashLine))
                self.main_window.plot_2d.addItem(fit_curve)
                self.fit_curves.append(fit_curve)  

    def clear_1d_fits(self):
        for curve in self.fit_curves:
            self.main_window.plot_2d.removeItem(curve)
        self.fit_curves = []
        
        if hasattr(self.main_window, 'peak_manager') and self.main_window.peak_manager.picked_peaks:
            for p in self.main_window.peak_manager.picked_peaks:
                keys_to_remove = ['fit_type', 'fit_amp', 'fit_cen', 'fit_wid', 'fit_eta', 'fit_area']
                for k in keys_to_remove:
                    p.pop(k, None)
