import numpy as np

class PeakManager:
    def __init__(self):
        self.picked_peaks = []
        self.peak_counter = 0

#---------------------------------------------------------------------------------------

    def add_force_peak(self, ppm_x, ppm_y, ppm_z=None, closest_z_idx=None):
        self.peak_counter += 1
        self.picked_peaks.append({
            'id': self.peak_counter, 
            'ppm_x': ppm_x, 
            'ppm_y': ppm_y,
            'ppm_z': ppm_z,
            'closest_z': closest_z_idx
        })
        return self.picked_peaks

#---------------------------------------------------------------------------------------

    def renumber_peaks(self):
        for i, p in enumerate(self.picked_peaks):
            p['id'] = i + 1
        self.peak_counter = len(self.picked_peaks)
        return self.picked_peaks

#---------------------------------------------------------------------------------------

    def clear_peaks(self):
        self.picked_peaks.clear()
        self.peak_counter = 0
        return self.picked_peaks

#---------------------------------------------------------------------------------------
                
    def refine_peak(self, click_ppm_x, click_ppm_y, data, ppm_x, ppm_y, threshold=0.0, click_z_idx=None, ppm_z=None):
        if data is None or data.size == 0:
            return self.picked_peaks
            
        x_idx_center = np.argmin(np.abs(ppm_x - click_ppm_x))
        window = 5 

        if data.ndim == 1:
            start_x = max(0, x_idx_center - window)
            end_x = min(len(ppm_x), x_idx_center + window + 1)
            
            local_data = data[start_x:end_x]
            if local_data.size == 0: 
                return self.picked_peaks
            
            center_idx = x_idx_center - start_x
            sign = 1 if local_data[center_idx] >= 0 else -1
            max_loc = np.argmax(local_data) if sign > 0 else np.argmin(local_data)
            true_x_idx = start_x + max_loc

            peak_intensity = data[true_x_idx]
            if abs(peak_intensity) < threshold:
                return self.picked_peaks

            offset = 0
            if 0 < true_x_idx < len(ppm_x) - 1:
                alpha, beta, gamma = data[true_x_idx - 1], data[true_x_idx], data[true_x_idx + 1]
                denom = alpha - 2*beta + gamma
                if denom != 0:
                    offset = 0.5 * (alpha - gamma) / denom
            
            ppm_step = ppm_x[1] - ppm_x[0] if len(ppm_x) > 1 else 0
            refined_ppm_x = ppm_x[true_x_idx] + offset * ppm_step
            refined_ppm_y = data[true_x_idx]
            
            self.peak_counter += 1
            self.picked_peaks.append({
                'id': self.peak_counter, 
                'ppm_x': refined_ppm_x, 
                'ppm_y': refined_ppm_y,
                'ppm_z': None,
                'closest_z': None
            })
            
        elif data.ndim == 2:
            y_idx_center = np.argmin(np.abs(ppm_y - click_ppm_y))
            
            start_x, end_x = max(0, x_idx_center - window), min(len(ppm_x), x_idx_center + window + 1)
            start_y, end_y = max(0, y_idx_center - window), min(len(ppm_y), y_idx_center + window + 1)

            local_data = data[start_x:end_x, start_y:end_y]
            if local_data.size == 0: 
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

            peak_intensity = data[true_x_idx, true_y_idx]
            if abs(peak_intensity) < threshold:
                return self.picked_peaks

            offset_x, offset_y = 0, 0
            if 0 < true_x_idx < len(ppm_x) - 1:
                alpha, beta, gamma = data[true_x_idx - 1, true_y_idx], data[true_x_idx, true_y_idx], data[true_x_idx + 1, true_y_idx]
                denom = alpha - 2*beta + gamma
                if denom != 0: offset_x = 0.5 * (alpha - gamma) / denom

            if 0 < true_y_idx < len(ppm_y) - 1:
                alpha, beta, gamma = data[true_x_idx, true_y_idx - 1], data[true_x_idx, true_y_idx], data[true_x_idx, true_y_idx + 1]
                denom = alpha - 2*beta + gamma
                if denom != 0: offset_y = 0.5 * (alpha - gamma) / denom

            ppm_step_x = ppm_x[1] - ppm_x[0] if len(ppm_x) > 1 else 0
            ppm_step_y = ppm_y[1] - ppm_y[0] if len(ppm_y) > 1 else 0

            refined_ppm_x = ppm_x[true_x_idx] + offset_x * ppm_step_x
            refined_ppm_y = ppm_y[true_y_idx] + offset_y * ppm_step_y

            self.peak_counter += 1
            self.picked_peaks.append({
                'id': self.peak_counter, 
                'ppm_x': refined_ppm_x, 
                'ppm_y': refined_ppm_y,
                'ppm_z': None,
                'closest_z': None
            })

        elif data.ndim == 3:
            if click_z_idx is None or ppm_z is None:
                return self.picked_peaks

            y_idx_center = np.argmin(np.abs(ppm_y - click_ppm_y))
            z_idx_center = click_z_idx
            window_z = 2 

            start_x, end_x = max(0, x_idx_center - window), min(len(ppm_x), x_idx_center + window + 1)
            start_y, end_y = max(0, y_idx_center - window), min(len(ppm_y), y_idx_center + window + 1)
            start_z, end_z = max(0, z_idx_center - window_z), min(len(ppm_z), z_idx_center + window_z + 1)

            local_data = data[start_z:end_z, start_y:end_y, start_x:end_x]
            if local_data.size == 0: 
                return self.picked_peaks

            sign = 1 if local_data[z_idx_center - start_z, y_idx_center - start_y, x_idx_center - start_x] >= 0 else -1
            
            if sign > 0:
                max_idx = np.unravel_index(np.argmax(local_data), local_data.shape)
            else:
                max_idx = np.unravel_index(np.argmin(local_data), local_data.shape)

            true_z_idx = start_z + max_idx[0]
            true_y_idx = start_y + max_idx[1]
            true_x_idx = start_x + max_idx[2]

            peak_intensity = data[true_z_idx, true_y_idx, true_x_idx]
            if abs(peak_intensity) < threshold:
                return self.picked_peaks

            offset_x, offset_y, offset_z = 0, 0, 0
            
            if 0 < true_x_idx < len(ppm_x) - 1:
                a, b, c = data[true_z_idx, true_y_idx, true_x_idx - 1], data[true_z_idx, true_y_idx, true_x_idx], data[true_z_idx, true_y_idx, true_x_idx + 1]
                d = a - 2*b + c
                if d != 0: offset_x = 0.5 * (a - c) / d

            if 0 < true_y_idx < len(ppm_y) - 1:
                a, b, c = data[true_z_idx, true_y_idx - 1, true_x_idx], data[true_z_idx, true_y_idx, true_x_idx], data[true_z_idx, true_y_idx + 1, true_x_idx]
                d = a - 2*b + c
                if d != 0: offset_y = 0.5 * (a - c) / d

            if 0 < true_z_idx < len(ppm_z) - 1:
                a, b, c = data[true_z_idx - 1, true_y_idx, true_x_idx], data[true_z_idx, true_y_idx, true_x_idx], data[true_z_idx + 1, true_y_idx, true_x_idx]
                d = a - 2*b + c
                if d != 0: offset_z = 0.5 * (a - c) / d

            ppm_step_x = ppm_x[1] - ppm_x[0] if len(ppm_x) > 1 else 0
            ppm_step_y = ppm_y[1] - ppm_y[0] if len(ppm_y) > 1 else 0
            ppm_step_z = ppm_z[1] - ppm_z[0] if len(ppm_z) > 1 else 0

            refined_ppm_x = ppm_x[true_x_idx] + offset_x * ppm_step_x
            refined_ppm_y = ppm_y[true_y_idx] + offset_y * ppm_step_y
            refined_ppm_z = ppm_z[true_z_idx] + offset_z * ppm_step_z

            closest_z_idx = round(true_z_idx + offset_z) 

            self.peak_counter += 1
            self.picked_peaks.append({
                'id': self.peak_counter, 
                'ppm_x': refined_ppm_x, 
                'ppm_y': refined_ppm_y,
                'ppm_z': refined_ppm_z,
                'closest_z': closest_z_idx
            })

        return self.picked_peaks

#---------------------------------------------------------------------------------------
       
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

#---------------------------------------------------------------------------------------

    def auto_pick(self, data, ppm_x, ppm_y, threshold=0.0, ppm_z=None):
        """Scans the entire spectrum for local extrema above the noise threshold."""
        if data is None or data.size == 0:
            return self.picked_peaks

        ppm_step_x = ppm_x[1] - ppm_x[0] if len(ppm_x) > 1 else 0

        if data.ndim == 1:
            # --- FIX: Only pick positive maxima in 1D to ignore noise valleys ---
            is_max = (data > threshold) & (data >= np.roll(data, 1)) & (data > np.roll(data, -1))
            
            is_max[0] = is_max[-1] = False
            indices = np.where(is_max)[0]
            
            for idx in indices:
                alpha, beta, gamma = data[idx - 1], data[idx], data[idx + 1]
                denom = alpha - 2*beta + gamma
                offset = 0.5 * (alpha - gamma) / denom if denom != 0 else 0
                
                refined_ppm_x = ppm_x[idx] + offset * ppm_step_x
                
                self.peak_counter += 1
                self.picked_peaks.append({
                    'id': self.peak_counter, 
                    'ppm_x': refined_ppm_x, 
                    'ppm_y': data[idx], 
                    'ppm_z': None,
                    'closest_z': None,
                    'intensity': data[idx]
                })
                
        elif data.ndim == 2:
            ppm_step_y = ppm_y[1] - ppm_y[0] if len(ppm_y) > 1 else 0
            
            # OPTIMIZATION: Initialize with the threshold mask instead of np.ones
            is_max = data > threshold
            is_min = data < -threshold
            
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    shifted = np.roll(data, shift=(dx, dy), axis=(0, 1))
                    
                    if dx < 0 or (dx == 0 and dy < 0):
                        is_max &= (data >= shifted)
                        is_min &= (data <= shifted)
                    else:
                        is_max &= (data > shifted)
                        is_min &= (data < shifted)
            
            is_max[0, :] = is_max[-1, :] = is_max[:, 0] = is_max[:, -1] = False
            is_min[0, :] = is_min[-1, :] = is_min[:, 0] = is_min[:, -1] = False
            
            x_indices, y_indices = np.where(is_max | is_min)
            
            for x_idx, y_idx in zip(x_indices, y_indices):
                offset_x, offset_y = 0, 0
                
                a, b, c = data[x_idx - 1, y_idx], data[x_idx, y_idx], data[x_idx + 1, y_idx]
                denom_x = a - 2*b + c
                if denom_x != 0: offset_x = 0.5 * (a - c) / denom_x
                
                a, b, c = data[x_idx, y_idx - 1], data[x_idx, y_idx], data[x_idx, y_idx + 1]
                denom_y = a - 2*b + c
                if denom_y != 0: offset_y = 0.5 * (a - c) / denom_y
                
                refined_ppm_x = ppm_x[x_idx] + offset_x * ppm_step_x
                refined_ppm_y = ppm_y[y_idx] + offset_y * ppm_step_y
                
                self.peak_counter += 1
                self.picked_peaks.append({
                    'id': self.peak_counter, 
                    'ppm_x': refined_ppm_x, 
                    'ppm_y': refined_ppm_y,
                    'ppm_z': None,
                    'closest_z': None,
                    'intensity': data[x_idx, y_idx] # NEW: Save the true peak height
                })

        elif data.ndim == 3:
            if ppm_z is None: return self.picked_peaks
            
            ppm_step_y = ppm_y[1] - ppm_y[0] if len(ppm_y) > 1 else 0
            ppm_step_z = ppm_z[1] - ppm_z[0] if len(ppm_z) > 1 else 0

            # OPTIMIZATION: Initialize with the threshold mask instead of np.ones
            is_max = data > threshold
            is_min = data < -threshold

            for dz in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    for dx in [-1, 0, 1]:
                        if dx == 0 and dy == 0 and dz == 0:
                            continue
                        shifted = np.roll(data, shift=(dz, dy, dx), axis=(0, 1, 2))
                        
                        if dz < 0 or (dz == 0 and dy < 0) or (dz == 0 and dy == 0 and dx < 0):
                            is_max &= (data >= shifted)
                            is_min &= (data <= shifted)
                        else:
                            is_max &= (data > shifted)
                            is_min &= (data < shifted)

            is_max[0, :, :] = is_max[-1, :, :] = False
            is_max[:, 0, :] = is_max[:, -1, :] = False
            is_max[:, :, 0] = is_max[:, :, -1] = False

            is_min[0, :, :] = is_min[-1, :, :] = False
            is_min[:, 0, :] = is_min[:, -1, :] = False
            is_min[:, :, 0] = is_min[:, :, -1] = False

            z_indices, y_indices, x_indices = np.where(is_max | is_min)

            for z_idx, y_idx, x_idx in zip(z_indices, y_indices, x_indices):
                offset_x, offset_y, offset_z = 0, 0, 0

                a, b, c = data[z_idx, y_idx, x_idx - 1], data[z_idx, y_idx, x_idx], data[z_idx, y_idx, x_idx + 1]
                denom_x = a - 2*b + c
                if denom_x != 0: offset_x = 0.5 * (a - c) / denom_x

                a, b, c = data[z_idx, y_idx - 1, x_idx], data[z_idx, y_idx, x_idx], data[z_idx, y_idx + 1, x_idx]
                denom_y = a - 2*b + c
                if denom_y != 0: offset_y = 0.5 * (a - c) / denom_y

                a, b, c = data[z_idx - 1, y_idx, x_idx], data[z_idx, y_idx, x_idx], data[z_idx + 1, y_idx, x_idx]
                denom_z = a - 2*b + c
                if denom_z != 0: offset_z = 0.5 * (a - c) / denom_z

                refined_ppm_x = ppm_x[x_idx] + offset_x * ppm_step_x
                refined_ppm_y = ppm_y[y_idx] + offset_y * ppm_step_y
                refined_ppm_z = ppm_z[z_idx] + offset_z * ppm_step_z

                closest_z_idx = round(z_idx + offset_z)

                self.peak_counter += 1
                self.picked_peaks.append({
                    'id': self.peak_counter, 
                    'ppm_x': refined_ppm_x, 
                    'ppm_y': refined_ppm_y,
                    'ppm_z': refined_ppm_z,
                    'closest_z': closest_z_idx,
                    'intensity': data[z_idx, y_idx, x_idx] # NEW: Save the true peak height
                })

        return self.picked_peaks