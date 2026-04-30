import nmrglue as ng
import numpy as np
from scipy.signal import hilbert

class DataHandler:

#---------------------------------------------------------------------        

    @staticmethod
    def load_file(file_name):
        return ng.pipe.read(file_name)

#---------------------------------------------------------------------        

    @staticmethod
    def calculate_rmsd(data):
        flat_data = data.flatten()
        med = np.median(flat_data)
        mad = np.median(np.abs(flat_data - med))
        sigma = mad * 1.4826
        return sigma if sigma != 0 else np.std(flat_data)

#---------------------------------------------------------------------        

    @staticmethod
    def phase_1d(trace, p0, p1, is_real):
        if is_real: 
            trace = hilbert(trace)
        return np.real(ng.process.proc_base.ps(trace, p0=p0, p1=p1))

#---------------------------------------------------------------------        

    @staticmethod
    def phase_2d(plot_data, x_p0, x_p1, y_p0, y_p1, slice_x_idx, is_real):
        if x_p0 != 0 or x_p1 != 0:
            ax = 1 if slice_x_idx == 1 else 0
            if is_real: plot_data = hilbert(plot_data, axis=ax)
            if ax == 1: plot_data = np.real(ng.process.proc_base.ps(plot_data, p0=x_p0, p1=x_p1))
            else: plot_data = np.real(ng.process.proc_base.ps(plot_data.T, p0=x_p0, p1=x_p1).T)
        
        if y_p0 != 0 or y_p1 != 0:
            ax = 0 if slice_x_idx == 1 else 1
            if is_real: plot_data = hilbert(plot_data, axis=ax)
            if ax == 1: plot_data = np.real(ng.process.proc_base.ps(plot_data, p0=y_p0, p1=y_p1))
            else: plot_data = np.real(ng.process.proc_base.ps(plot_data.T, p0=y_p0, p1=y_p1).T)

        return plot_data.T if slice_x_idx == 1 else plot_data

#---------------------------------------------------------------------        

    @staticmethod
    def phase_z_plane(raw_data, z_p0, z_p1, z_dim, target_z_idx, is_real):
        tmp_data = raw_data.copy()
        if is_real: tmp_data = hilbert(tmp_data, axis=z_dim)
        tmp_data = np.swapaxes(tmp_data, z_dim, -1)
        tmp_data = ng.process.proc_base.ps(tmp_data, p0=z_p0, p1=z_p1)
        tmp_data = np.swapaxes(tmp_data, z_dim, -1)
        slices = [slice(None)] * 3
        slices[z_dim] = target_z_idx
        return np.real(tmp_data[tuple(slices)])

#---------------------------------------------------------------------        

    @staticmethod
    def get_contour_levels(vis_data, base_mult, scale_fact, count):
        noise_rmsd = DataHandler.calculate_rmsd(vis_data)
        base_level = noise_rmsd * base_mult
        factors = scale_fact ** np.arange(count)
        
        pos_levels = base_level * factors
        neg_levels = -base_level * factors
        
        v_max, v_min = vis_data.max(), vis_data.min()
        pos_levels = [l for l in pos_levels if l <= v_max]
        neg_levels = [l for l in neg_levels if l >= v_min]
        
        all_levels = pos_levels + neg_levels
        is_pos = [True] * len(pos_levels) + [False] * len(neg_levels)
        
        return all_levels, is_pos