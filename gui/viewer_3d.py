"""
3D viewer widget: embeds PyVista in a PyQt5 widget.
Renders the whole assembly as a single mesh and overlays joint axes.
"""
import numpy as np

import pyvista as pv
from pyvistaqt import BackgroundPlotter

from PyQt5.QtWidgets import QWidget, QVBoxLayout


class Viewer3D(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._plotter: BackgroundPlotter = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._plotter = BackgroundPlotter(show=False)
        self._plotter.set_background('#1e1e2e')   # dark navy — good contrast
        layout.addWidget(self._plotter.app_window)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_assembly(self, mesh, joints: list):
        """
        Render the whole-assembly trimesh as one solid mesh and overlay
        detected joint axes as coloured arrows.

        mesh:   trimesh.Trimesh of the full assembled robot (metres)
        joints: list of DetectedJoint objects
        """
        self._plotter.clear()

        try:
            pv_mesh = self._trimesh_to_pyvista(mesh)
            self._plotter.add_mesh(
                pv_mesh,
                color='#b0c4de',      # light steel blue — neutral, readable
                opacity=1.0,
                smooth_shading=True,
                show_edges=True,
                edge_color='#404060',
                line_width=0.5,
            )
        except Exception as e:
            from utils.logger import get_logger
            get_logger(__name__).warning(f"Could not display assembly mesh: {e}")

        self._draw_joint_axes(joints)

        # Isometric-ish camera: look from a diagonal above-right direction
        self._plotter.reset_camera()
        try:
            bounds = pv_mesh.bounds   # (xmin, xmax, ymin, ymax, zmin, zmax)
            cx = (bounds[0] + bounds[1]) / 2
            cy = (bounds[2] + bounds[3]) / 2
            cz = (bounds[4] + bounds[5]) / 2
            span = max(bounds[1]-bounds[0], bounds[3]-bounds[2], bounds[5]-bounds[4])
            dist = span * 2.0
            self._plotter.camera_position = [
                (cx + dist, cy + dist * 0.6, cz + dist * 0.8),  # camera eye
                (cx, cy, cz),                                      # focal point
                (0, 0, 1),                                         # up vector
            ]
        except Exception:
            pass   # reset_camera already gave a reasonable view

    # kept for backwards-compatibility if any other code calls it
    def show_parts(self, meshes: list, names: list):
        """Legacy: merge all part meshes and show as one assembly."""
        import trimesh as tm
        combined = None
        for m in meshes:
            if m is None:
                continue
            try:
                combined = tm.util.concatenate([combined, m]) if combined else m
            except Exception:
                pass
        if combined is not None:
            self.show_assembly(combined, [])

    def highlight_joint(self, origin: tuple, axis: tuple,
                        color: str = '#ff4444', length: float = None):
        """Draw an arrow at the joint origin along the joint axis."""
        try:
            if length is None:
                # Auto-scale: 8% of the visible diagonal
                try:
                    b = self._plotter.bounds
                    diag = ((b[1]-b[0])**2 + (b[3]-b[2])**2 + (b[5]-b[4])**2) ** 0.5
                    length = max(diag * 0.08, 0.005)
                except Exception:
                    length = 0.02
            arrow = pv.Arrow(start=origin, direction=axis, scale=length, tip_length=0.25)
            self._plotter.add_mesh(arrow, color=color, lighting=False)
        except Exception:
            pass

    def reset_camera(self):
        self._plotter.reset_camera()

    def close(self):
        if self._plotter:
            self._plotter.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _draw_joint_axes(self, joints: list):
        """Overlay all detected joints as coloured arrows."""
        COLORS = {
            'revolute':   '#ff6b6b',   # red
            'prismatic':  '#4ecdc4',   # teal
            'continuous': '#ffe66d',   # yellow
            'fixed':      '#95a5a6',   # grey
        }
        for j in joints:
            color = COLORS.get(j.joint_type.value, '#ffffff')
            self.highlight_joint(j.origin_xyz, j.axis_xyz, color=color)

    @staticmethod
    def _trimesh_to_pyvista(mesh) -> pv.PolyData:
        verts = np.array(mesh.vertices)
        faces = mesh.faces
        n = len(faces)
        pv_faces = np.hstack([np.full((n, 1), 3, dtype=np.int32), faces]).ravel()
        return pv.PolyData(verts, pv_faces)
