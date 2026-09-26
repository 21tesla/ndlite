import unittest
import sys
import os
from PyQt6.QtWidgets import QApplication
import nmrglue as ng
import numpy as np
from ndlite.ui.main_window import NMRViewerApp

# Create a single QApplication instance for all tests
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

class TestSpectrumOverlay(unittest.TestCase):
    def test_different_sweep_widths_overlay(self):
        # We use the permanent example files in the repository
        file1 = os.path.join("example", "2D_HSQC", "hsqc-1.ft2")
        file2 = os.path.join("example", "2D_HSQC", "hsqc-2.ft2")
        
        # Instantiate NMRViewerApp
        viewer = NMRViewerApp()
        
        # Load the files
        viewer.io_controller.load_files([file1, file2])
        
        # Verify both files are loaded
        self.assertEqual(len(viewer.raw_data_list), 2)
        self.assertEqual(len(viewer.ppm_x_list), 2)
        self.assertEqual(len(viewer.ppm_y_list), 2)
        
        # Verify dimensions shape
        self.assertEqual(viewer.raw_data_list[0].ndim, 2)
        
        # Verify active index is initially 0
        self.assertEqual(viewer.active_index, 0)
        self.assertTrue(np.allclose(viewer.ppm_x, viewer.ppm_x_list[0]))
        self.assertTrue(np.allclose(viewer.ppm_y, viewer.ppm_y_list[0]))

        # Simulate selecting spectrum 1 as active
        viewer.io_controller.on_selection_changed(1)
        self.assertEqual(viewer.active_index, 1)
        # Verify main window active axes are successfully updated to spectrum 1
        self.assertTrue(np.allclose(viewer.ppm_x, viewer.ppm_x_list[1]))
        self.assertTrue(np.allclose(viewer.ppm_y, viewer.ppm_y_list[1]))

        # Capture the active spectrum's axes before flipping
        x_before = viewer.ppm_x.copy()
        y_before = viewer.ppm_y.copy()

        # Simulate flipping axes
        viewer.flip_axes()

        # Verify the flip actually swapped the axes on the active spectrum
        self.assertTrue(np.allclose(viewer.ppm_x, y_before))
        self.assertTrue(np.allclose(viewer.ppm_y, x_before))
        # The per-spectrum lists must be swapped too
        self.assertTrue(np.allclose(viewer.ppm_x_list[1], y_before))
        self.assertTrue(np.allclose(viewer.ppm_y_list[1], x_before))

        # Clean up
        viewer.close()

if __name__ == '__main__':
    unittest.main()
