import nmrglue as ng
import numpy as np
from scipy.signal import hilbert
import scipy.sparse as sparse
from scipy.sparse.linalg import spsolve

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
        trace = trace.astype(float) 
        if is_real: 
            # Pad the array to prevent FFT wrap-around artifacts (Gibbs ringing)
            pad_len = len(trace) // 2
            padded = np.pad(trace, (pad_len, pad_len), mode='reflect')
            analytic = hilbert(padded)
            # Slice the original trace back out of the padded analytic signal
            trace = analytic[pad_len:-pad_len]
            
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
        
#---------------------------------------------------------------------        
        
    @staticmethod
    def baseline_als(y, lam=1e5, p=0.001, niter=10):
        """
        Asymmetric Least Squares Smoothing.
        lam: Smoothness parameter (1e4 to 1e8 is typical for NMR).
        p: Asymmetry parameter (0.001 to 0.01 is typical).
        """
        L = len(y)
        # Fix 1: Explicitly declare dtype=float to resolve FutureWarning
        D = sparse.diags([1, -2, 1], [0, -1, -2], shape=(L, L - 2), dtype=float)
        D = lam * D.dot(D.transpose())
        w = np.ones(L)
        
        for i in range(niter):
            W = sparse.spdiags(w, 0, L, L)
            Z = W + D
            
            # Fix 2: Convert Z to CSR format before solving to resolve SparseEfficiencyWarning
            z = spsolve(Z.tocsr(), w * y)
            w = p * (y > z) + (1 - p) * (y < z)
            
        return z
        
#---------------------------------------------------------------------        

    @staticmethod
    def lorentzian(x, amp, cen, wid):
        """
        Ideal NMR lineshape. 
        wid = half-width at half-maximum (HWHM)
        """
        return (amp * wid**2) / ((x - cen)**2 + wid**2)

#---------------------------------------------------------------------        
        

    @staticmethod
    def gaussian(x, amp, cen, wid):
        """
        Inhomogeneously broadened lineshape.
        wid = standard deviation (sigma)
        """
        return amp * np.exp(-((x - cen)**2) / (2 * wid**2))

#---------------------------------------------------------------------        
        
    @staticmethod
    def pseudo_voigt(x, amp, cen, wid, eta):
        """
        Linear combination for real-world NMR peaks.
        eta = mixing parameter (0.0 to 1.0). 1.0 is pure Lorentzian.
        """
        l_part = DataHandler.lorentzian(x, amp, cen, wid)
        g_part = DataHandler.gaussian(x, amp, cen, wid)
        return (eta * l_part) + ((1 - eta) * g_part)

#---------------------------------------------------------------------        
               
    @staticmethod
    def calc_analytical_area(amp, wid, shape_type='lorentzian', eta=1.0):
        """
        Calculates the exact integral (area under the curve) from the fitted parameters.
        """
        if shape_type == 'lorentzian':
            return amp * wid * np.pi
        elif shape_type == 'gaussian':
            return amp * wid * np.sqrt(2 * np.pi)
        elif shape_type == 'pseudo_voigt':
            l_area = amp * wid * np.pi
            g_area = amp * wid * np.sqrt(2 * np.pi)
            return (eta * l_area) + ((1 - eta) * g_area)
        return 0.0