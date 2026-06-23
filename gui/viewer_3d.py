"""
3D viewer widget: embeds PyVista in a PyQt5 widget.
Renders the assembly parts and highlights joints with colored arrows.
"""
import numpy as np

import pyvista as pv
from pyvistaqt import BackgroundPlotter

from PyQt5.QtWidgets import QWidget, QVBoxLayout


class Viewer3D(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._plotter: BackgroundPlotter = None
        self._actors: dict = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._plotter = BackgroundPlotter(show=False)
        self._plotter.set_background('white')
        layout.addWidget(self._plotter.app_window)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_parts(self, meshes: list, names: list):
        """
        meshes: list of trimesh.Trimesh objects (in meters)
        names:  list of part name strings
        """
        self._plotter.clear()
        self._actors = {}
        colors = ['#4a90d9', '#e8935a', '#5cb85c', '#d9534f',
                  '#9b59b6', '#1abc9c', '#f39c12', '#34495e']

        for i, (mesh, name) in enumerate(zip(meshes, names)):
            try:
                pv_mesh = self._trimesh_to_pyvista(mesh)
                color = colors[i % len(colors)]
                actor = self._plotter.add_mesh(
                    pv_mesh,
                    color=color,
                    opacity=0.8,
                    smooth_shading=True,
                    label=name,
                )
                self._actors[name] = actor
            except Exception as e:
                from utils.logger import get_logger
                get_logger(__name__).warning(f"Could not display mesh '{name}': {e}")

        self._plotter.reset_camera()

    def highlight_joint(self, origin: tuple, axis: tuple,
                        color: str = '#ff0000', length: float = 0.05):
        """Draw an arrow at the joint origin along the joint axis."""
        try:
            arrow = pv.Arrow(
                start=origin,
                direction=axis,
                scale=length,
            )
            self._plotter.add_mesh(arrow, color=color)
        except Exception:
            pass

    def show_joint_axes(self, joints: list):
        """Visualize all detected joints as colored arrows."""
        for j in joints:
            color = '#ff4444' if j.joint_type.value == 'revolute' else '#44aaff'
            self.highlight_joint(j.origin_xyz, j.axis_xyz, color=color)

    def reset_camera(self):
        self._plotter.reset_camera()

    def close(self):
        if self._plotter:
            self._plotter.close()

    # ------------------------------------------------------------------
    # Conversion helper
    # ------------------------------------------------------------------

    @staticmethod
    def _trimesh_to_pyvista(mesh) -> pv.PolyData:
        import trimesh
        verts = np.array(mesh.vertices)
        faces = mesh.faces
        # PyVista face format: [3, v0, v1, v2, ...]
        n = len(faces)
        pv_faces = np.hstack([np.full((n, 1), 3, dtype=np.int32), faces]).ravel()
        return pv.PolyData(verts, pv_faces)
