"""
Panel to review and edit each detected joint.
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QDoubleSpinBox, QGroupBox, QScrollArea, QFrame, QSizePolicy,
    QPushButton,
)
from PyQt5.QtCore import Qt, pyqtSignal
from core.joint_detector import DetectedJoint, JointType


class JointPanel(QWidget):
    joint_changed = pyqtSignal(str, dict)   # (joint_name, new_data)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._joints: list[DetectedJoint] = []
        self._widgets: dict = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        title = QLabel('<b>Detected Joints</b>')
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self._container = QWidget()
        self._vbox = QVBoxLayout(self._container)
        self._vbox.setAlignment(Qt.AlignTop)
        scroll.setWidget(self._container)
        layout.addWidget(scroll)

    def populate(self, joints: list[DetectedJoint]):
        self._joints = joints
        self._widgets = {}

        # Clear existing
        while self._vbox.count():
            item = self._vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for j in joints:
            self._vbox.addWidget(self._make_joint_card(j))

    def _make_joint_card(self, j: DetectedJoint) -> QGroupBox:
        conf_pct = int(j.confidence * 100)
        box = QGroupBox(f"{j.name}  [{conf_pct}% confidence]")
        layout = QVBoxLayout(box)

        # Parent → Child
        row1 = QHBoxLayout()
        row1.addWidget(QLabel(f"{j.parent_link}  →  {j.child_link}"))
        layout.addLayout(row1)

        # Joint type selector
        row2 = QHBoxLayout()
        row2.addWidget(QLabel('Type:'))
        combo = QComboBox()
        for jt in JointType:
            if jt != JointType.UNKNOWN:
                combo.addItem(jt.value)
        combo.setCurrentText(j.joint_type.value)
        combo.currentTextChanged.connect(
            lambda text, jname=j.name: self._on_type_changed(jname, text)
        )
        row2.addWidget(combo)
        row2.addStretch()
        layout.addLayout(row2)

        # Limits row (only relevant for revolute/prismatic)
        row3 = QHBoxLayout()
        row3.addWidget(QLabel('Limits (lower / upper):'))
        lower_spin = self._spin(j.limit_lower, -2 * 3.14159, 2 * 3.14159)
        upper_spin = self._spin(j.limit_upper, -2 * 3.14159, 2 * 3.14159)
        row3.addWidget(lower_spin)
        row3.addWidget(upper_spin)
        layout.addLayout(row3)

        # Effort / velocity
        row4 = QHBoxLayout()
        row4.addWidget(QLabel('Effort (N·m):'))
        effort_spin = self._spin(j.effort, 0, 10000, decimals=1)
        row4.addWidget(effort_spin)
        row4.addWidget(QLabel('Vel (rad/s):'))
        vel_spin = self._spin(j.velocity, 0, 100, decimals=2)
        row4.addWidget(vel_spin)
        layout.addLayout(row4)

        # Evidence text
        ev_label = QLabel(f'<i>{j.evidence}</i>')
        ev_label.setWordWrap(True)
        layout.addWidget(ev_label)

        self._widgets[j.name] = {
            'combo': combo,
            'lower': lower_spin,
            'upper': upper_spin,
            'effort': effort_spin,
            'vel': vel_spin,
        }
        return box

    def _spin(self, value, minimum, maximum, decimals=4) -> QDoubleSpinBox:
        sp = QDoubleSpinBox()
        sp.setRange(minimum, maximum)
        sp.setDecimals(decimals)
        sp.setValue(value)
        sp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return sp

    def _on_type_changed(self, joint_name: str, text: str):
        self.joint_changed.emit(joint_name, {'type': text})

    def get_joint_data(self, joint_name: str) -> dict:
        w = self._widgets.get(joint_name)
        if not w:
            return {}
        return {
            'type':        w['combo'].currentText(),
            'limit_lower': w['lower'].value(),
            'limit_upper': w['upper'].value(),
            'effort':      w['effort'].value(),
            'velocity':    w['vel'].value(),
        }

    def get_all_joint_overrides(self) -> dict:
        return {name: self.get_joint_data(name) for name in self._widgets}
