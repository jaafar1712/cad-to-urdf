"""
Panel to review and edit each link's mass and material.
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QDoubleSpinBox, QGroupBox, QScrollArea, QFrame, QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal
from core.inertia_calculator import MATERIAL_DENSITIES


class LinkPanel(QWidget):
    material_changed = pyqtSignal(str, str)   # (link_name, material)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._links: list = []
        self._widgets: dict = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        title = QLabel('<b>Links / Inertial Properties</b>')
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self._container = QWidget()
        self._vbox = QVBoxLayout(self._container)
        self._vbox.setAlignment(Qt.AlignTop)
        scroll.setWidget(self._container)
        layout.addWidget(scroll)

    def populate(self, links: list):
        self._links = links
        self._widgets = {}

        while self._vbox.count():
            item = self._vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for ld in links:
            self._vbox.addWidget(self._make_link_card(ld))

    def _make_link_card(self, ld: dict) -> QGroupBox:
        box = QGroupBox(ld['name'])
        layout = QVBoxLayout(box)

        # Mass display
        mass_row = QHBoxLayout()
        mass_row.addWidget(QLabel('Mass (kg):'))
        mass_spin = QDoubleSpinBox()
        mass_spin.setRange(0.001, 10000.0)
        mass_spin.setDecimals(4)
        mass_spin.setValue(ld.get('mass', 1.0))
        mass_row.addWidget(mass_spin)
        layout.addLayout(mass_row)

        # Material selector
        mat_row = QHBoxLayout()
        mat_row.addWidget(QLabel('Material:'))
        combo = QComboBox()
        for m in MATERIAL_DENSITIES:
            combo.addItem(m)
        combo.setCurrentText('steel')
        combo.currentTextChanged.connect(
            lambda text, n=ld['name']: self.material_changed.emit(n, text)
        )
        mat_row.addWidget(combo)
        layout.addLayout(mat_row)

        # Inertia summary
        ixx = ld.get('ixx', 0)
        iyy = ld.get('iyy', 0)
        izz = ld.get('izz', 0)
        info = QLabel(
            f'Ixx={ixx:.3e}  Iyy={iyy:.3e}  Izz={izz:.3e} kg·m²'
        )
        info.setStyleSheet('color: gray; font-size: 10px;')
        layout.addWidget(info)

        com = ld.get('center_of_mass', (0, 0, 0))
        com_label = QLabel(
            f'CoM: ({com[0]:.3f}, {com[1]:.3f}, {com[2]:.3f}) m'
        )
        com_label.setStyleSheet('color: gray; font-size: 10px;')
        layout.addWidget(com_label)

        self._widgets[ld['name']] = {
            'mass': mass_spin,
            'material': combo,
        }
        return box

    def get_link_overrides(self, name: str) -> dict:
        w = self._widgets.get(name, {})
        return {
            'mass':     w['mass'].value() if 'mass' in w else None,
            'material': w['material'].currentText() if 'material' in w else 'steel',
        }
