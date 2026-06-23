import numpy as np
from typing import Tuple


def normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def angle_between(a: np.ndarray, b: np.ndarray) -> float:
    """Angle in degrees between two vectors."""
    a, b = normalize(a), normalize(b)
    dot = np.clip(np.dot(a, b), -1.0, 1.0)
    return np.degrees(np.arccos(abs(dot)))


def axes_are_parallel(a: np.ndarray, b: np.ndarray, tol_deg: float = 5.0) -> bool:
    return angle_between(a, b) < tol_deg


def distance_between_lines(
    pt_a: np.ndarray, dir_a: np.ndarray,
    pt_b: np.ndarray, dir_b: np.ndarray,
) -> float:
    """Shortest distance between two infinite lines in 3D."""
    cross = np.cross(dir_a, dir_b)
    norm_cross = np.linalg.norm(cross)
    if norm_cross < 1e-12:
        # Lines are parallel — distance is point-to-line
        return np.linalg.norm(np.cross(dir_a, pt_b - pt_a))
    return abs(np.dot(cross / norm_cross, pt_b - pt_a))


def rotation_matrix_from_vectors(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """Rodrigues rotation matrix that rotates unit vector src onto dst."""
    src, dst = normalize(src), normalize(dst)
    v = np.cross(src, dst)
    c = np.dot(src, dst)
    if abs(c + 1.0) < 1e-12:
        # 180° rotation — pick an arbitrary perpendicular axis
        perp = np.array([1, 0, 0]) if abs(src[0]) < 0.9 else np.array([0, 1, 0])
        v = normalize(np.cross(src, perp))
        return 2.0 * np.outer(v, v) - np.eye(3)
    s = np.linalg.norm(v)
    kmat = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + kmat + kmat @ kmat * ((1 - c) / (s ** 2 + 1e-30))


def rpy_from_rotation_matrix(R: np.ndarray) -> Tuple[float, float, float]:
    """Extract roll-pitch-yaw (XYZ Euler) from a 3×3 rotation matrix."""
    sy = np.sqrt(R[0, 0] ** 2 + R[1, 0] ** 2)
    if sy > 1e-6:
        roll  = np.arctan2( R[2, 1], R[2, 2])
        pitch = np.arctan2(-R[2, 0], sy)
        yaw   = np.arctan2( R[1, 0], R[0, 0])
    else:
        roll  = np.arctan2(-R[1, 2], R[1, 1])
        pitch = np.arctan2(-R[2, 0], sy)
        yaw   = 0.0
    return float(roll), float(pitch), float(yaw)


def rpy_to_align_z_with(axis: np.ndarray) -> Tuple[float, float, float]:
    """Return RPY so that the Z-axis of a frame points along `axis`."""
    R = rotation_matrix_from_vectors(np.array([0.0, 0.0, 1.0]), normalize(axis))
    return rpy_from_rotation_matrix(R)


def occ_pnt_to_np(pnt) -> np.ndarray:
    return np.array([pnt.X(), pnt.Y(), pnt.Z()])


def occ_dir_to_np(d) -> np.ndarray:
    return normalize(np.array([d.X(), d.Y(), d.Z()]))
