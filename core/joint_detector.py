"""
Joint detection between adjacent parts.
Classifies joint type (revolute / prismatic / fixed) from cylindrical
face geometry shared between two parts.
"""
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Tuple, List
from enum import Enum

from utils.geometry_utils import (normalize, axes_are_parallel,
                                   distance_between_lines,
                                   occ_pnt_to_np, occ_dir_to_np)
from utils.logger import get_logger

log = get_logger(__name__)


class JointType(Enum):
    REVOLUTE   = "revolute"
    FIXED      = "fixed"
    PRISMATIC  = "prismatic"
    CONTINUOUS = "continuous"
    UNKNOWN    = "unknown"


@dataclass
class DetectedJoint:
    joint_type:  JointType
    parent_link: str
    child_link:  str
    origin_xyz:  Tuple[float, float, float]   # meters
    origin_rpy:  Tuple[float, float, float]   # radians
    axis_xyz:    Tuple[float, float, float]   # unit vector
    confidence:  float                         # 0.0 – 1.0
    evidence:    str                           # human-readable reason
    # Editable limits (can be changed in GUI)
    limit_lower: float = -3.14159
    limit_upper: float =  3.14159
    effort:      float = 150.0
    velocity:    float = 3.14
    name:        str   = ""

    def __post_init__(self):
        if not self.name:
            self.name = (f"{self.parent_link}_to_{self.child_link}_"
                         f"{self.joint_type.value}")

    def to_dict(self) -> dict:
        return {
            'name':        self.name,
            'type':        self.joint_type.value,
            'parent':      self.parent_link,
            'child':       self.child_link,
            'origin_xyz':  self.origin_xyz,
            'origin_rpy':  self.origin_rpy,
            'axis_xyz':    self.axis_xyz,
            'limit_lower': self.limit_lower,
            'limit_upper': self.limit_upper,
            'effort':      self.effort,
            'velocity':    self.velocity,
            'confidence':  self.confidence,
            'evidence':    self.evidence,
        }


class JointDetector:

    # Thresholds
    AXIS_PARALLEL_TOL_DEG    = 5.0    # degrees — axes treated as parallel
    COLLINEAR_DIST_TOL_M     = 0.015  # 15 mm — axes treated as collinear
    RADIUS_MATCH_TOL_M       = 0.003  # 3 mm — radii treated as equal
    PIN_IN_HOLE_RATIO_MIN    = 0.7    # smaller/larger radius > this → pin-in-hole
    PIN_IN_HOLE_RATIO_MAX    = 1.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_joint(self,
                     part_a_topo: dict,
                     part_b_topo: dict,
                     part_a_name: str,
                     part_b_name: str) -> DetectedJoint:
        """
        Determine the joint type between two parts from their topology data.
        Returns the highest-confidence DetectedJoint found.
        """
        cyls_a = part_a_topo.get('cylindrical_faces', [])
        cyls_b = part_b_topo.get('cylindrical_faces', [])

        best: Optional[DetectedJoint] = None

        if cyls_a and cyls_b:
            for ca in cyls_a:
                for cb in cyls_b:
                    # --- Try REVOLUTE ---
                    j = self._check_revolute(ca, cb, part_a_name, part_b_name)
                    if j and (best is None or j.confidence > best.confidence):
                        best = j

                    # --- Try PRISMATIC (only if no revolute found) ---
                    if best is None or best.joint_type != JointType.REVOLUTE:
                        j = self._check_prismatic(ca, cb, part_a_name, part_b_name)
                        if j and (best is None or j.confidence > best.confidence):
                            best = j

        if best and best.confidence >= 0.55:
            log.info(
                f"Joint detected: {part_a_name} → {part_b_name}  "
                f"type={best.joint_type.value}  conf={best.confidence:.2f}"
            )
            return best

        # Default: FIXED
        return self._make_fixed(part_a_name, part_b_name,
                                part_a_topo, part_b_topo)

    def detect_all_joints(self,
                          parts: List[dict],
                          topos: List[dict]) -> List[DetectedJoint]:
        """
        Build a kinematic chain: detect joints between consecutive parts.
        Skips self-loops and links that already have a parent.
        Guarantees all joint names are unique.
        """
        joints: List[DetectedJoint] = []
        used_children: set = set()   # each link may appear as child only once
        used_names:    set = set()   # joint names must be unique

        for i in range(len(parts) - 1):
            name_a = parts[i]['name']
            name_b = parts[i + 1]['name']

            if name_a == name_b:
                log.warning(f"Skipping self-loop joint: '{name_a}' -> '{name_b}'")
                continue

            if name_b in used_children:
                log.warning(
                    f"Skipping joint '{name_a}'->'{name_b}': "
                    f"'{name_b}' already has a parent"
                )
                continue

            j = self.detect_joint(topos[i], topos[i + 1], name_a, name_b)

            # Guarantee unique joint name
            base, counter = j.name, 1
            while j.name in used_names:
                j.name = f"{base}_{counter}"
                counter += 1

            used_names.add(j.name)
            used_children.add(name_b)
            joints.append(j)

        return joints

    # ------------------------------------------------------------------
    # Revolute detection
    # ------------------------------------------------------------------

    def _check_revolute(self, cyl_a, cyl_b, name_a, name_b) -> Optional[DetectedJoint]:
        dir_a = occ_dir_to_np(cyl_a['axis_dir'])
        dir_b = occ_dir_to_np(cyl_b['axis_dir'])
        pt_a  = occ_pnt_to_np(cyl_a['axis_point']) * 0.001   # mm → m
        pt_b  = occ_pnt_to_np(cyl_b['axis_point']) * 0.001

        # 1. Axes must be parallel (or anti-parallel)
        if not axes_are_parallel(dir_a, dir_b, self.AXIS_PARALLEL_TOL_DEG):
            return None

        # 2. Axes must be collinear (share the same line in 3D)
        dist = distance_between_lines(pt_a, dir_a, pt_b, dir_b)
        if dist > self.COLLINEAR_DIST_TOL_M:
            return None

        # Compute confidence from radius relationship
        r_a = cyl_a['radius'] * 0.001   # mm → m
        r_b = cyl_b['radius'] * 0.001
        r_diff = abs(r_a - r_b)

        if r_diff < self.RADIUS_MATCH_TOL_M:
            # Matching radii — shaft-in-shaft (high confidence)
            confidence = 0.92
            evidence = f"Collinear cylinders with matching radii ({r_a*1000:.1f}mm)"
        else:
            r_small = min(r_a, r_b)
            r_large = max(r_a, r_b)
            ratio = r_small / (r_large + 1e-9)
            if self.PIN_IN_HOLE_RATIO_MIN <= ratio <= self.PIN_IN_HOLE_RATIO_MAX:
                # Pin in hole — still revolute
                confidence = 0.82
                evidence = (f"Pin-in-hole cylinders: r={r_small*1000:.1f}mm / "
                            f"{r_large*1000:.1f}mm, ratio={ratio:.2f}")
            else:
                confidence = 0.70
                evidence = f"Collinear cylinders (radius mismatch: {r_diff*1000:.1f}mm)"

        # Joint origin = midpoint between the two cylinder axis reference points
        origin_m = (pt_a + pt_b) / 2.0

        # Ensure axis points in the canonical direction (prefer +Z, +X, +Y)
        axis = dir_a.copy()
        if axis[2] < 0 or (abs(axis[2]) < 1e-6 and axis[0] < 0):
            axis = -axis

        return DetectedJoint(
            joint_type=JointType.REVOLUTE,
            parent_link=name_a,
            child_link=name_b,
            origin_xyz=tuple(origin_m.tolist()),
            origin_rpy=(0.0, 0.0, 0.0),
            axis_xyz=tuple(axis.tolist()),
            confidence=confidence,
            evidence=evidence,
        )

    # ------------------------------------------------------------------
    # Prismatic detection
    # ------------------------------------------------------------------

    def _check_prismatic(self, cyl_a, cyl_b, name_a, name_b) -> Optional[DetectedJoint]:
        dir_a = occ_dir_to_np(cyl_a['axis_dir'])
        dir_b = occ_dir_to_np(cyl_b['axis_dir'])
        pt_a  = occ_pnt_to_np(cyl_a['axis_point']) * 0.001
        pt_b  = occ_pnt_to_np(cyl_b['axis_point']) * 0.001

        # Axes must be parallel
        if not axes_are_parallel(dir_a, dir_b, self.AXIS_PARALLEL_TOL_DEG):
            return None

        # For prismatic: axes are parallel but NOT collinear
        dist = distance_between_lines(pt_a, dir_a, pt_b, dir_b)
        if dist <= self.COLLINEAR_DIST_TOL_M:
            return None   # collinear → revolute, not prismatic

        origin_m = (pt_a + pt_b) / 2.0
        axis = dir_a.copy()

        return DetectedJoint(
            joint_type=JointType.PRISMATIC,
            parent_link=name_a,
            child_link=name_b,
            origin_xyz=tuple(origin_m.tolist()),
            origin_rpy=(0.0, 0.0, 0.0),
            axis_xyz=tuple(axis.tolist()),
            confidence=0.65,
            evidence=(f"Parallel cylinders (non-collinear, axis offset={dist*1000:.1f}mm) "
                      f"— prismatic motion along shared axis"),
            limit_lower=-0.1,
            limit_upper=0.1,
        )

    # ------------------------------------------------------------------
    # Fixed fallback
    # ------------------------------------------------------------------

    def _make_fixed(self, name_a, name_b, topo_a, topo_b) -> DetectedJoint:
        # Estimate a reasonable origin from planar faces if available
        origin = (0.0, 0.0, 0.0)
        planes_a = topo_a.get('planar_faces', [])
        if planes_a:
            pt = occ_pnt_to_np(planes_a[0]['origin']) * 0.001
            origin = tuple(pt.tolist())

        return DetectedJoint(
            joint_type=JointType.FIXED,
            parent_link=name_a,
            child_link=name_b,
            origin_xyz=origin,
            origin_rpy=(0.0, 0.0, 0.0),
            axis_xyz=(0.0, 0.0, 1.0),
            confidence=0.5,
            evidence="No matching cylindrical face geometry found — defaulting to fixed joint",
        )
