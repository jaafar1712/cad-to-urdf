"""
Main application window for CAD2URDF.
Layout:
  Left:   Assembly tree widget
  Center: PyVista 3D viewer
  Right:  Tabbed panel (Links / Joints)
  Bottom: Status bar with progress bar
"""
import os
import re
import tempfile


def _safe_filename(name: str) -> str:
    """Strip/replace characters that are illegal in Windows filenames."""
    safe = re.sub(r'[<>:"/\\|?*#\s]+', '_', name)
    safe = safe.strip('._') or 'part'
    return safe

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QTabWidget, QStatusBar, QProgressBar, QLabel, QMenuBar,
    QAction, QMessageBox, QFileDialog, QApplication,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt5.QtGui import QKeySequence

from gui.assembly_tree_widget import AssemblyTreeWidget
from gui.joint_panel import JointPanel
from gui.link_panel import LinkPanel
from gui.export_dialog import ExportDialog

from utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

class AnalysisWorker(QObject):
    """Runs the CAD analysis pipeline in a background thread."""
    progress  = pyqtSignal(int, str)     # (percent, message)
    finished  = pyqtSignal(dict)          # result dict
    error     = pyqtSignal(str)

    def __init__(self, filepath: str):
        super().__init__()
        self.filepath = filepath

    def run(self):
        try:
            from core.step_reader       import StepReader
            from core.topology_explorer import TopologyExplorer
            from core.joint_detector    import JointDetector
            from core.inertia_calculator import InertiaCalculator
            from core.assembly_analyzer  import AssemblyAnalyzer
            from core.mesh_exporter      import MeshExporter

            self.progress.emit(5, 'Reading STEP file…')
            reader = StepReader()
            reader.load(self.filepath)
            parts = reader.get_parts()

            self.progress.emit(25, f'Analyzing topology ({len(parts)} parts)…')
            explorer = TopologyExplorer()
            topos = [explorer.analyze_shape(p['shape']) for p in parts]

            self.progress.emit(45, 'Detecting joints…')
            detector = JointDetector()
            joints = detector.detect_all_joints(parts, topos)

            self.progress.emit(60, 'Calculating inertial properties…')
            calc = InertiaCalculator()
            links = []
            for p in parts:
                inertia = calc.calculate(p['shape'])
                link = {'name': p['name']}
                link.update(inertia)
                links.append(link)

            self.progress.emit(80, 'Exporting part meshes…')
            exporter = MeshExporter()
            tmp_dir = tempfile.mkdtemp(prefix='cad2urdf_')
            vis_dir  = os.path.join(tmp_dir, 'visual')
            col_dir  = os.path.join(tmp_dir, 'collision')
            os.makedirs(vis_dir);  os.makedirs(col_dir)

            import trimesh
            visual_paths    = []
            collision_paths = []
            for p in parts:
                safe = _safe_filename(p['name'])
                dae = os.path.join(vis_dir,  f"{safe}.dae")
                stl = os.path.join(col_dir,  f"{safe}.stl")
                exporter.export_visual_dae(p['shape'], dae)
                exporter.export_collision_stl(p['shape'], stl)
                visual_paths.append(dae)
                collision_paths.append(stl)

            # Build a single whole-assembly preview mesh via the simple STEP
            # reader — bypasses XDE location-composition and is guaranteed
            # to show all parts in their correct assembled positions.
            self.progress.emit(92, 'Building 3D preview…')
            preview_assembly = None
            try:
                whole = StepReader.load_whole_shape(self.filepath)
                if whole is not None:
                    prev_stl = os.path.join(tmp_dir, '_preview_.stl')
                    mesh = exporter._tessellate(whole, 0.05, 0.3)
                    mesh.export(prev_stl, file_type='stl')
                    preview_assembly = trimesh.load(prev_stl)
            except Exception as prev_err:
                log.warning(f"Assembly preview failed: {prev_err}")

            self.progress.emit(100, 'Analysis complete.')
            self.finished.emit({
                'parts':             parts,
                'links':             links,
                'joints':            joints,
                'topos':             topos,
                'preview_assembly':  preview_assembly,
                'visual_paths':      visual_paths,
                'collision_paths':   collision_paths,
                'tmp_dir':           tmp_dir,
            })

        except ValueError as e:
            self.error.emit(f"Validation Error\n\n{e}")
        except Exception as e:
            import traceback
            self.error.emit(f"{e}\n\n{traceback.format_exc()}")


class ExportWorker(QObject):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, data: dict, package_name: str, output_dir: str,
                 joint_overrides: dict):
        super().__init__()
        self.data            = data
        self.package_name    = package_name
        self.output_dir      = output_dir
        self.joint_overrides = joint_overrides

    def run(self):
        try:
            from core.urdf_generator     import URDFGenerator
            from core.ros_package_builder import ROSPackageBuilder
            import tempfile

            d = self.data
            joints = d['joints']

            self.progress.emit(20, 'Building URDF…')

            # Apply GUI overrides to joint data
            joint_dicts = []
            for j in joints:
                jd = j.to_dict()
                ov = self.joint_overrides.get(j.name, {})
                jd.update(ov)
                joint_dicts.append(jd)

            gen = URDFGenerator()
            tmp = tempfile.NamedTemporaryFile(suffix='.urdf', delete=False)
            tmp.close()
            gen.generate(d['links'], joint_dicts,
                         self.package_name, tmp.name)

            self.progress.emit(60, 'Building ROS 2 package…')
            builder = ROSPackageBuilder()
            pkg_path = builder.build(
                self.package_name,
                self.output_dir,
                tmp.name,
                d['visual_paths'],
                d['collision_paths'],
            )

            os.unlink(tmp.name)
            self.progress.emit(100, 'Export complete!')
            self.finished.emit(pkg_path)

        except ValueError as e:
            self.error.emit(f"Validation Error\n\n{e}")
        except Exception as e:
            import traceback
            self.error.emit(f"{e}\n\n{traceback.format_exc()}")


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle('CAD2URDF — CAD to ROS 2 URDF Converter')
        self.setMinimumSize(1200, 700)
        self._analysis_result = None
        self._thread = None
        self._setup_menu()
        self._setup_central()
        self._setup_statusbar()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _setup_menu(self):
        mb = self.menuBar()

        file_menu = mb.addMenu('&File')
        open_act = QAction('&Open CAD File…', self)
        open_act.setShortcut(QKeySequence.Open)
        open_act.triggered.connect(self.open_cad_file)
        file_menu.addAction(open_act)

        file_menu.addSeparator()

        export_act = QAction('&Export ROS 2 Package…', self)
        export_act.setShortcut(QKeySequence('Ctrl+E'))
        export_act.triggered.connect(self.export_package)
        file_menu.addAction(export_act)

        file_menu.addSeparator()
        quit_act = QAction('&Quit', self)
        quit_act.setShortcut(QKeySequence.Quit)
        quit_act.triggered.connect(QApplication.quit)
        file_menu.addAction(quit_act)

        help_menu = mb.addMenu('&Help')
        about_act = QAction('&About', self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

    def _setup_central(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # --- Left: Assembly tree ---
        self._tree = AssemblyTreeWidget()
        self._tree.setMaximumWidth(250)
        self._tree.part_selected.connect(self._on_part_selected)
        splitter.addWidget(self._tree)

        # --- Center: 3D viewer ---
        try:
            from gui.viewer_3d import Viewer3D
            self._viewer = Viewer3D()
        except Exception as e:
            log.warning(f"3D viewer unavailable: {e}")
            self._viewer = QLabel('3D viewer unavailable\n(pyvista not loaded)')
            self._viewer.setAlignment(Qt.AlignCenter)
            self._viewer.setStyleSheet('background: #2d2d2d; color: white;')
        splitter.addWidget(self._viewer)

        # --- Right: tabbed panels ---
        tabs = QTabWidget()
        tabs.setMaximumWidth(340)

        self._link_panel = LinkPanel()
        self._link_panel.material_changed.connect(self._on_material_changed)
        tabs.addTab(self._link_panel, 'Links')

        self._joint_panel = JointPanel()
        self._joint_panel.joint_changed.connect(self._on_joint_changed)
        tabs.addTab(self._joint_panel, 'Joints')

        splitter.addWidget(tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 1)

    def _setup_statusbar(self):
        sb = self.statusBar()
        self._status_label = QLabel('Ready — open a STEP file to begin.')
        sb.addWidget(self._status_label, 1)
        self._progress = QProgressBar()
        self._progress.setMaximumWidth(200)
        self._progress.setVisible(False)
        sb.addPermanentWidget(self._progress)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def open_cad_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Open CAD File', '',
            'STEP Files (*.step *.stp);;IGES Files (*.iges *.igs);;All Files (*)',
        )
        if not path:
            return
        self._run_analysis(path)

    def open_cad_file_path(self, path: str):
        """Open a specific file path directly (e.g. from CLI argument)."""
        if os.path.isfile(path):
            self._run_analysis(path)

    def export_package(self):
        if not self._analysis_result:
            QMessageBox.warning(self, 'No Data',
                                'Please open and analyze a CAD file first.')
            return

        first_name = self._analysis_result['parts'][0]['name'] \
            if self._analysis_result['parts'] else 'my_robot'

        import re as _re
        _safe = _re.sub(r'[^a-z0-9_]', '_', first_name.lower())
        _safe = _re.sub(r'_+', '_', _safe).strip('_') or 'robot'

        dlg = ExportDialog(
            default_name=_safe,
            parent=self,
        )
        if dlg.exec_() != dlg.Accepted:
            return

        joint_overrides = self._joint_panel.get_all_joint_overrides()

        self._run_export(
            dlg.package_name,
            dlg.output_dir,
            joint_overrides,
            open_when_done=dlg.open_explorer,
        )

    # ------------------------------------------------------------------
    # Background pipeline
    # ------------------------------------------------------------------

    def _run_analysis(self, filepath: str):
        self._set_status(0, f'Loading {os.path.basename(filepath)}…')
        self._progress.setVisible(True)

        worker = AnalysisWorker(filepath)
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._set_status)
        worker.finished.connect(self._on_analysis_done)
        worker.error.connect(self._on_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        self._worker = worker
        thread.start()

    def _run_export(self, pkg_name: str, out_dir: str,
                    joint_overrides: dict, open_when_done: bool):
        self._set_status(0, 'Exporting…')
        self._progress.setVisible(True)

        worker = ExportWorker(
            self._analysis_result, pkg_name, out_dir, joint_overrides
        )
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._set_status)
        worker.finished.connect(
            lambda path: self._on_export_done(path, open_when_done)
        )
        worker.error.connect(self._on_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        self._export_worker = worker
        self._export_thread = thread
        thread.start()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_analysis_done(self, result: dict):
        self._analysis_result = result
        self._progress.setVisible(False)
        self._set_status(100, f"Analysis complete — "
                              f"{len(result['parts'])} links, "
                              f"{len(result['joints'])} joints detected.")

        self._tree.populate(result['parts'])
        self._link_panel.populate(result['links'])
        self._joint_panel.populate(result['joints'])

        # Update 3D viewer with single whole-assembly mesh
        try:
            asm = result.get('preview_assembly')
            if asm is not None and hasattr(self._viewer, 'show_assembly'):
                self._viewer.show_assembly(asm, result['joints'])
        except Exception as e:
            log.warning(f"Viewer update failed: {e}")

    def _on_export_done(self, pkg_path: str, open_folder: bool):
        self._progress.setVisible(False)
        self._set_status(100, f'Package exported: {pkg_path}')
        QMessageBox.information(
            self, 'Export Complete',
            f'ROS 2 package created:\n{pkg_path}\n\n'
            f'Build it with:\n  colcon build --packages-select {os.path.basename(pkg_path)}'
        )
        if open_folder:
            import subprocess
            subprocess.Popen(['explorer', pkg_path])

    def _on_error(self, msg: str):
        self._progress.setVisible(False)
        self._set_status(-1, 'Error during processing.')
        QMessageBox.critical(self, 'Error', msg[:2000])
        log.error(msg)

    def _on_part_selected(self, name: str):
        if hasattr(self._viewer, 'highlight_joint'):
            pass
        self._set_status(None, f'Selected: {name}')

    def _on_material_changed(self, link_name: str, material: str):
        log.debug(f"Material changed: {link_name} → {material}")

    def _on_joint_changed(self, joint_name: str, data: dict):
        log.debug(f"Joint changed: {joint_name} → {data}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_status(self, percent, message: str):
        self._status_label.setText(message)
        if percent is not None and percent >= 0:
            self._progress.setValue(percent)

    def _show_about(self):
        QMessageBox.about(
            self, 'About CAD2URDF',
            '<b>CAD2URDF</b> v0.1<br><br>'
            'Converts STEP CAD assemblies to simulation-ready ROS 2 URDF packages.<br><br>'
            'Built with pythonocc, PyVista, and PyQt5.',
        )

    def closeEvent(self, event):
        try:
            if hasattr(self._viewer, 'close'):
                self._viewer.close()
        except Exception:
            pass
        event.accept()
