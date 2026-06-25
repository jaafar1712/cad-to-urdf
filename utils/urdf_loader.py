"""
URDF loader utility for the package viewer.
Parses URDF XML, resolves package:// mesh paths, and computes
forward kinematics (all joints at zero) to get each link's world pose.
"""
import os
import xml.etree.ElementTree as ET
import numpy as np
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# URDF parser
# ---------------------------------------------------------------------------

def parse_urdf(source: str) -> dict:
    """
    Parse URDF from a file path OR from a raw XML string.
    Returns a dict with keys: robot_name, links, joints.
    """
    if os.path.isfile(source):
        try:
            root = ET.parse(source).getroot()
        except ET.ParseError as e:
            raise ValueError(f"XML parse error in {source}: {e}")
    else:
        try:
            root = ET.fromstring(source)
        except ET.ParseError as e:
            raise ValueError(f"XML parse error: {e}")

    links  = [_parse_link(el)  for el in root.findall('link')]
    joints = [_parse_joint(el) for el in root.findall('joint')]
    return {
        'robot_name': root.get('name', 'robot'),
        'links':  links,
        'joints': joints,
    }


def _parse_link(el: ET.Element) -> dict:
    name = el.get('name', 'unnamed')

    vis_mesh_uri = None
    vis_scale    = (1.0, 1.0, 1.0)
    vis_origin_xyz = (0.0, 0.0, 0.0)
    vis_origin_rpy = (0.0, 0.0, 0.0)
    col_mesh_uri = None
    col_scale    = (1.0, 1.0, 1.0)
    rgba         = (0.7, 0.7, 0.75, 1.0)

    visual = el.find('visual')
    if visual is not None:
        orig = visual.find('origin')
        if orig is not None:
            vis_origin_xyz = _parse_xyz(orig.get('xyz', '0 0 0'))
            vis_origin_rpy = _parse_xyz(orig.get('rpy', '0 0 0'))
        geom = visual.find('geometry')
        if geom is not None:
            mesh = geom.find('mesh')
            if mesh is not None:
                vis_mesh_uri = mesh.get('filename', '')
                vis_scale    = _parse_xyz(mesh.get('scale', '1 1 1'))
        mat = visual.find('material')
        if mat is not None:
            col_el = mat.find('color')
            if col_el is not None:
                rgba = _parse_xyz(col_el.get('rgba', '0.7 0.7 0.75 1.0'), n=4)

    collision = el.find('collision')
    if collision is not None:
        geom = collision.find('geometry')
        if geom is not None:
            mesh = geom.find('mesh')
            if mesh is not None:
                col_mesh_uri = mesh.get('filename', '')
                col_scale    = _parse_xyz(mesh.get('scale', '1 1 1'))

    inertial   = el.find('inertial')
    mass       = 0.0
    com        = (0.0, 0.0, 0.0)
    if inertial is not None:
        m_el = inertial.find('mass')
        if m_el is not None:
            mass = float(m_el.get('value', 0.0))
        o_el = inertial.find('origin')
        if o_el is not None:
            com = _parse_xyz(o_el.get('xyz', '0 0 0'))

    return {
        'name':            name,
        'vis_mesh_uri':    vis_mesh_uri,
        'vis_scale':       vis_scale,
        'vis_origin_xyz':  vis_origin_xyz,
        'vis_origin_rpy':  vis_origin_rpy,
        'col_mesh_uri':    col_mesh_uri,
        'col_scale':       col_scale,
        'color_rgba':      rgba,
        'mass':            mass,
        'com':             com,
    }


def _parse_joint(el: ET.Element) -> dict:
    name  = el.get('name', 'unnamed')
    jtype = el.get('type', 'fixed')

    parent_el = el.find('parent')
    child_el  = el.find('child')
    parent = parent_el.get('link', '') if parent_el is not None else ''
    child  = child_el.get('link',  '') if child_el  is not None else ''

    orig   = el.find('origin')
    xyz    = _parse_xyz(orig.get('xyz', '0 0 0')) if orig is not None else (0.0, 0.0, 0.0)
    rpy    = _parse_xyz(orig.get('rpy', '0 0 0')) if orig is not None else (0.0, 0.0, 0.0)

    ax_el  = el.find('axis')
    axis   = _parse_xyz(ax_el.get('xyz', '0 0 1')) if ax_el is not None else (0.0, 0.0, 1.0)

    lim_el = el.find('limit')
    limits = None
    if lim_el is not None:
        limits = {
            'lower':    float(lim_el.get('lower',    -3.14159)),
            'upper':    float(lim_el.get('upper',     3.14159)),
            'effort':   float(lim_el.get('effort',       0.0)),
            'velocity': float(lim_el.get('velocity',     0.0)),
        }

    return {
        'name':       name,
        'type':       jtype,
        'parent':     parent,
        'child':      child,
        'origin_xyz': xyz,
        'origin_rpy': rpy,
        'axis':       axis,
        'limits':     limits,
    }


def _parse_xyz(s: str, n: int = 3) -> tuple:
    parts = s.split()
    vals  = [float(x) for x in parts[:n]]
    while len(vals) < n:
        vals.append(0.0)
    return tuple(vals)


# ---------------------------------------------------------------------------
# Mesh path resolution
# ---------------------------------------------------------------------------

def resolve_mesh_path(uri: str, package_dir: str) -> Optional[str]:
    """
    Resolve a URDF mesh URI to an absolute file path.
    Handles package://<pkg>/path and model://<pkg>/path.
    """
    if not uri:
        return None
    for prefix in ('package://', 'model://'):
        if uri.startswith(prefix):
            rest = uri[len(prefix):]
            # rest = "<pkg_name>/path/to/mesh"
            slash = rest.find('/')
            if slash >= 0:
                rel = rest[slash + 1:]
                return os.path.join(package_dir, rel)
            return None
    # Bare relative path
    p = os.path.join(package_dir, uri) if not os.path.isabs(uri) else uri
    return p


# ---------------------------------------------------------------------------
# Forward kinematics
# ---------------------------------------------------------------------------

def compute_link_transforms(parsed: dict, q: dict = None) -> Dict[str, np.ndarray]:
    """
    Compute each link's 4x4 world transform at joint angles q (default 0).
    Returns {link_name: 4x4 numpy array}.
    """
    if q is None:
        q = {}

    all_link_names = {lk['name'] for lk in parsed['links']}
    joints         = parsed['joints']
    children       = {j['child'] for j in joints}
    roots          = all_link_names - children

    transforms: Dict[str, np.ndarray] = {r: np.eye(4) for r in roots}

    # BFS — iterate until no new links are added
    changed = True
    max_iters = len(all_link_names) + 5
    iters = 0
    while changed and iters < max_iters:
        changed = False
        iters  += 1
        for j in joints:
            if j['parent'] not in transforms or j['child'] in transforms:
                continue
            parent_T  = transforms[j['parent']]
            joint_T   = _xform(j['origin_xyz'], j['origin_rpy'])
            angle     = q.get(j['name'], 0.0)
            if j['type'] in ('revolute', 'continuous') and abs(angle) > 1e-9:
                joint_T = joint_T @ _axis_angle_T(j['axis'], angle)
            elif j['type'] == 'prismatic' and abs(angle) > 1e-9:
                ax = np.array(j['axis'], dtype=float)
                ax /= np.linalg.norm(ax) + 1e-12
                T_pris = np.eye(4)
                T_pris[:3, 3] = ax * angle
                joint_T = joint_T @ T_pris
            transforms[j['child']] = parent_T @ joint_T
            changed = True

    # Disconnected links (rare, but handle gracefully)
    for lk in parsed['links']:
        if lk['name'] not in transforms:
            transforms[lk['name']] = np.eye(4)

    return transforms


def _rpy_to_rot(rpy) -> np.ndarray:
    r, p, y = rpy
    cr, sr = np.cos(r), np.sin(r)
    cp, sp = np.cos(p), np.sin(p)
    cy, sy = np.cos(y), np.sin(y)
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def _xform(xyz, rpy) -> np.ndarray:
    T = np.eye(4)
    T[:3, :3] = _rpy_to_rot(rpy)
    T[:3, 3]  = xyz
    return T


def _axis_angle_T(axis, angle: float) -> np.ndarray:
    ax = np.array(axis, dtype=float)
    ax /= np.linalg.norm(ax) + 1e-12
    c, s  = np.cos(angle), np.sin(angle)
    x, y, z = ax
    R = np.array([
        [c + x*x*(1-c),    x*y*(1-c) - z*s,  x*z*(1-c) + y*s],
        [y*x*(1-c) + z*s,  c + y*y*(1-c),    y*z*(1-c) - x*s],
        [z*x*(1-c) - y*s,  z*y*(1-c) + x*s,  c + z*z*(1-c)  ],
    ])
    T = np.eye(4)
    T[:3, :3] = R
    return T


# ---------------------------------------------------------------------------
# Package validation
# ---------------------------------------------------------------------------

def validate_package(package_dir: str, parsed: dict) -> dict:
    """
    Check that every mesh referenced in the URDF exists on disk.
    Returns {ok, n_pass, n_fail, n_warn, issues: [str]}.
    """
    issues  = []
    n_pass  = n_fail = n_warn = 0

    for lk in parsed['links']:
        for role, uri_key in (('visual', 'vis_mesh_uri'), ('collision', 'col_mesh_uri')):
            uri = lk.get(uri_key)
            if not uri:
                continue
            path = resolve_mesh_path(uri, package_dir)
            if path and os.path.isfile(path):
                n_pass += 1
            else:
                n_fail += 1
                issues.append(f"[{lk['name']}] {role} mesh missing:\n  {uri}\n  → {path}")

    # Check launch dir
    launch_dir = os.path.join(package_dir, 'launch')
    if os.path.isdir(launch_dir) and any(
        f.endswith(('.py', '.launch', '.launch.py'))
        for f in os.listdir(launch_dir)
    ):
        n_pass += 1
    else:
        n_warn += 1
        issues.append("No launch file found in launch/")

    # Check CMakeLists + package.xml
    for fname in ('CMakeLists.txt', 'package.xml'):
        fpath = os.path.join(package_dir, fname)
        if os.path.isfile(fpath):
            n_pass += 1
        else:
            n_warn += 1
            issues.append(f"Missing build file: {fname}")

    return {
        'ok':     n_fail == 0,
        'n_pass': n_pass,
        'n_fail': n_fail,
        'n_warn': n_warn,
        'issues': issues,
    }
