"""
CAD2URDF — Entry point.
Launch: python main.py
"""
import sys
import os

# Ensure project root is on path regardless of cwd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from gui.main_window import MainWindow
from utils.logger import get_logger

log = get_logger(__name__)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('CAD2URDF')
    app.setOrganizationName('CAD2URDF')

    # Crisp font
    font = QFont('Segoe UI', 9)
    app.setFont(font)

    # High-DPI support
    app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    window = MainWindow()
    window.show()

    log.info('CAD2URDF started.')

    # If a file was passed as CLI argument, open it immediately
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        window.open_cad_file_path(sys.argv[1])

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
