"""
Generates GUI screenshots for the README using Qt's offscreen platform.
Saves PNG files to docs/screenshots/.
"""
import sys, os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QPixmap

OUT = "docs/screenshots"
os.makedirs(OUT, exist_ok=True)

app = QApplication(sys.argv)
app.setApplicationName("CAD2URDF")
from PyQt5.QtGui import QFont
app.setFont(QFont("Segoe UI", 9))

from gui.main_window import MainWindow
win = MainWindow()
win.resize(1280, 760)
win.show()

def grab(widget, path, w=None, h=None):
    if w:
        widget.resize(w, h)
    pix = widget.grab()
    pix.save(path)
    print(f"  Saved: {path}  ({pix.width()}x{pix.height()})")

# ----- Screenshot 1: main window (empty state) -----
def shot1():
    grab(win, f"{OUT}/01_main_window_empty.png", 1280, 760)

    # ----- Screenshot 2: simulate analysis result -----
    # Inject fake analysis data so the panels populate
    from core.step_reader import StepReader
    from core.topology_explorer import TopologyExplorer
    from core.joint_detector import JointDetector
    from core.inertia_calculator import InertiaCalculator

    reader = StepReader()
    reader.load("test_arm.step")
    parts = reader.get_parts()
    topos = [TopologyExplorer().analyze_shape(p["shape"]) for p in parts]
    joints = JointDetector().detect_all_joints(parts, topos)
    calc = InertiaCalculator()
    links = []
    for p in parts:
        inertia = calc.calculate(p["shape"])
        link = {"name": p["name"]}
        link.update(inertia)
        links.append(link)

    win._tree.populate(parts)
    win._link_panel.populate(links)
    win._joint_panel.populate(joints)
    win._analysis_result = {
        "parts": parts, "links": links, "joints": joints,
        "topos": topos, "preview_meshes": [], "visual_paths": [],
        "collision_paths": [], "tmp_dir": "",
    }
    win._status_label.setText(
        "Analysis complete — 2 links, 1 joints detected."
    )
    grab(win, f"{OUT}/02_main_window_loaded.png", 1280, 760)

    # ----- Screenshot 3: joints tab -----
    # Switch to Joints tab (index 1)
    for widget in win.findChildren(__import__("PyQt5.QtWidgets", fromlist=["QTabWidget"]).QTabWidget):
        widget.setCurrentIndex(1)
    grab(win, f"{OUT}/03_joints_panel.png", 1280, 760)

    # ----- Screenshot 4: export dialog -----
    from gui.export_dialog import ExportDialog
    dlg = ExportDialog("test_arm", parent=win)
    dlg.show()
    grab(dlg, f"{OUT}/04_export_dialog.png", 500, 200)
    dlg.close()

    print("\nAll screenshots saved.")
    app.quit()

QTimer.singleShot(200, shot1)
sys.exit(app.exec_())
