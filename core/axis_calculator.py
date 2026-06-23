"""
Compute joint axis direction and origin in world space from
cylindrical face geometry.
"""
import numpy as np
from typing import Tuple, Optional, Dict

from utils.geometry_utils import (normalize, occ_pnt_to_np, occ_dir_to_np,
                                   rpy_to_align_z_with)
from utils.logger import get_logger

log = get_logger(__name__)


class AxisCalculator:

    def compute_joint_frame(self,
                            cyl_face: Dict,
                            reference_origin: Optional[np.ndarray] = None
                            ) -> Tuple[Tuple, Tuple]:
        """
        Compute origin and RPY for a joint frame aligned with a cylinder axis.

        Args:
            cyl_face:         A cylindrical face dict from TopologyExplorer
            reference_origin: Optional override for the origin point (meters)

        Returns:
            (origin_xyz, origin_rpy) both as (x, y, z) tuples in meters / radians
        """
        axis_dir = occ_dir_to_np(cyl_face['axis_dir'])
        axis_pt  = occ_pnt_to_np(cyl_face['axis_point']) * 0.001   # mm → m

        origin = reference_origin if reference_origin is not None else axis_pt
        rpy    = rpy_to_align_z_with(axis_dir)

        return tuple(origin.tolist()), rpy

    def best_joint_axis(self, cyls_a: list, cyls_b: list) -> Optional[np.ndarray]:
        """
        Find the best-matching axis direction between two sets of cylinder faces.
        Returns a unit vector in the direction of the shared axis, or None.
        """
        from utils.geometry_utils import axes_are_parallel, distance_between_lines

        best_dist = np.inf
        best_axis = None

        for ca in cyls_a:
            for cb in cyls_b:
                da = occ_dir_to_np(ca['axis_dir'])
                db = occ_dir_to_np(cb['axis_dir'])
                pa = occ_pnt_to_np(ca['axis_point']) * 0.001
                pb = occ_pnt_to_np(cb['axis_point']) * 0.001

                if not axes_are_parallel(da, db, tol_deg=5.0):
                    continue
                dist = distance_between_lines(pa, da, pb, db)
                if dist < best_dist:
                    best_dist = dist
                    best_axis = da

        return best_axis

    def project_point_onto_axis(self, point: np.ndarray,
                                axis_pt: np.ndarray,
                                axis_dir: np.ndarray) -> np.ndarray:
        """Project a 3D point onto the infinite line (axis_pt, axis_dir)."""
        d = normalize(axis_dir)
        return axis_pt + np.dot(point - axis_pt, d) * d
