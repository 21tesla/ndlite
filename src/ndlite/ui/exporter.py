from PyQt6.QtCore import QTimer

class Exporter:

    def __init__(self, main_window):
        self.main_window = main_window
#---------------------------------------------------------------------------------------

    def export_spectrum(self):
        self._export_with_mode('spectrum')

#---------------------------------------------------------------------------------------

    def export_peaks_spectrum(self):
        self._export_with_mode('peaks')

#---------------------------------------------------------------------------------------

    def _export_with_mode(self, mode):
        self.main_window.is_exporting = True
        
        # Save visibility of peak elements for all spectra
        scatter_vis = {idx: scatter.isVisible() for idx, scatter in self.main_window.peak_scatter_items.items()}
        text_vis = {}
        for idx, items in self.main_window.peak_text_items.items():
            text_vis[idx] = {pid: item.isVisible() for pid, item in items.items()}

        self._export_state = {
            'hline': self.main_window.hline.isVisible(),
            'vline': self.main_window.vline.isVisible(),
            'trace': self.main_window.trace_curve.isVisible(),
            'scatter': scatter_vis,
            'texts': text_vis
        }
        
        self.main_window.hline.setVisible(False)
        self.main_window.vline.setVisible(False)
        self.main_window.trace_curve.setVisible(False)
        self.main_window.plot_2d.setTitle(" ")
        
        if mode == 'spectrum':
            # Hide all peaks
            for scatter in self.main_window.peak_scatter_items.values():
                scatter.setVisible(False)
            for items in self.main_window.peak_text_items.values():
                for item in items.values():
                    item.setVisible(False)
        elif mode == 'peaks':
            # Peaks are already shown based on their visibility flags
            pass
                
        scene = self.main_window.plot_2d.scene()
        scene.contextMenuItem = self.main_window.plot_2d.getPlotItem()
        scene.showExportDialog()
        
        if not hasattr(self, 'export_poll_timer'):
            self.export_poll_timer = QTimer(self.main_window)
            self.export_poll_timer.timeout.connect(self._check_export_dialog_closed)
        self.export_poll_timer.start(200)

#---------------------------------------------------------------------------------------

    def _check_export_dialog_closed(self):
        try:
            scene = self.main_window.plot_2d.scene()
            if not hasattr(scene, 'exportDialog') or scene.exportDialog is None or not scene.exportDialog.isVisible():
                self.export_poll_timer.stop()
                self._restore_export_state()
        except RuntimeError:
            self.export_poll_timer.stop()
            self._restore_export_state()

#---------------------------------------------------------------------------------------

    def _restore_export_state(self):
        self.main_window.is_exporting = False
        
        if hasattr(self, '_export_state'):
            self.main_window.hline.setVisible(self._export_state.get('hline', False))
            self.main_window.vline.setVisible(self._export_state.get('vline', False))
            self.main_window.trace_curve.setVisible(self._export_state.get('trace', False))
            
            scatter_vis = self._export_state.get('scatter', {})
            for idx, scatter in self.main_window.peak_scatter_items.items():
                scatter.setVisible(scatter_vis.get(idx, False))
                
            text_vis = self._export_state.get('texts', {})
            for idx, items in self.main_window.peak_text_items.items():
                if idx in text_vis:
                    for pid, item in items.items():
                        item.setVisible(text_vis[idx].get(pid, False))
                
        self.main_window.set_mode(self.main_window.current_mode)
