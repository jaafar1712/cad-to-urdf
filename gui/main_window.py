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
import shutil
import tempfile


def _safe_filename(name: str) -> str:
    safe = re.sub(r'[<>:"/\\|?*#\s]+', '_', name)
    safe = safe.strip('._') or 'part'
    return safe


# Minimum free disk space required before starting mesh export (bytes)
_MIN_FREE_BYTES = 600 * 1024 * 1024   # 600 MB


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
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, filepath: str):
        super().__init__()
        self.filepath = filepath

    def run(self):
        from utils.session_log import SessionLog
        slog = SessionLog('Analysis')
        slog.set_file(self.filepath)

        try:
            from core.step_reader        import StepReader
            from core.topology_explorer  import TopologyExplorer
            from core.joint_detector     import JointDetector
            from core.inertia_calculator import InertiaCalculator
            from core.assembly_analyzer  import AssemblyAnalyzer
            from core.mesh_exporter      import MeshExporter

            # ── pre-flight: disk space ──────────────────────────────────
            tmp_root = tempfile.gettempdir()
            free     = shutil.disk_usage(tmp_root).free
            free_mb  = free // (1024 * 1024)
            if free < _MIN_FREE_BYTES:
                msg = (
                    f"Only {free_mb} MB free on disk "
                    f"(need >= {_MIN_FREE_BYTES//(1024*1024)} MB).\n\n"
                    f"Temp folder: {tmp_root}\n\n"
                    "Free space then try again.\n"
                    "Tip: File -> Clear Temp Files removes previous session caches."
                )
                slog.step('Disk space check', 'fail', f'{free_mb} MB free')
                slog.error(msg)
                slog.write()
                self.error.emit(msg)
                return
            slog.step('Disk space check', 'ok', f'{free_mb} MB free')

            # ── STEP reader ─────────────────────────────────────────────
            self.progress.emit(5, 'Reading STEP file...')
            reader = StepReader()
            reader.load(self.filepath)
            parts  = reader.get_parts()

            # Deduplicate part names (multiple instances get _1, _2 suffix)
            parts = AssemblyAnalyzer._deduplicate_names(parts)
            slog.step('Read STEP file', 'ok', f'{len(parts)} parts extracted')

            # ── topology ────────────────────────────────────────────────
            # Use placed_shape (world coords) for topology so cylinder axis
            # directions are correctly expressed in the world/parent frame.
            self.progress.emit(25, f'Analyzing topology ({len(parts)} parts)...')
            explorer = TopologyExplorer()
            topos    = [explorer.analyze_shape(p['shape']) for p in parts]
            slog.step('Topology analysis', 'ok', f'{len(parts)} parts analyzed')

            # ── joints ──────────────────────────────────────────────────
            self.progress.emit(45, 'Detecting joints...')
            detector = JointDetector()
            joints   = detector.detect_all_joints(parts, topos)

            # Override joint origins: use placement translations so joint
            # frame = child part's prototype origin in parent-local coords.
            # This fixes the double-transform caused by world-space cylinder
            # midpoints being used as URDF parent-local joint offsets.
            part_world_origin = {}
            for p in parts:
                loc = p.get('location')
                if loc is None or loc.IsIdentity():
                    part_world_origin[p['name']] = (0.0, 0.0, 0.0)
                else:
                    try:
                        t = loc.Transformation().TranslationPart()
                        part_world_origin[p['name']] = (
                            t.X() * 0.001, t.Y() * 0.001, t.Z() * 0.001
                        )
                    except Exception:
                        part_world_origin[p['name']] = (0.0, 0.0, 0.0)

            for j in joints:
                po = part_world_origin.get(j.parent_link, (0.0, 0.0, 0.0))
                co = part_world_origin.get(j.child_link,  (0.0, 0.0, 0.0))
                j.origin_xyz = (
                    co[0] - po[0],
                    co[1] - po[1],
                    co[2] - po[2],
                )

            slog.step('Joint detection', 'ok', f'{len(joints)} joints detected')

            # ── inertia ─────────────────────────────────────────────────
            # Use raw_shape (prototype-local coords) so CoM is expressed in
            # the link's own frame, as the URDF <inertial><origin> requires.
            self.progress.emit(60, 'Calculating inertial properties...')
            calc  = InertiaCalculator()
            links = []
            clamped = 0
            for p in parts:
                raw = p.get('raw_shape') or p['shape']
                inertia = calc.calculate(raw)
                if inertia.get('mass', 1.0) <= 1e-3 + 1e-9:
                    clamped += 1
                    slog.warning(
                        f"Part '{p['name']}' mass clamped to 1 g "
                        "(surface model — no solid volume)"
                    )
                link = {'name': p['name'], 'index': p.get('index', 0)}
                link.update(inertia)
                links.append(link)
            status = 'warn' if clamped else 'ok'
            slog.step('Inertia calculation', status,
                      f'{clamped} part(s) with surface-only geometry' if clamped else '')

            # ── mesh export ─────────────────────────────────────────────
            # Use raw_shape so mesh vertices are in prototype-local (link-local)
            # coords.  Placed_shape has world-space vertices which causes a
            # double-transform when Gazebo/RViz applies the link pose on top.
            self.progress.emit(80, 'Exporting part meshes...')
            exporter  = MeshExporter()
            tmp_dir   = tempfile.mkdtemp(prefix='cad2urdf_')
            vis_dir   = os.path.join(tmp_dir, 'visual')
            col_dir   = os.path.join(tmp_dir, 'collision')
            os.makedirs(vis_dir)
            os.makedirs(col_dir)

            import trimesh
            visual_paths    = []
            collision_paths = []
            failed_exports  = 0
            for p in parts:
                safe      = _safe_filename(p['name'])
                dae       = os.path.join(vis_dir, f"{safe}.dae")
                stl       = os.path.join(col_dir, f"{safe}.stl")
                raw_shape = p.get('raw_shape') or p['shape']
                try:
                    exporter.export_visual_dae(raw_shape, dae)
                    exporter.export_collision_stl(raw_shape, stl)
                except OSError as e:
                    if e.errno == 28 or 'space' in str(e).lower():
                        msg = (
                            f"No space left on device while exporting '{p['name']}'.\n\n"
                            f"Free up disk space and try again.\n"
                            f"Temp dir: {tmp_dir}\n\n"
                            "Tip: File -> Clear Temp Files removes old session caches."
                        )
                        slog.step('Mesh export (DAE/STL)', 'fail',
                                  f'Disk full at part {p["name"]}')
                        slog.error(msg)
                        slog.write()
                        self.error.emit(msg)
                        return
                    failed_exports += 1
                    log.warning(f"Mesh export failed for '{p['name']}': {e}")
                visual_paths.append(dae)
                collision_paths.append(stl)

            export_status = 'warn' if failed_exports else 'ok'
            slog.step('Mesh export (DAE/STL)', export_status,
                      f'{failed_exports} part(s) failed' if failed_exports else
                      f'{len(parts)} files written')

            # ── preview mesh ─────────────────────────────────────────────
            self.progress.emit(92, 'Building 3D preview...')
            preview_assembly = None
            try:
                whole = StepReader.load_whole_shape(self.filepath)
                if whole is not None:
                    prev_stl = os.path.join(tmp_dir, '_preview_.stl')
                    mesh     = exporter._tessellate(whole, 0.05, 0.3)
                    mesh.export(prev_stl, file_type='stl')
                    preview_assembly = trimesh.load(prev_stl)
                    slog.step('Preview mesh', 'ok',
                              f'{len(preview_assembly.faces)} faces')
            except Exception as prev_err:
                log.warning(f"Assembly preview failed: {prev_err}")
                slog.step('Preview mesh', 'warn', str(prev_err)[:120])

            self.progress.emit(100, 'Analysis complete.')
            slog.write()

            self.finished.emit({
                'parts':            parts,
                'links':            links,
                'joints':           joints,
                'topos':            topos,
                'preview_assembly': preview_assembly,
                'visual_paths':     visual_paths,
                'collision_paths':  collision_paths,
                'tmp_dir':          tmp_dir,
            })

        except ValueError as e:
            slog.step('Pipeline', 'fail', 'Validation error')
            slog.error(str(e))
            slog.write()
            self.error.emit(f"Validation Error\n\n{e}")
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            slog.step('Pipeline', 'fail', str(e)[:120])
            slog.error(tb)
            slog.write()
            self.error.emit(f"{e}\n\n{tb}")


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
        from utils.session_log import SessionLog
        slog = SessionLog('Export')

        try:
            from core.urdf_generator      import URDFGenerator
            from core.ros_package_builder import ROSPackageBuilder

            d      = self.data
            joints = d['joints']
            slog.set_file(self.output_dir)

            self.progress.emit(20, 'Building URDF...')
            joint_dicts = []
            for j in joints:
                jd = j.to_dict()
                ov = self.joint_overrides.get(j.name, {})
                jd.update(ov)
                joint_dicts.append(jd)

            gen = URDFGenerator()
            import tempfile as _tf
            tmp = _tf.NamedTemporaryFile(suffix='.urdf', delete=False)
            tmp.close()
            gen.generate(d['links'], joint_dicts, self.package_name, tmp.name)
            slog.step('Generate URDF', 'ok', tmp.name)

            self.progress.emit(60, 'Building ROS 2 package...')
            builder  = ROSPackageBuilder()
            pkg_path = builder.build(
                self.package_name, self.output_dir, tmp.name,
                d['visual_paths'], d['collision_paths'],
            )
            slog.step('Build ROS 2 package', 'ok', pkg_path)

            os.unlink(tmp.name)
            self.progress.emit(100, 'Export complete!')
            slog.write()
            self.finished.emit(pkg_path)

        except ValueError as e:
            slog.step('Export', 'fail', 'Validation error')
            slog.error(str(e))
            slog.write()
            self.error.emit(f"Validation Error\n\n{e}")
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            slog.step('Export', 'fail', str(e)[:120])
            slog.error(tb)
            slog.write()
            self.error.emit(f"{e}\n\n{tb}")


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle('CAD2URDF -- CAD to ROS 2 URDF Converter')
        self.setMinimumSize(1200, 700)
        self._analysis_result = None
        self._thread          = None
        self._session_tmp_dir = None   # cleaned up when user opens a new file
        self._setup_menu()
        self._setup_central()
        self._setup_statusbar()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _setup_menu(self):
        mb = self.menuBar()

        file_menu = mb.addMenu('&File')

        open_act = QAction('&Open CAD File...', self)
        open_act.setShortcut(QKeySequence.Open)
        open_act.triggered.connect(self.open_cad_file)
        file_menu.addAction(open_act)

        file_menu.addSeparator()

        export_act = QAction('&Export ROS 2 Package...', self)
        export_act.setShortcut(QKeySequence('Ctrl+E'))
        export_act.triggered.connect(self.export_package)
        file_menu.addAction(export_act)

        validate_act = QAction('&Validate Package...', self)
        validate_act.setShortcut(QKeySequence('Ctrl+Shift+V'))
        validate_act.triggered.connect(self.validate_package)
        file_menu.addAction(validate_act)

        viewer_act = QAction('Open &Package Viewer...', self)
        viewer_act.setShortcut(QKeySequence('Ctrl+P'))
        viewer_act.setToolTip(
            'Open a ROS 2 package folder to preview the URDF '
            'with 3D meshes, file tree, and structure'
        )
        viewer_act.triggered.connect(self.open_package_viewer)
        file_menu.addAction(viewer_act)

        file_menu.addSeparator()

        clear_act = QAction('&Clear Temp Files', self)
        clear_act.setShortcut(QKeySequence('Ctrl+Shift+C'))
        clear_act.setToolTip(
            'Delete mesh cache from the current session to free disk space'
        )
        clear_act.triggered.connect(self.clear_temp_files)
        file_menu.addAction(clear_act)

        report_act = QAction('Open &Debug Report', self)
        report_act.setShortcut(QKeySequence('Ctrl+Shift+R'))
        report_act.triggered.connect(self.open_debug_report)
        file_menu.addAction(report_act)

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

        self._tree = AssemblyTreeWidget()
        self._tree.setMaximumWidth(250)
        self._tree.part_selected.connect(self._on_part_selected)
        splitter.addWidget(self._tree)

        try:
            from gui.viewer_3d import Viewer3D
            self._viewer = Viewer3D()
        except Exception as e:
            log.warning(f"3D viewer unavailable: {e}")
            self._viewer = QLabel('3D viewer unavailable\n(pyvista not loaded)')
            self._viewer.setAlignment(Qt.AlignCenter)
            self._viewer.setStyleSheet('background: #2d2d2d; color: white;')
        splitter.addWidget(self._viewer)

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
        self._status_label = QLabel('Ready -- open a STEP file to begin.')
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
        # Clean up temp files from the PREVIOUS session before starting a new one.
        # This is the main guard against filling the disk.
        self._cleanup_session_temp()
        self._reset_ui()
        self._run_analysis(path)

    def open_cad_file_path(self, path: str):
        if os.path.isfile(path):
            self._cleanup_session_temp()
            self._reset_ui()
            self._run_analysis(path)

    def export_package(self):
        if not self._analysis_result:
            QMessageBox.warning(self, 'No Data',
                                'Please open and analyze a CAD file first.')
            return

        first_name = (self._analysis_result['parts'][0]['name']
                      if self._analysis_result['parts'] else 'my_robot')
        import re as _re
        _safe = _re.sub(r'[^a-z0-9_]', '_', first_name.lower())
        _safe = _re.sub(r'_+', '_', _safe).strip('_') or 'robot'

        dlg = ExportDialog(default_name=_safe, parent=self)
        if dlg.exec_() != dlg.Accepted:
            return

        self._run_export(
            dlg.package_name, dlg.output_dir,
            self._joint_panel.get_all_joint_overrides(),
            open_when_done=dlg.open_explorer,
        )

    def validate_package(self):
        pkg_dir = QFileDialog.getExistingDirectory(
            self, 'Select ROS 2 Package Directory', '',
            QFileDialog.ShowDirsOnly,
        )
        if not pkg_dir:
            return
        try:
            from utils.urdf_validator import validate_package as _val
            from utils.session_log import SessionLog
            result = _val(pkg_dir)
            slog   = SessionLog('Validation')
            slog.set_file(pkg_dir)
            slog.step('Package validation',
                      'ok' if result['ok'] else 'fail',
                      f"{result['n_pass']} passed, {result['n_warn']} warn, "
                      f"{result['n_fail']} fail")
            if not result['ok']:
                slog.error(result['report'])
            slog.write()
        except Exception as e:
            QMessageBox.critical(self, 'Validator Error', str(e))
            return

        icon  = (QMessageBox.Warning if not result['ok']
                 else QMessageBox.Information)
        title = ('Validation Failed'     if result['n_fail'] > 0 else
                 'Validation Passed'     if result['n_warn'] == 0 else
                 'Passed with Warnings')
        dlg = QMessageBox(icon, title, result['report'], parent=self)
        dlg.setTextFormat(Qt.PlainText)
        dlg.exec_()

    def clear_temp_files(self):
        """File -> Clear Temp Files: delete all cad2urdf_* temp dirs."""
        dirs = []
        tmp_root = tempfile.gettempdir()
        try:
            dirs = [
                os.path.join(tmp_root, d)
                for d in os.listdir(tmp_root)
                if d.startswith('cad2urdf_')
            ]
        except Exception:
            pass

        if self._session_tmp_dir:
            dirs.append(self._session_tmp_dir)

        freed = 0
        for d in set(dirs):
            if os.path.isdir(d):
                try:
                    size = sum(
                        f.stat().st_size
                        for f in os.scandir(d)
                        if f.is_file()
                    )
                    shutil.rmtree(d, ignore_errors=True)
                    freed += size
                except Exception:
                    pass
        self._session_tmp_dir = None

        free_now = shutil.disk_usage(tmp_root).free // (1024 * 1024)
        QMessageBox.information(
            self, 'Temp Files Cleared',
            f'Freed {freed // (1024*1024)} MB.\n'
            f'Disk free: {free_now} MB.',
        )
        self._set_status(None, f'Temp files cleared — {free_now} MB free.')

    def open_package_viewer(self, package_dir: str = None):
        """File -> Open Package Viewer — opens the URDF / ROS 2 package viewer."""
        from gui.package_viewer import PackageViewerWindow
        if not package_dir:
            package_dir = QFileDialog.getExistingDirectory(
                self, 'Select ROS 2 Package Directory', '',
                QFileDialog.ShowDirsOnly,
            ) or None
        viewer = PackageViewerWindow(package_dir=package_dir, parent=self)
        viewer.show()
        # keep a reference so it isn't garbage-collected
        if not hasattr(self, '_package_viewers'):
            self._package_viewers = []
        self._package_viewers.append(viewer)

    def open_debug_report(self):
        """File -> Open Debug Report: open the session markdown in the default editor."""
        from utils.session_log import REPORT_PATH
        if not os.path.isfile(REPORT_PATH):
            QMessageBox.information(
                self, 'No Report Yet',
                f'The debug report will be created after the first pipeline run.\n'
                f'It will be saved to:\n{REPORT_PATH}',
            )
            return
        import subprocess
        subprocess.Popen(['notepad.exe', REPORT_PATH])

    # ------------------------------------------------------------------
    # Background pipeline
    # ------------------------------------------------------------------

    def _run_analysis(self, filepath: str):
        self._set_status(0, f'Loading {os.path.basename(filepath)}...')
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

    def _run_export(self, pkg_name, out_dir, joint_overrides, open_when_done):
        self._set_status(0, 'Exporting...')
        self._progress.setVisible(True)

        worker = ExportWorker(self._analysis_result, pkg_name, out_dir,
                              joint_overrides)
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
        self._session_tmp_dir = result.get('tmp_dir')   # remember for cleanup
        self._progress.setVisible(False)
        self._set_status(
            100,
            f"Analysis complete -- "
            f"{len(result['parts'])} links, "
            f"{len(result['joints'])} joints detected."
        )
        self._tree.populate(result['parts'])
        self._link_panel.populate(result['links'])
        self._joint_panel.populate(result['joints'])

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
            f'Build with:\n  colcon build --packages-select {os.path.basename(pkg_path)}'
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
        self._set_status(None, f'Selected: {name}')

    def _on_material_changed(self, link_name: str, material: str):
        log.debug(f"Material changed: {link_name} -> {material}")

    def _on_joint_changed(self, joint_name: str, data: dict):
        log.debug(f"Joint changed: {joint_name} -> {data}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _cleanup_session_temp(self):
        """Delete temp directory from the previous analysis session."""
        if self._session_tmp_dir and os.path.isdir(self._session_tmp_dir):
            shutil.rmtree(self._session_tmp_dir, ignore_errors=True)
            log.info(f"Cleaned previous session temp: {self._session_tmp_dir}")
        self._session_tmp_dir = None

    def _reset_ui(self):
        """Clear all panels and viewer for a new file."""
        self._analysis_result = None
        try:
            self._tree.clear()
        except Exception:
            pass
        try:
            self._link_panel.clear()
        except Exception:
            pass
        try:
            self._joint_panel.clear()
        except Exception:
            pass
        try:
            if hasattr(self._viewer, '_plotter') and self._viewer._plotter:
                self._viewer._plotter.clear()
        except Exception:
            pass

    def _set_status(self, percent, message: str):
        self._status_label.setText(message)
        if percent is not None and percent >= 0:
            self._progress.setValue(percent)

    def _show_about(self):
        QMessageBox.about(
            self, 'About CAD2URDF',
            '<b>CAD2URDF</b> v0.1<br><br>'
            'Converts STEP CAD assemblies to ROS 2 URDF packages.<br><br>'
            'Built with pythonocc, PyVista, and PyQt5.',
        )

    def closeEvent(self, event):
        self._cleanup_session_temp()
        try:
            if hasattr(self._viewer, 'close'):
                self._viewer.close()
        except Exception:
            pass
        event.accept()
