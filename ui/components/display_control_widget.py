from PyQt6.QtWidgets import QGroupBox, QGridLayout, QLabel, QSlider, QDoubleSpinBox, QSpinBox
from PyQt6.QtCore import Qt

class DisplayControlWidget(QGroupBox):
    def __init__(self, prefs, parent=None):
        super().__init__("Display Controls", parent)
        self.prefs = prefs
        self.cont_sliders = {}
        self.cont_widgets = {}
        self.on_changed_callback = None
        self.init_ui()

    def init_ui(self):
        grid_cont = QGridLayout()
        c_prefs = self.prefs["controls"]
        
        cont_params = [
            ("base", c_prefs["base"]["label"], c_prefs["base"]["min"], c_prefs["base"]["max"], c_prefs["base"]["default"], c_prefs["base"]["is_int"]),
            ("scale", c_prefs["scale"]["label"], c_prefs["scale"]["min"], c_prefs["scale"]["max"], c_prefs["scale"]["default"], c_prefs["scale"]["is_int"]),
            ("count", c_prefs["count"]["label"], c_prefs["count"]["min"], c_prefs["count"]["max"], c_prefs["count"]["default"], c_prefs["count"]["is_int"]),
            ("offset", c_prefs["offset"]["label"], c_prefs["offset"]["min"], c_prefs["offset"]["max"], c_prefs["offset"]["default"], c_prefs["offset"]["is_int"])
        ]
        
        for row, (key, label, vmin, vmax, vdef, is_int) in enumerate(cont_params):
            lbl = QLabel(label)
            sl = QSlider(Qt.Orientation.Horizontal)

            if is_int:
                sl.setMinimum(int(vmin))
                sl.setMaximum(int(vmax))
                sl.setValue(int(vdef))
                sb = QSpinBox()
                sb.setRange(int(vmin), int(vmax))
                sb.setSingleStep(1)
                sb.setValue(int(vdef))
                sb.setMinimumWidth(80)

                def make_conn_int(k, slider, spinbox):
                    spinbox.setKeyboardTracking(False)
                    
                    def sl_changed(val):
                        spinbox.blockSignals(True)
                        spinbox.setValue(val)
                        spinbox.blockSignals(False)

                    def sb_changed(val):
                        slider.blockSignals(True)
                        slider.setValue(val)
                        slider.blockSignals(False)
                        if self.on_changed_callback:
                            self.on_changed_callback()

                    slider.valueChanged.connect(sl_changed)
                    spinbox.valueChanged.connect(sb_changed)
                    
                    def sl_released():
                        if self.on_changed_callback:
                            self.on_changed_callback()
                    slider.sliderReleased.connect(sl_released)
                make_conn_int(key, sl, sb)
            else:
                sl.setMinimum(int(vmin * 100))
                sl.setMaximum(int(vmax * 100))
                sl.setValue(int(vdef * 100))
                sb = QDoubleSpinBox()
                sb.setRange(vmin, vmax)
                sb.setSingleStep(0.1)
                sb.setDecimals(2)
                sb.setValue(vdef)
                sb.setMinimumWidth(80)

                def make_conn_float(k, slider, spinbox):
                    spinbox.setKeyboardTracking(False)
                    
                    def sl_changed(val):
                        spinbox.blockSignals(True)
                        try:
                            spinbox.setValue(round(val / 100.0, 2))
                        finally:
                            spinbox.blockSignals(False)

                    def sb_changed(val):
                        slider.blockSignals(True)
                        try:
                            slider.setValue(int(round(val * 100)))
                        finally:
                            slider.blockSignals(False)
                        if self.on_changed_callback:
                            self.on_changed_callback()

                    slider.valueChanged.connect(sl_changed)
                    spinbox.valueChanged.connect(sb_changed)
                    
                    def sl_released():
                        if self.on_changed_callback:
                            self.on_changed_callback()
                    slider.sliderReleased.connect(sl_released)
                make_conn_float(key, sl, sb)
                
            grid_cont.addWidget(lbl, row, 0)
            grid_cont.addWidget(sl, row, 1)
            grid_cont.addWidget(sb, row, 2)
            self.cont_sliders[key] = sb
            self.cont_widgets[key] = (lbl, sl, sb)
            
        self.setLayout(grid_cont)

    def set_1d_mode(self, is_1d):
        for key in ['base', 'scale', 'count']:
            lbl, sl, sb = self.cont_widgets[key]
            lbl.setEnabled(not is_1d)
            sl.setEnabled(not is_1d)
            sb.setEnabled(not is_1d)

        lbl, sl, sb = self.cont_widgets['offset']
        lbl.setEnabled(is_1d)
        sl.setEnabled(is_1d)
        sb.setEnabled(is_1d)

    def get_value(self, key):
        return self.cont_sliders[key].value()
