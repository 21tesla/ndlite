#!/opt/homebrew/Caskroom/miniconda/base/bin/python
import sys
import os
from PyQt6.QtWidgets import QApplication

# Import your newly modularized main window
from ui.main_window import NMRViewerApp

if __name__ == "__main__":
    app = QApplication(sys.argv)
    passed_files = [f for f in sys.argv[1:] if os.path.isfile(f)]
    viewer = NMRViewerApp(file_paths=passed_files)
    viewer.show()
    sys.exit(app.exec())
