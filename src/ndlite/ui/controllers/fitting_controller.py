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
        
        ppm_step = np.abs(x_data[0] - x_data[1]) if len(x_data) > 1 else 1.0
        
        # Sort peaks by ppm to ensure consistent ordering
        peaks = sorted(self.main_window.peak_manager.picked_peaks, key=lambda p: p['ppm_x'])
        num_peaks = len(peaks)
        
        # 1. Define global fitting region
        # Span from the first peak's left edge to the last peak's right edge
        window_pts = max(10, int(0.03 / ppm_step))
        min_ppm = min(p['ppm_x'] for p in peaks)
        max_ppm = max(p['ppm_x'] for p in peaks)
        
        # Ensure min_ppm is the smaller numerical value, handling inverted axis
        if x_data[0] > x_data[-1]:
            start_ppm, end_ppm = max_ppm, min_ppm
        else:
            start_ppm, end_ppm = min_ppm, max_ppm
            
        start_idx = max(0, np.argmin(np.abs(x_data - start_ppm)) - window_pts)
        end_idx = min(len(x_data), np.argmin(np.abs(x_data - end_ppm)) + window_pts + 1)
        
        # Handle inverted axis indexing
        if start_idx > end_idx:
            start_idx, end_idx = end_idx, start_idx
            
        x_fit = x_data[start_idx:end_idx]
        y_fit = y_data[start_idx:end_idx]
        
        if len(x_fit) < num_peaks * 3:
             print("Not enough data points for global fit.")
             return

        # 2. Build initial guesses and bounds for ALL peaks
        p0 = []
        bounds_min = []
        bounds_max = []
        
        for p in peaks:
            cen = p['ppm_x']
            idx_center = np.argmin(np.abs(x_data - cen))
            amp = max(1e-6, y_data[idx_center])
            wid = ppm_step * 2.0
            
            # Wiggle room
            delta_amp = max(1e-4, amp * 0.05)
            delta_cen = max(1e-4, ppm_step * 0.1)
            
            p0.extend([amp, cen, wid])
            bounds_min.extend([amp - delta_amp, cen - delta_cen, ppm_step * 0.5])
            bounds_max.extend([amp + delta_amp, cen + delta_cen, np.abs(x_fit[-1] - x_fit[0]) * 0.25])
            
            if shape_type == 'pseudo_voigt':
                p0.append(0.5)
                bounds_min.append(0.0)
                bounds_max.append(1.0)

        # 3. Define the composite objective function
        def global_model(x, *params):
            y_sum = np.zeros_like(x)
            
            if shape_type == 'pseudo_voigt':
                # Params grouped in blocks of 4: [amp1, cen1, wid1, eta1, amp2, cen2, wid2, eta2, ...]
                for i in range(num_peaks):
                    idx = i * 4
                    amp, cen, wid, eta = params[idx:idx+4]
                    y_sum += self.main_window.data_handler.pseudo_voigt(x, amp, cen, wid, eta)
            else:
                # Params grouped in blocks of 3: [amp1, cen1, wid1, amp2, cen2, wid2, ...]
                func = self.main_window.data_handler.lorentzian if shape_type == 'lorentzian' else self.main_window.data_handler.gaussian
                for i in range(num_peaks):
                    idx = i * 3
                    amp, cen, wid = params[idx:idx+3]
                    y_sum += func(x, amp, cen, wid)
                    
            return y_sum

        # 4. Perform the global optimization
        try:
            popt, _ = curve_fit(global_model, x_fit, y_fit, p0=p0, bounds=(bounds_min, bounds_max))
            
            # 5. Unpack and save results back to the individual peaks
            for i, p in enumerate(peaks):
                if shape_type == 'pseudo_voigt':
                    idx = i * 4
                    p['fit_amp'], p['fit_cen'], p['fit_wid'], p['fit_eta'] = popt[idx:idx+4]
                    area = self.main_window.data_handler.calc_analytical_area(p['fit_amp'], p['fit_wid'], 'pseudo_voigt', p['fit_eta'])
                else:
                    idx = i * 3
                    p['fit_amp'], p['fit_cen'], p['fit_wid'] = popt[idx:idx+3]
                    p['fit_eta'] = 1.0 if shape_type == 'lorentzian' else 0.0
                    area = self.main_window.data_handler.calc_analytical_area(p['fit_amp'], p['fit_wid'], shape_type)
                    
                p['fit_area'] = abs(area)
                p['fit_type'] = shape_type
                
        except Exception as e:
            print(f"Global fit failed: {e}")
            for p in peaks:
                p['fit_type'] = 'failed'
                p['fit_area'] = 0.0

        self.main_window.peak_controller.update_peak_markers()
        self.draw_1d_fits()
        self.main_window.plot_2d.setTitle(f"Success: Global fit of {num_peaks} peaks using {shape_type.replace('_', '-').title()}.")

    def draw_1d_fits(self):
        for curve in self.fit_curves:
            self.main_window.plot_2d.removeItem(curve)
        self.fit_curves = []
        
        orig_i = self.main_window.enabled_indices[0]
        offset_val = self.main_window.cont_sliders['offset'].value()
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
