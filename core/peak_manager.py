import numpy as np

class PeakManager:
    def __init__(self):
        self.picked_peaks = []
        self.peak_counter = 0

    def add_force_peak(self, ppm_x, ppm_y):
        self.peak_counter += 1
        self.picked_peaks.append({'id': self.peak_counter, 'ppm_x': ppm_x, 'ppm_y': ppm_y})
        return self.picked_peaks

    def renumber_peaks(self):
        for i, p in enumerate(self.picked_peaks):
            p['id'] = i + 1
        self.peak_counter = len(self.picked_peaks)
        return self.picked_peaks
        
    def refine_peak(self, click_ppm_x, click_ppm_y, vis_data, ppm_x, ppm_y, threshold=0.0):
        if vis_data is None or vis_data.size == 0:
            #print("DIAGNOSTIC: Abort - vis_data is empty!")
            return self.picked_peaks
            
        x_idx_center = np.argmin(np.abs(ppm_x - click_ppm_x))
        window = 5 

        if vis_data.ndim == 1:
            start_x = max(0, x_idx_center - window)
            end_x = min(len(ppm_x), x_idx_center + window + 1)
            
            local_data = vis_data[start_x:end_x]
            if local_data.size == 0: 
                #print("DIAGNOSTIC: Abort - 1D local_data window is empty!")
                return self.picked_peaks
            
            center_idx = x_idx_center - start_x
            sign = 1 if local_data[center_idx] >= 0 else -1
            max_loc = np.argmax(local_data) if sign > 0 else np.argmin(local_data)
            true_x_idx = start_x + max_loc

            # NEW: Noise Threshold Check
            peak_intensity = vis_data[true_x_idx]
            if abs(peak_intensity) < threshold:
                #print(f"DIAGNOSTIC: Abort - 1D noise rejected ({abs(peak_intensity):.2f} < threshold {threshold:.2f})")
                return self.picked_peaks

            offset = 0
            if 0 < true_x_idx < len(ppm_x) - 1:
                alpha, beta, gamma = vis_data[true_x_idx - 1], vis_data[true_x_idx], vis_data[true_x_idx + 1]
                denom = alpha - 2*beta + gamma
                if denom != 0:
                    offset = 0.5 * (alpha - gamma) / denom
            
            ppm_step = ppm_x[1] - ppm_x[0] if len(ppm_x) > 1 else 0
            refined_ppm_x = ppm_x[true_x_idx] + offset * ppm_step
            refined_ppm_y = click_ppm_y # Keep y as clicked for 1D
            
        elif vis_data.ndim == 2:
            y_idx_center = np.argmin(np.abs(ppm_y - click_ppm_y))
            
            start_x, end_x = max(0, x_idx_center - window), min(len(ppm_x), x_idx_center + window + 1)
            start_y, end_y = max(0, y_idx_center - window), min(len(ppm_y), y_idx_center + window + 1)

            local_data = vis_data[start_x:end_x, start_y:end_y]
            if local_data.size == 0: 
                #print("DIAGNOSTIC: Abort - 2D local_data window is empty!")
                return self.picked_peaks

            center_x_local = x_idx_center - start_x
            center_y_local = y_idx_center - start_y
            
            sign = 1 if local_data[center_x_local, center_y_local] >= 0 else -1
            
            if sign > 0:
                max_idx = np.unravel_index(np.argmax(local_data), local_data.shape)
            else:
                max_idx = np.unravel_index(np.argmin(local_data), local_data.shape)

            true_x_idx = start_x + max_idx[0]
            true_y_idx = start_y + max_idx[1]

            # NEW: Noise Threshold Check
            peak_intensity = vis_data[true_x_idx, true_y_idx]
            if abs(peak_intensity) < threshold:
                #print(f"DIAGNOSTIC: Abort - 2D noise rejected ({abs(peak_intensity):.2f} < threshold {threshold:.2f})")
                return self.picked_peaks

            offset_x, offset_y = 0, 0
            # X interpolation
            if 0 < true_x_idx < len(ppm_x) - 1:
                alpha, beta, gamma = vis_data[true_x_idx - 1, true_y_idx], vis_data[true_x_idx, true_y_idx], vis_data[true_x_idx + 1, true_y_idx]
                denom = alpha - 2*beta + gamma
                if denom != 0: offset_x = 0.5 * (alpha - gamma) / denom

            # Y interpolation
            if 0 < true_y_idx < len(ppm_y) - 1:
                alpha, beta, gamma = vis_data[true_x_idx, true_y_idx - 1], vis_data[true_x_idx, true_y_idx], vis_data[true_x_idx, true_y_idx + 1]
                denom = alpha - 2*beta + gamma
                if denom != 0: offset_y = 0.5 * (alpha - gamma) / denom

            ppm_step_x = ppm_x[1] - ppm_x[0] if len(ppm_x) > 1 else 0
            ppm_step_y = ppm_y[1] - ppm_y[0] if len(ppm_y) > 1 else 0

            refined_ppm_x = ppm_x[true_x_idx] + offset_x * ppm_step_x
            refined_ppm_y = ppm_y[true_y_idx] + offset_y * ppm_step_y

        self.peak_counter += 1
        self.picked_peaks.append({'id': self.peak_counter, 'ppm_x': refined_ppm_x, 'ppm_y': refined_ppm_y})
        
        #print(f"DIAGNOSTIC: Clicked ({click_ppm_x:.2f}, {click_ppm_y:.2f}) -> Snapped to ({refined_ppm_x:.2f}, {refined_ppm_y:.2f})")
        
        return self.picked_peaks
        
    def delete_nearest_peak(self, click_x, click_y, dx_scale, dy_scale):
        if not self.picked_peaks:
            return self.picked_peaks
            
        best_idx, min_dist = -1, float('inf')
        
        for i, p in enumerate(self.picked_peaks):
            dx = (p['ppm_x'] - click_x) / dx_scale
            dy = (p['ppm_y'] - click_y) / dy_scale
            dist = dx**2 + dy**2
            if dist < min_dist:
                min_dist, best_idx = dist, i
                
        if min_dist < 0.01 and best_idx != -1:
            del self.picked_peaks[best_idx]
            
        return self.picked_peaks

    def auto_pick(self, vis_data, ppm_x, ppm_y, threshold=0.0):
        """Scans the entire spectrum for local extrema above the noise threshold."""
        if vis_data is None or vis_data.size == 0:
            return self.picked_peaks

        ppm_step_x = ppm_x[1] - ppm_x[0] if len(ppm_x) > 1 else 0

        if vis_data.ndim == 1:
            # Find local extrema in 1D
            is_max = (vis_data > np.roll(vis_data, 1)) & (vis_data > np.roll(vis_data, -1)) & (vis_data > threshold)
            is_min = (vis_data < np.roll(vis_data, 1)) & (vis_data < np.roll(vis_data, -1)) & (vis_data < -threshold)
            
            # Avoid edge wrap-around artifacts from np.roll
            is_max[0] = is_max[-1] = is_min[0] = is_min[-1] = False
            
            indices = np.where(is_max | is_min)[0]
            
            for idx in indices:
                # 1D Parabolic interpolation
                alpha, beta, gamma = vis_data[idx - 1], vis_data[idx], vis_data[idx + 1]
                denom = alpha - 2*beta + gamma
                offset = 0.5 * (alpha - gamma) / denom if denom != 0 else 0
                
                refined_ppm_x = ppm_x[idx] + offset * ppm_step_x
                
                self.peak_counter += 1
                self.picked_peaks.append({'id': self.peak_counter, 'ppm_x': refined_ppm_x, 'ppm_y': 0.0})

        elif vis_data.ndim == 2:
            ppm_step_y = ppm_y[1] - ppm_y[0] if len(ppm_y) > 1 else 0
            
            # Scan all 8 surrounding neighbors simultaneously
            is_max = np.ones(vis_data.shape, dtype=bool)
            is_min = np.ones(vis_data.shape, dtype=bool)
            
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    shifted = np.roll(vis_data, shift=(dx, dy), axis=(0, 1))
                    is_max &= (vis_data > shifted)
                    is_min &= (vis_data < shifted)
            
            # Filter by threshold
            is_max &= (vis_data > threshold)
            is_min &= (vis_data < -threshold)
            
            # Avoid edge wrap-around artifacts
            is_max[0, :] = is_max[-1, :] = is_max[:, 0] = is_max[:, -1] = False
            is_min[0, :] = is_min[-1, :] = is_min[:, 0] = is_min[:, -1] = False
            
            x_indices, y_indices = np.where(is_max | is_min)
            
            for x_idx, y_idx in zip(x_indices, y_indices):
                # 2D Parabolic interpolation
                offset_x, offset_y = 0, 0
                
                alpha, beta, gamma = vis_data[x_idx - 1, y_idx], vis_data[x_idx, y_idx], vis_data[x_idx + 1, y_idx]
                denom_x = alpha - 2*beta + gamma
                if denom_x != 0: offset_x = 0.5 * (alpha - gamma) / denom_x
                
                alpha, beta, gamma = vis_data[x_idx, y_idx - 1], vis_data[x_idx, y_idx], vis_data[x_idx, y_idx + 1]
                denom_y = alpha - 2*beta + gamma
                if denom_y != 0: offset_y = 0.5 * (alpha - gamma) / denom_y
                
                refined_ppm_x = ppm_x[x_idx] + offset_x * ppm_step_x
                refined_ppm_y = ppm_y[y_idx] + offset_y * ppm_step_y
                
                self.peak_counter += 1
                self.picked_peaks.append({'id': self.peak_counter, 'ppm_x': refined_ppm_x, 'ppm_y': refined_ppm_y})
                
        return self.picked_peaks

    def clear_peaks(self):
        self.picked_peaks.clear()
        self.peak_counter = 0
        return self.picked_peaks