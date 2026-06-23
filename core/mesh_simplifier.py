"""
Polygon count reduction for collision meshes using trimesh quadric decimation.
"""
import trimesh
import numpy as np
from utils.logger import get_logger

log = get_logger(__name__)


class MeshSimplifier:

    def simplify(self, mesh: trimesh.Trimesh,
                 target_faces: int) -> trimesh.Trimesh:
        """
        Reduce polygon count to at most target_faces using quadric decimation.
        Returns the simplified mesh (or original if already under target).
        """
        if len(mesh.faces) <= target_faces:
            return mesh

        original_count = len(mesh.faces)
        try:
            simplified = mesh.simplify_quadric_decimation(target_faces)
        except Exception as e:
            log.warning(f"Quadric decimation failed ({e}), falling back to voxel")
            simplified = self._voxel_simplify(mesh, target_faces)

        log.debug(
            f"Simplified mesh: {original_count} → {len(simplified.faces)} faces "
            f"(target: {target_faces})"
        )
        return simplified

    def _voxel_simplify(self, mesh: trimesh.Trimesh,
                        target_faces: int) -> trimesh.Trimesh:
        """Fallback: voxelize and reconstruct surface."""
        try:
            # Estimate voxel pitch to achieve target face count
            pitch = mesh.scale / (target_faces ** (1 / 3))
            voxels = mesh.voxelized(pitch=max(pitch, 1e-4))
            hull_mesh = voxels.as_boxes()
            return hull_mesh
        except Exception as e:
            log.warning(f"Voxel simplification failed ({e}) — returning convex hull")
            return trimesh.convex.convex_hull(mesh)

    def convex_hull(self, mesh: trimesh.Trimesh) -> trimesh.Trimesh:
        """Generate convex hull as the most aggressive simplification."""
        return trimesh.convex.convex_hull(mesh)
