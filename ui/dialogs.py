from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt

class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NMRdraw_lite Shortcuts")
        self.setFixedSize(600, 450) 
        
        layout = QVBoxLayout(self)
        
        help_text = """
        <div style='font-size: 12px; line-height: 1.4;'>
            <h3>NMRdraw_lite Shortcuts</h3>
            <table width="100%">
                <tr><td width="120"><b>h</b></td><td>Show this help message</td></tr>
                <tr><td><b>p</b></td><td>Pick Peaks mode (Click near a peak to snap)</td></tr>
                <tr><td><b>Shift + P</b></td><td>Force pick peak exactly at current crosshair</td></tr>
                <tr><td><b>d</b></td><td>Delete Peaks mode (Click near a peak to remove)</td></tr>
                <tr><td><b>Shift + R</b></td><td>Renumber peaks sequentially</td></tr>
                <tr><td><b>Shift + S</b></td><td>Show Peaks</td></tr>
                <tr><td><b>Shift + H</b></td><td>Hide Peaks</td></tr>
                <tr><td><b>s</b></td><td>Save peak list to file</td></tr>
                <tr><td><b>x, y, z</b></td><td>Phase along respective axis</td></tr>
                <tr><td><b>Esc</b></td><td>Exit current mode / return to default</td></tr>
            </table>
            <hr>
            <h3>Mouse Controls</h3>
            <table width="100%">
                <tr><td width="120"><b>Alt + Left Drag</b></td><td>Pan spectrum (simulates Middle-Click)</td></tr>
                <tr><td><b>Right Click</b></td><td>Hide crosshairs</td></tr>
            </table>
        </div>
        """
        
        lbl = QLabel(help_text)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setWordWrap(True)
        layout.addWidget(lbl)
        
        btn = QPushButton("Close")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
