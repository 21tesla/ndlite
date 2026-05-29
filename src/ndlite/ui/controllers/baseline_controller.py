from PyQt6.QtWidgets import QMessageBox
import numpy as np

class BaselineController:
    def __init__(self, main_window):
        self.main_window = main_window

    def run_als_baseline(self):
        if not self.main_window._check_1d_baseline_validity(): return
        
        active_idx = self.main_window.active_index
        data_1d = self.main_window.raw_data_list[active_idx]
        
        baseline = self.main_window.data_handler.baseline_als(np.real(data_1d))
        
        self.main_window.baseline_corrections[active_idx] = baseline
        
        self.main_window.recompute_contours()
        self.main_window.plot_2d.setTitle("Success: ALS Baseline correction applied.")

    def start_interactive_baseline(self):
        if not self.main_window._check_1d_baseline_validity(): return
        
        if not hasattr(self.main_window, 'baseline_anchors'):
            self.main_window.baseline_anchors = []
            import pyqtgraph as pg
            self.main_window.baseline_scatter = pg.ScatterPlotItem(size=10, pen=pg.mkPen('k'), brush=pg.mkBrush(0, 255, 0, 150))
            self.main_window.plot_2d.addItem(self.main_window.baseline_scatter)
            
        self.main_window.baseline_anchors.clear()
        self.main_window.baseline_scatter.setData([])
        self.main_window.baseline_scatter.setVisible(True)
        self.main_window.set_mode('baseline_interactive')
        self.main_window.plot_2d.setTitle("Interactive Baseline: Left-click to add anchors, Right-click to exit.")

    def clear_baseline(self):
        if not self.main_window._check_1d_baseline_validity(): return
        
        active_idx = self.main_window.active_index
        if hasattr(self.main_window, 'baseline_corrections') and self.main_window.baseline_corrections[active_idx] is not None:
            self.main_window.baseline_corrections[active_idx] = None
            self.main_window.recompute_contours()
            self.main_window.plot_2d.setTitle("Success: Baseline correction cleared.")
        else:
            self.main_window.plot_2d.setTitle("No baseline correction to clear.")
