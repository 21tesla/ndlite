from PyQt6.QtWidgets import QFileDialog, QMessageBox
import pyqtgraph.exporters as exporters

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
        # Safety check: peak_scatter_items may contain None if markers haven't been created yet
        scatter_vis = {}
        for idx, scatter in enumerate(self.main_window.peak_scatter_items):
            if scatter is not None:
                scatter_vis[idx] = scatter.isVisible()
            else:
                scatter_vis[idx] = False

        text_vis = {}
        for idx, items in enumerate(self.main_window.peak_text_items):
            text_vis[idx] = {pid: item.isVisible() for pid, item in items.items()}

        self._export_state = {
            'hline': self.main_window.hline.isVisible(),
            'vline': self.main_window.vline.isVisible(),
            'trace': self.main_window.trace_curve.isVisible(),
            'scatter': scatter_vis,
            'texts': text_vis
        }
        
        # Hide interactive elements for export
        self.main_window.hline.setVisible(False)
        self.main_window.vline.setVisible(False)
        self.main_window.trace_curve.setVisible(False)
        self.main_window.plot_2d.setTitle(" ")
        
        if mode == 'spectrum':
            # Hide all peaks
            for scatter in self.main_window.peak_scatter_items:
                if scatter is not None:
                    scatter.setVisible(False)
            for items in self.main_window.peak_text_items:
                for item in items.values():
                    item.setVisible(False)
        elif mode == 'peaks':
            # Peaks are already shown based on their visibility flags
            pass
                
        # Use a standard QFileDialog instead of the finicky pyqtgraph export dialog
        file_filter = "PNG Image (*.png);;SVG Vector Graphics (*.svg);;PDF Document (*.pdf);;CSV Data (*.csv);;All Files (*)"
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self.main_window, "Export Spectrum", "", file_filter
        )

        if file_path:
            try:
                plot_item = self.main_window.plot_2d.getPlotItem()
                if "SVG" in selected_filter:
                    exporter = exporters.SVGExporter(plot_item)
                elif "PDF" in selected_filter:
                    exporter = exporters.PrintExporter(plot_item)
                elif "CSV" in selected_filter:
                    exporter = exporters.CSVExporter(plot_item)
                else:
                    exporter = exporters.ImageExporter(plot_item)
                
                exporter.export(file_path)
            except Exception as e:
                QMessageBox.critical(self.main_window, "Export Error", f"Failed to export: {str(e)}")

        # Always restore state
        self._restore_export_state()

#---------------------------------------------------------------------------------------

    def _restore_export_state(self):
        self.main_window.is_exporting = False
        
        if hasattr(self, '_export_state'):
            self.main_window.hline.setVisible(self._export_state.get('hline', False))
            self.main_window.vline.setVisible(self._export_state.get('vline', False))
            self.main_window.trace_curve.setVisible(self._export_state.get('trace', False))
            
            scatter_vis = self._export_state.get('scatter', {})
            for idx, scatter in enumerate(self.main_window.peak_scatter_items):
                if scatter is not None:
                    scatter.setVisible(scatter_vis.get(idx, False))
                
            text_vis = self._export_state.get('texts', {})
            for idx, items in enumerate(self.main_window.peak_text_items):
                if idx in text_vis:
                    for pid, item in items.items():
                        item.setVisible(text_vis[idx].get(pid, False))
                
        self.main_window.set_mode(self.main_window.current_mode)
