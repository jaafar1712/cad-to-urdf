"""
Export dialog: lets user set output directory and package name before export.
"""
import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QDialogButtonBox, QCheckBox,
)
from PyQt5.QtCore import Qt


class ExportDialog(QDialog):

    def __init__(self, default_name: str = 'my_robot', parent=None):
        super().__init__(parent)
        self.setWindowTitle('Export ROS 2 Package')
        self.setMinimumWidth(480)
        self._setup_ui(default_name)

    def _setup_ui(self, default_name: str):
        layout = QVBoxLayout(self)

        # Package name
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel('Package name:'))
        self._name_edit = QLineEdit(default_name)
        name_row.addWidget(self._name_edit)
        layout.addLayout(name_row)

        # Output directory
        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel('Output directory:'))
        self._dir_edit = QLineEdit(os.path.expanduser('~'))
        browse_btn = QPushButton('Browse…')
        browse_btn.clicked.connect(self._browse)
        dir_row.addWidget(self._dir_edit)
        dir_row.addWidget(browse_btn)
        layout.addLayout(dir_row)

        # Options
        self._open_explorer = QCheckBox('Open output folder when done')
        self._open_explorer.setChecked(True)
        layout.addWidget(self._open_explorer)

        # Buttons
        btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal,
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(
            self, 'Select Output Directory', self._dir_edit.text()
        )
        if d:
            self._dir_edit.setText(d)

    @property
    def package_name(self) -> str:
        return self._name_edit.text().strip() or 'my_robot'

    @property
    def output_dir(self) -> str:
        return self._dir_edit.text().strip()

    @property
    def open_explorer(self) -> bool:
        return self._open_explorer.isChecked()
