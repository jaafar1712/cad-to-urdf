"""
Standalone URDF / ROS 2 package viewer.

Two tabs:
  1. Package View  — open a folder, see file tree + 3D preview + URDF structure
  2. URDF Text     — paste raw URDF, get structure + box-based 3D preview

3D view uses PyVista (BackgroundPlotter) — same engine as the main CAD viewer.
Meshes are loaded with trimesh (DAE / STL).
"""
import os
import traceback

import numpy as np
import pyvista as pv
from pyvistaqt import BackgroundPlotter

import trimesh

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QTabWidget, QTabBar, QLabel, QPushButton, QFileDialog, QPlainTextEdit,
    QTreeWidget, QTreeWidgetItem, QStatusBar, QFrame, QSizePolicy,
    QProgressBar, QMessageBox,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt5.QtGui import QColor, QFont

from utils.urdf_loader import (
    parse_urdf, resolve_mesh_path, compute_link_transforms, validate_package
)
from utils.logger import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Colour palette — one colour per link (cycles)
# ---------------------------------------------------------------------------
_LINK_COLOURS = [
    '#5b8cca',  # blue
    '#e07b39',  # orange
    '#5cb85c',  # green
    '#c05454',  # red
    '#8e5cb8',  # purple
    '#4ab8b8',  # teal
    '#c8b858',  # yellow
    '#b05c8e',  # pink
]


# ---------------------------------------------------------------------------
# Background loader
# ---------------------------------------------------------------------------

class _MeshLoader(QObject):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)   # {link_name: trimesh or None}
    error    = pyqtSignal(str)

    def __init__(self, parsed: dict, package_dir: str):
        super().__init__()
        self.parsed      = parsed
        self.package_dir = package_dir

    def run(self):
        result = {}
        links  = self.parsed['links']
        total  = len(links)
        for i, lk in enumerate(links):
            pct = int(i / max(total, 1) * 100)
            self.progress.emit(pct, f"Loading mesh for {lk['name']}…")
            mesh = _load_link_mesh(lk, self.package_dir)
            result[lk['name']] = mesh
        self.progress.emit(100, 'Meshes loaded.')
        self.finished.emit(result)


def _load_link_mesh(link_data: dict, package_dir: str):
    """Try visual mesh, then collision; return trimesh.Trimesh or None."""
    for uri_key, scale_key in (
        ('vis_mesh_uri', 'vis_scale'),
        ('col_mesh_uri', 'col_scale'),
    ):
        uri = link_data.get(uri_key)
        if not uri:
            continue
        path = resolve_mesh_path(uri, package_dir)
        if not path or not os.path.isfile(path):
            continue
        try:
            scale = link_data.get(scale_key, (1.0, 1.0, 1.0))
            loaded = trimesh.load(path, force='mesh', process=False)
            if not isinstance(loaded, trimesh.Trimesh):
                # Scene → merge
                if hasattr(loaded, 'dump'):
                    parts = loaded.dump()
                    if parts:
                        loaded = trimesh.util.concatenate(parts)
            if isinstance(loaded, trimesh.Trimesh) and len(loaded.vertices) > 0:
                if any(abs(s - 1.0) > 1e-6 for s in scale):
                    loaded.apply_scale(scale)
                return loaded
        except Exception as e:
            log.warning(f"Could not load mesh '{uri}': {e}")
    return None


# ---------------------------------------------------------------------------
# 3D Renderer helper
# ---------------------------------------------------------------------------

class _URDFRenderer:
    """Renders a parsed URDF onto a BackgroundPlotter."""

    def __init__(self, plotter: BackgroundPlotter):
        self._pl = plotter

    # Virtual-only links — no geometry, skip placeholder box
    _SKIP_LINKS = {'world', 'base_link_inertia'}

    def render(self, parsed: dict, meshes: dict,
               transforms: dict, q: dict = None):
        """
        parsed:     parse_urdf() result
        meshes:     {link_name: trimesh.Trimesh or None}
        transforms: compute_link_transforms() result
        q:          joint angles dict (default 0)
        """
        if q:
            transforms = compute_link_transforms(parsed, q)

        self._pl.clear()
        self._pl.set_background('#1a1a2e')

        n_rendered = 0
        for idx, lk in enumerate(parsed['links']):
            name   = lk['name']
            colour = _LINK_COLOURS[idx % len(_LINK_COLOURS)]

            # Skip virtual reference frames — they have no geometry
            if name in self._SKIP_LINKS:
                continue

            T    = transforms.get(name, np.eye(4))
            mesh = meshes.get(name)

            try:
                if mesh is not None and isinstance(mesh, trimesh.Trimesh) \
                        and len(mesh.vertices) > 0:
                    pv_mesh = self._tm_to_pv(mesh, T)
                    if pv_mesh is not None:
                        self._pl.add_mesh(
                            pv_mesh, color=colour, opacity=1.0,
                            smooth_shading=True, show_edges=False,
                        )
                        n_rendered += 1
                else:
                    # Fallback: small box at the link origin.
                    # Build the box already at the world position so we never
                    # call pv.PolyData.transform() — that API is deprecated in
                    # recent PyVista and raises a Warning caught as Exception.
                    c    = T[:3, 3]
                    half = 0.025
                    box  = pv.Box(bounds=(
                        float(c[0]-half), float(c[0]+half),
                        float(c[1]-half), float(c[1]+half),
                        float(c[2]-half), float(c[2]+half),
                    ))
                    self._pl.add_mesh(box, color=colour, opacity=0.55)
                    n_rendered += 1
            except Exception as e:
                log.warning(f"Could not render link '{name}': {e}")

        # Joint-axis arrows
        for j in parsed['joints']:
            if j['type'] == 'fixed':
                continue
            try:
                parent_T = transforms.get(j['parent'], np.eye(4))
                joint_T  = parent_T @ self._joint_local_T(j)
                origin   = joint_T[:3, 3]
                axis_dir = joint_T[:3, :3] @ np.array(j['axis'])
                # auto-scale arrow to 5% of scene size
                try:
                    b    = self._pl.bounds
                    span = max(b[1]-b[0], b[3]-b[2], b[5]-b[4], 0.05)
                    scale = span * 0.12
                except Exception:
                    scale = 0.05
                arrow = pv.Arrow(
                    start=tuple(origin.tolist()),
                    direction=tuple(axis_dir.tolist()),
                    scale=scale, tip_length=0.25,
                )
                colour_map = {
                    'revolute':   '#ff6b6b',
                    'prismatic':  '#4ecdc4',
                    'continuous': '#ffe66d',
                }
                self._pl.add_mesh(
                    arrow,
                    color=colour_map.get(j['type'], '#aaaaaa'),
                    lighting=False,
                )
            except Exception as e:
                log.warning(f"Could not draw joint arrow '{j['name']}': {e}")

        # Ground grid
        try:
            grid = pv.Plane(center=(0, 0, 0), direction=(0, 0, 1),
                            i_size=2, j_size=2)
            self._pl.add_mesh(grid, color='#2a2a3a', opacity=0.4)
        except Exception:
            pass

        self._pl.reset_camera()
        try:
            b    = self._pl.bounds
            cx   = (b[0]+b[1])/2; cy = (b[2]+b[3])/2; cz = (b[4]+b[5])/2
            span = max(b[1]-b[0], b[3]-b[2], b[5]-b[4], 0.1)
            d    = span * 2.2
            self._pl.camera_position = [
                (cx+d, cy+d*0.5, cz+d*0.9),
                (cx, cy, cz),
                (0, 0, 1),
            ]
        except Exception:
            pass

        return n_rendered

    @staticmethod
    def _joint_local_T(j: dict) -> np.ndarray:
        from utils.urdf_loader import _xform
        return _xform(j['origin_xyz'], j['origin_rpy'])

    @staticmethod
    def _tm_to_pv(mesh: trimesh.Trimesh, T: np.ndarray):
        try:
            v = np.array(mesh.vertices, dtype=float)
            f = np.array(mesh.faces,    dtype=np.int32)
            R  = T[:3, :3]
            tr = T[:3, 3]
            v = (R @ v.T).T + tr
            n = len(f)
            pv_faces = np.hstack([
                np.full((n, 1), 3, dtype=np.int32), f
            ]).ravel()
            return pv.PolyData(v, pv_faces)
        except Exception as e:
            log.warning(f"Mesh→PyVista failed: {e}")
            return None


# ---------------------------------------------------------------------------
# Package Viewer Window
# ---------------------------------------------------------------------------

class PackageViewerWindow(QMainWindow):
    """
    Open via:  PackageViewerWindow(package_dir="path/to/pkg").show()
    Or standalone with no arguments (user opens folder from File menu).
    """

    def __init__(self, package_dir: str = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('URDF Package Viewer')
        self.setMinimumSize(1280, 750)

        self._package_dir = None
        self._parsed      = None
        self._meshes      = {}
        self._transforms  = {}
        self._plotter     = None
        self._renderer    = None
        self._thread      = None

        self._setup_menu()
        self._setup_central()
        self._setup_statusbar()

        if package_dir and os.path.isdir(package_dir):
            self.load_package(package_dir)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_menu(self):
        mb = self.menuBar()
        file_menu = mb.addMenu('&File')

        open_pkg = file_menu.addAction('&Open Package Folder…')
        open_pkg.setShortcut('Ctrl+O')
        open_pkg.triggered.connect(self._browse_package)

        open_urdf = file_menu.addAction('Open &URDF File…')
        open_urdf.setShortcut('Ctrl+U')
        open_urdf.triggered.connect(self._browse_urdf)

        file_menu.addSeparator()
        file_menu.addAction('&Close', self.close, 'Ctrl+W')

    def _setup_central(self):
        self._tabs = QTabWidget()
        self.setCentralWidget(self._tabs)

        # ----- Tab 1: Package viewer -----
        pkg_widget = QWidget()
        pkg_layout = QVBoxLayout(pkg_widget)
        pkg_layout.setContentsMargins(4, 4, 4, 4)

        # Top toolbar
        toolbar = QHBoxLayout()
        self._pkg_path_label = QLabel('No package loaded')
        self._pkg_path_label.setStyleSheet('color: #aaa; font-style: italic;')
        open_btn = QPushButton('Open Package…')
        open_btn.clicked.connect(self._browse_package)
        reload_btn = QPushButton('Reload')
        reload_btn.clicked.connect(self._reload)
        toolbar.addWidget(self._pkg_path_label, 1)
        toolbar.addWidget(open_btn)
        toolbar.addWidget(reload_btn)
        pkg_layout.addLayout(toolbar)

        # Main split: file-tree | 3d-view | urdf-structure
        splitter = QSplitter(Qt.Horizontal)

        # Left: file tree
        self._file_tree = QTreeWidget()
        self._file_tree.setHeaderLabel('Package Files')
        self._file_tree.setMaximumWidth(220)
        self._file_tree.itemDoubleClicked.connect(self._on_file_double_click)
        splitter.addWidget(self._file_tree)

        # Center: 3D view
        view_container = QWidget()
        view_layout    = QVBoxLayout(view_container)
        view_layout.setContentsMargins(0, 0, 0, 0)
        self._plotter = BackgroundPlotter(show=False)
        self._plotter.set_background('#1a1a2e')
        view_layout.addWidget(self._plotter.app_window)
        self._renderer = _URDFRenderer(self._plotter)
        splitter.addWidget(view_container)

        # Right: URDF structure tree
        self._urdf_tree = QTreeWidget()
        self._urdf_tree.setHeaderLabels(['Element', 'Value'])
        self._urdf_tree.setMaximumWidth(280)
        splitter.addWidget(self._urdf_tree)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 1)
        pkg_layout.addWidget(splitter)

        self._tabs.addTab(pkg_widget, 'Package View')

        # ----- Tab 2: URDF text paste -----
        text_widget = QWidget()
        text_layout = QVBoxLayout(text_widget)
        text_layout.setContentsMargins(4, 4, 4, 4)

        text_top = QHBoxLayout()
        text_top.addWidget(QLabel('Paste URDF XML:'))
        parse_btn = QPushButton('Parse & Preview')
        parse_btn.clicked.connect(self._parse_text_urdf)
        clear_btn = QPushButton('Clear')
        clear_btn.clicked.connect(lambda: self._urdf_text_edit.clear())
        text_top.addStretch()
        text_top.addWidget(parse_btn)
        text_top.addWidget(clear_btn)
        text_layout.addLayout(text_top)

        text_splitter = QSplitter(Qt.Horizontal)

        self._urdf_text_edit = QPlainTextEdit()
        self._urdf_text_edit.setPlaceholderText(
            '<?xml version="1.0"?>\n<robot name="my_robot">\n  ...\n</robot>'
        )
        font = QFont('Consolas', 10)
        font.setStyleHint(QFont.Monospace)
        self._urdf_text_edit.setFont(font)
        text_splitter.addWidget(self._urdf_text_edit)

        self._text_tree = QTreeWidget()
        self._text_tree.setHeaderLabels(['Element', 'Value'])
        text_splitter.addWidget(self._text_tree)

        text_splitter.setStretchFactor(0, 3)
        text_splitter.setStretchFactor(1, 1)
        text_layout.addWidget(text_splitter)

        self._tabs.addTab(text_widget, 'URDF Text')

    def _setup_statusbar(self):
        sb = self.statusBar()
        self._status_label = QLabel('Ready — open a package folder or paste URDF text.')
        sb.addWidget(self._status_label, 1)
        self._progress = QProgressBar()
        self._progress.setMaximumWidth(200)
        self._progress.setVisible(False)
        sb.addPermanentWidget(self._progress)

    # ------------------------------------------------------------------
    # Load a package folder
    # ------------------------------------------------------------------

    def _browse_package(self):
        d = QFileDialog.getExistingDirectory(
            self, 'Select ROS 2 Package Directory', '',
            QFileDialog.ShowDirsOnly,
        )
        if d:
            self.load_package(d)

    def _browse_urdf(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Open URDF File', '',
            'URDF Files (*.urdf *.urdf.xacro);;All Files (*)',
        )
        if path:
            # Treat parent directory as package dir
            self.load_package(os.path.dirname(path), urdf_override=path)

    def _reload(self):
        if self._package_dir:
            self.load_package(self._package_dir)

    def load_package(self, package_dir: str, urdf_override: str = None):
        """Main entry point: load a ROS 2 package and display it."""
        self._package_dir = package_dir
        self._tabs.setCurrentIndex(0)

        # Find URDF file
        urdf_path = urdf_override or self._find_urdf(package_dir)
        if not urdf_path:
            self._set_status('No URDF file found in this package.')
            QMessageBox.warning(self, 'No URDF',
                                f'No .urdf file found in:\n{package_dir}')
            return

        # Parse
        try:
            self._parsed = parse_urdf(urdf_path)
        except Exception as e:
            self._set_status(f'URDF parse error: {e}')
            QMessageBox.critical(self, 'Parse Error', str(e))
            return

        pkg_name = os.path.basename(package_dir)
        self._pkg_path_label.setText(f'{pkg_name}  —  {package_dir}')
        self.setWindowTitle(f'URDF Package Viewer — {pkg_name}')

        # Fill file tree
        self._populate_file_tree(package_dir)

        # Fill URDF structure
        self._populate_urdf_tree(self._urdf_tree, self._parsed)

        # Validate
        val = validate_package(package_dir, self._parsed)
        self._show_validation(val)

        # Load meshes in background
        self._load_meshes_async(package_dir)

    def _find_urdf(self, package_dir: str) -> str:
        """Search common locations for a URDF file."""
        candidates = []
        for subdir in ('urdf', 'description', ''):
            d = os.path.join(package_dir, subdir) if subdir else package_dir
            if os.path.isdir(d):
                for f in os.listdir(d):
                    if f.endswith('.urdf'):
                        candidates.append(os.path.join(d, f))
        return candidates[0] if candidates else None

    # ------------------------------------------------------------------
    # File tree
    # ------------------------------------------------------------------

    def _populate_file_tree(self, package_dir: str):
        self._file_tree.clear()
        root_item = QTreeWidgetItem([os.path.basename(package_dir)])
        root_item.setData(0, Qt.UserRole, package_dir)
        self._file_tree.addTopLevelItem(root_item)
        self._add_dir_to_tree(root_item, package_dir, depth=0)
        root_item.setExpanded(True)

    def _add_dir_to_tree(self, parent_item: QTreeWidgetItem,
                          dir_path: str, depth: int):
        if depth > 4:
            return
        try:
            entries = sorted(os.listdir(dir_path))
        except PermissionError:
            return
        # Dirs first, then files
        dirs  = [e for e in entries if os.path.isdir(os.path.join(dir_path, e))]
        files = [e for e in entries if os.path.isfile(os.path.join(dir_path, e))]
        for name in dirs:
            full = os.path.join(dir_path, name)
            item = QTreeWidgetItem([name + '/'])
            item.setData(0, Qt.UserRole, full)
            parent_item.addChild(item)
            self._add_dir_to_tree(item, full, depth + 1)
        for name in files:
            full = os.path.join(dir_path, name)
            item = QTreeWidgetItem([name])
            item.setData(0, Qt.UserRole, full)
            self._colour_file_item(item, name)
            parent_item.addChild(item)

    @staticmethod
    def _colour_file_item(item: QTreeWidgetItem, name: str):
        ext = os.path.splitext(name)[1].lower()
        colours = {
            '.urdf': '#7ec8e3',
            '.dae':  '#98e08a',
            '.stl':  '#98e08a',
            '.obj':  '#98e08a',
            '.py':   '#f7c97e',
            '.xml':  '#e89e6a',
            '.yaml': '#c8a8e8',
            '.launch': '#f7c97e',
        }
        if ext in colours:
            item.setForeground(0, QColor(colours[ext]))

    def _on_file_double_click(self, item: QTreeWidgetItem, _col):
        path = item.data(0, Qt.UserRole)
        if path and os.path.isfile(path):
            ext = os.path.splitext(path)[1].lower()
            if ext == '.urdf':
                try:
                    with open(path, encoding='utf-8') as fh:
                        self._urdf_text_edit.setPlainText(fh.read())
                    self._tabs.setCurrentIndex(1)
                except Exception as e:
                    self._set_status(f'Cannot open file: {e}')

    # ------------------------------------------------------------------
    # URDF structure tree
    # ------------------------------------------------------------------

    def _populate_urdf_tree(self, tree: QTreeWidget, parsed: dict):
        tree.clear()
        links  = parsed['links']
        joints = parsed['joints']

        # Robot name
        name_item = QTreeWidgetItem(['Robot', parsed.get('robot_name', '?')])
        name_item.setForeground(0, QColor('#7ec8e3'))
        tree.addTopLevelItem(name_item)

        # Links
        links_root = QTreeWidgetItem([f'Links ({len(links)})', ''])
        links_root.setForeground(0, QColor('#98e08a'))
        tree.addTopLevelItem(links_root)
        for idx, lk in enumerate(links):
            colour = _LINK_COLOURS[idx % len(_LINK_COLOURS)]
            li = QTreeWidgetItem([lk['name'], ''])
            li.setForeground(0, QColor(colour))
            has_mesh = bool(lk.get('vis_mesh_uri'))
            li.addChild(QTreeWidgetItem(['mesh', lk['vis_mesh_uri'] or '(none)']))
            li.addChild(QTreeWidgetItem(['mass', f"{lk['mass']:.4g} kg"]))
            links_root.addChild(li)
        links_root.setExpanded(True)

        # Joints
        joints_root = QTreeWidgetItem([f'Joints ({len(joints)})', ''])
        joints_root.setForeground(0, QColor('#f7c97e'))
        tree.addTopLevelItem(joints_root)
        type_colours = {
            'revolute':   '#ff8888',
            'prismatic':  '#88e8e8',
            'continuous': '#ffee88',
            'fixed':      '#888888',
        }
        for j in joints:
            tc = type_colours.get(j['type'], '#cccccc')
            ji = QTreeWidgetItem([j['name'], j['type']])
            ji.setForeground(1, QColor(tc))
            ji.addChild(QTreeWidgetItem(['parent → child',
                                         f"{j['parent']} → {j['child']}"]))
            xyz = j['origin_xyz']
            ji.addChild(QTreeWidgetItem(['origin xyz',
                                         f"{xyz[0]:.4f}  {xyz[1]:.4f}  {xyz[2]:.4f}"]))
            ax  = j['axis']
            ji.addChild(QTreeWidgetItem(['axis',
                                         f"{ax[0]:.3f}  {ax[1]:.3f}  {ax[2]:.3f}"]))
            if j['limits']:
                lim = j['limits']
                ji.addChild(QTreeWidgetItem(['limits',
                    f"[{lim['lower']:.2f}, {lim['upper']:.2f}] rad"]))
            joints_root.addChild(ji)
        joints_root.setExpanded(True)

        tree.resizeColumnToContents(0)

    # ------------------------------------------------------------------
    # Validation bar
    # ------------------------------------------------------------------

    def _show_validation(self, val: dict):
        n_p, n_f, n_w = val['n_pass'], val['n_fail'], val['n_warn']
        if n_f == 0 and n_w == 0:
            icon, colour = 'OK', '#4caf50'
        elif n_f == 0:
            icon, colour = 'WARN', '#ff9800'
        else:
            icon, colour = 'FAIL', '#f44336'

        msg = (f'[{icon}]  {n_p} checks passed'
               + (f',  {n_w} warnings' if n_w else '')
               + (f',  {n_f} ERRORS' if n_f else ''))
        if val['issues']:
            msg += '   |   ' + val['issues'][0].replace('\n', ' ')
        self._set_status(msg, colour)

    # ------------------------------------------------------------------
    # Async mesh loading
    # ------------------------------------------------------------------

    def _load_meshes_async(self, package_dir: str):
        self._progress.setVisible(True)
        self._set_status('Loading meshes…')

        loader  = _MeshLoader(self._parsed, package_dir)
        thread  = QThread()
        loader.moveToThread(thread)
        thread.started.connect(loader.run)
        loader.progress.connect(self._on_mesh_progress)
        loader.finished.connect(self._on_meshes_loaded)
        loader.error.connect(self._on_error)
        loader.finished.connect(thread.quit)
        loader.error.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        self._thread   = thread
        self._loader   = loader
        thread.start()

    def _on_mesh_progress(self, pct: int, msg: str):
        self._progress.setValue(pct)
        self._set_status(msg)

    def _on_meshes_loaded(self, meshes: dict):
        self._progress.setVisible(False)
        self._meshes     = meshes
        self._transforms = compute_link_transforms(self._parsed)

        loaded = sum(1 for m in meshes.values() if m is not None)
        total  = len(meshes)
        self._set_status(f'Rendering…  ({loaded}/{total} meshes loaded)')

        n_rendered = 0
        try:
            n_rendered = self._renderer.render(
                self._parsed, self._meshes, self._transforms
            ) or 0
        except Exception as e:
            # Only abort for real errors, not DeprecationWarning / UserWarning
            if isinstance(e, Warning):
                log.warning(f"PyVista warning during render (non-fatal): {e}")
            else:
                log.error(traceback.format_exc())
                self._set_status(f'Render error: {e}', '#f44336')
                return

        if n_rendered == 0 and loaded == 0:
            self._set_status(
                f'No meshes found in package — check that meshes/visual/ '
                f'or meshes/collision/ contains .dae or .stl files.',
                '#ff9800',
            )
        else:
            self._set_status(
                f'Done.  {len(self._parsed["links"])} links, '
                f'{len(self._parsed["joints"])} joints, '
                f'{loaded}/{total} meshes rendered.',
                '#4caf50',
            )

    def _on_error(self, msg: str):
        self._progress.setVisible(False)
        self._set_status(f'Error: {msg[:120]}')

    # ------------------------------------------------------------------
    # URDF text tab
    # ------------------------------------------------------------------

    def _parse_text_urdf(self):
        text = self._urdf_text_edit.toPlainText().strip()
        if not text:
            return
        try:
            parsed = parse_urdf(text)
        except Exception as e:
            QMessageBox.critical(self, 'Parse Error', str(e))
            return

        self._populate_urdf_tree(self._text_tree, parsed)

        # Render with box placeholders (no package dir → no meshes)
        transforms = compute_link_transforms(parsed)
        try:
            self._renderer.render(parsed, {}, transforms)
        except Exception as e:
            if not isinstance(e, Warning):
                log.warning(f'Render error: {e}')
        self._tabs.setCurrentIndex(0)   # switch to 3D view tab

        self._set_status(
            f'Parsed: robot="{parsed["robot_name"]}"  '
            f'{len(parsed["links"])} links  {len(parsed["joints"])} joints  '
            '(box placeholders — open package folder to load real meshes)',
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_status(self, msg: str, colour: str = '#cccccc'):
        self._status_label.setText(msg)
        self._status_label.setStyleSheet(f'color: {colour};')

    def closeEvent(self, event):
        try:
            if self._plotter:
                self._plotter.close()
        except Exception:
            pass
        event.accept()
