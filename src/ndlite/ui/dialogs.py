from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QDialogButtonBox, QMessageBox
import json
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt

#---------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------

class HelpDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ndlite Shortcuts")
        self.setFixedSize(600, 450) 
        
        layout = QVBoxLayout(self)
        
        help_text = """
        <div style='font-size: 12px; line-height: 1.4;'>
            <h3>ndlite Shortcuts</h3>
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
                <tr><td><b>f</b></td><td>Flip x,y axes</td></tr>                
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

#---------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------

class SettingsDialog(QDialog):

    def __init__(self, prefs, prefs_file, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.resize(400, 500)
        self.prefs = prefs
        self.prefs_file = prefs_file
        self.flat_prefs = self.flatten_dict(self.prefs)
        
        self.init_ui()
#---------------------------------------------------------------------------------------

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Setting", "Value"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        
        self.table.setRowCount(len(self.flat_prefs))
        
        for row, (key, value) in enumerate(self.flat_prefs.items()):
            # Setting Name (Read-only)
            key_item = QTableWidgetItem(key)
            key_item.setFlags(key_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, key_item)
            
            # Setting Value (Editable)
            val_item = QTableWidgetItem(str(value))
            # Store the original type so we can cast it back upon saving
            val_item.setData(Qt.ItemDataRole.UserRole, type(value).__name__)
            self.table.setItem(row, 1, val_item)
            
        layout.addWidget(self.table)
        
        # Save / Cancel Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.save_settings)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

#---------------------------------------------------------------------------------------

    def flatten_dict(self, d, parent_key='', sep='.'):
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self.flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)

#---------------------------------------------------------------------------------------

    def unflatten_dict(self, d, sep='.'):
        result_dict = dict()
        for k, v in d.items():
            parts = k.split(sep)
            d_ref = result_dict
            for part in parts[:-1]:
                if part not in d_ref:
                    d_ref[part] = dict()
                d_ref = d_ref[part]
            d_ref[parts[-1]] = v
        return result_dict

#---------------------------------------------------------------------------------------

    def save_settings(self):
        updated_flat = {}
        try:
            for row in range(self.table.rowCount()):
                key = self.table.item(row, 0).text()
                val_item = self.table.item(row, 1)
                str_val = val_item.text()
                orig_type = val_item.data(Qt.ItemDataRole.UserRole)
                
                # Safely cast back to the original type
                if orig_type == 'int':
                    updated_flat[key] = int(str_val)
                elif orig_type == 'float':
                    updated_flat[key] = float(str_val)
                elif orig_type == 'bool':
                    updated_flat[key] = str_val.lower() in ('true', '1', 'yes')
                else:
                    updated_flat[key] = str_val
                    
            nested_prefs = self.unflatten_dict(updated_flat)
            
            with open(self.prefs_file, 'w') as f:
                json.dump(nested_prefs, f, indent=4)
                
            self.parent().prefs = nested_prefs
            self.accept()
            
            QMessageBox.information(self, "Settings Saved", "Preferences saved successfully.\n\nPlease restart the application for UI changes to fully take effect.")
            
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Input", f"Could not save settings due to a type conversion error:\n{e}\n\nPlease ensure numbers remain as numbers.")
            
            

