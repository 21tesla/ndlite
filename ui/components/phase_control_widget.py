from PyQt6.QtWidgets import QGroupBox, QGridLayout, QLabel, QSlider, QDoubleSpinBox
from PyQt6.QtCore import Qt

class PhaseControlWidget(QGroupBox):

    def __init__(self, parent=None):
        super().__init__("Phase Correction", parent)
        self.phase_ui = {}
        self.on_phase_changed_callback = None
        self.on_phase_released_callback = None
        self.init_ui()
        self.setEnabled(False)

#---------------------------------------------------------------------------------------

    def init_ui(self):
        grid_phase = QGridLayout()
        params = [
            ("p0", "P0 Phase", -180, 180, 0.1),
            ("p1", "P1 Phase", -360, 360, 0.1)
        ]
        for row, (key, label, vmin, vmax, step) in enumerate(params):
            lbl = QLabel(label)
            sl = QSlider(Qt.Orientation.Horizontal)
            sl.setMinimum(int(vmin * 10))
            sl.setMaximum(int(vmax * 10))
            sl.setValue(0)
            sb = QDoubleSpinBox()
            sb.setRange(vmin, vmax)
            sb.setSingleStep(step)
            sb.setDecimals(1)
            sb.setValue(0.0)
            sb.setMinimumWidth(80)

            def make_connections(k, slider, spinbox):
                spinbox.setKeyboardTracking(False)
                
                def sl_changed(val):
                    spinbox.blockSignals(True)
                    try:
                        spinbox.setValue(round(val / 10.0, 1))
                    finally:
                        spinbox.blockSignals(False)
                    if self.on_phase_changed_callback:
                        self.on_phase_changed_callback(k, val / 10.0)

                def sb_changed(val):
                    slider.blockSignals(True)
                    try:
                        slider.setValue(int(round(val * 10)))
                    finally:
                        slider.blockSignals(False)
                    if self.on_phase_changed_callback:
                        self.on_phase_changed_callback(k, val)
                    if self.on_phase_released_callback:
                        self.on_phase_released_callback()

                slider.valueChanged.connect(sl_changed)
                spinbox.valueChanged.connect(sb_changed)
                
                def sl_released():
                    if self.on_phase_released_callback:
                        self.on_phase_released_callback()
                slider.sliderReleased.connect(sl_released)

            make_connections(key, sl, sb)

            grid_phase.addWidget(lbl, row, 0)
            grid_phase.addWidget(sl, row, 1)
            grid_phase.addWidget(sb, row, 2)
            self.phase_ui[key] = (sl, sb)
                        
        self.setLayout(grid_phase)

#---------------------------------------------------------------------------------------

    def update_from_state(self, axis, phase_state):
        self.setTitle(f"Phase Correction ({axis.upper()}-Axis)")
        state = phase_state[axis]
        for key, val in state.items():
            sl, sb = self.phase_ui[key]
            sl.blockSignals(True)
            sb.blockSignals(True)
            sl.setValue(int(val * 10))
            sb.setValue(val)
            sl.blockSignals(False)
            sb.blockSignals(False)
