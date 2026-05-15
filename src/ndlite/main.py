#!/opt/homebrew/Caskroom/miniconda/base/bin/python
import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer, qInstallMessageHandler, QtMsgType, QEvent

from ndlite.ui.main_window import NMRViewerApp

def suppress_qt_warnings(mode, context, message):
    if "QGestureManager::deliverEvents" in message:
        return
    print(message, file=sys.stderr)

class NDLiteApplication(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.viewer = None

    def event(self, e):
        if e.type() == QEvent.Type.FileOpen:
            file_path = e.file()
            if self.viewer and os.path.isfile(file_path):
                # Ensure it's called on the main thread via QTimer
                QTimer.singleShot(0, lambda: self.viewer.io_controller.load_files([file_path]))
            return True
        return super().event(e)

def main():
    qInstallMessageHandler(suppress_qt_warnings)
    
    # Process files from command line arguments
    passed_files = []
    for arg in sys.argv[1:]:
        # Skip potential macOS/Qt flags
        if arg.startswith('-'):
            continue
        
        path = os.path.abspath(os.path.expanduser(arg))
        if os.path.isfile(path):
            passed_files.append(path)

    app = NDLiteApplication(sys.argv)
    viewer = NMRViewerApp(file_paths=passed_files)
    app.viewer = viewer
    viewer.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()