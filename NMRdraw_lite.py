#!/opt/homebrew/Caskroom/miniconda/base/bin/python
import sys
import os
from PyQt6.QtWidgets import QApplication

from PyQt6.QtCore import Qt, QTimer, qInstallMessageHandler, QtMsgType

from ui.main_window import NMRViewerApp

def suppress_qt_warnings(mode, context, message):
    if "QGestureManager::deliverEvents" in message:
        return
    # Print any other warnings or errors to the console
    print(message, file=sys.stderr)

if __name__ == "__main__":
    qInstallMessageHandler(suppress_qt_warnings)
    app = QApplication(sys.argv)
    passed_files = [f for f in sys.argv[1:] if os.path.isfile(f)]
    viewer = NMRViewerApp(file_paths=passed_files)
    viewer.show()
    sys.exit(app.exec())