"""
Comprehensive URDF package validator.

Checks performed
----------------
1.  Package directory structure (urdf/, meshes/visual/, meshes/collision/)
2.  URDF file exists and is valid XML
3.  All <mesh filename="package://…"> URIs resolve to existing files on disk
4.  No duplicate link or joint names
5.  Kinematic chain is fully connected (no orphan links)
6.  Every non-world link has a positive mass
7.  Mass values are physically plausible (≥ 1 g)
8.  Diagonal inertia moments are positive and not suspiciously small
9.  Triangle inequality holds for each inertia triple
10. Inertia matrix is positive-definite (Sylvester criterion)
"""
import os
import re
from collections import defaultdict
from typing import List, Dict, Tuple, Optional

try:
    from lxml import etree
    HAS_LXML = True
except ImportError:
    import xml.etree.ElementTree as etree
    HAS_LXML = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# ── thresholds ──────────────────────────────────────────────────────────────

MIN_MASS_KG      = 1e-3    # 1 g — below this we warn (likely a surface model)
MIN_INERTIA_KGM2 = 1e-8   # below this is suspicious for any real mechanical part
                            # (Gazebo typically needs > 1e-9 to stay stable;
                            #  cad2urdf clamps to 1e-9, so ≤ that = clamped)


# ── result helpers ───────────────────────────────────────────────────────────

PASS  = "OK  "
WARN  = "WARN"
FAIL  = "FAIL"


class CheckResult:
    def __init__(self, tag: str, label: str, detail: str = ""):
        self.tag    = tag    # PASS / WARN / FAIL
        self.label  = label
        self.detail = detail

    def __str__(self):
        s = f"[{self.tag}] {self.label}"
        if self.detail:
            s += f"\n       {self.detail}"
        return s

    @property
    def is_fail(self):  return self.tag == FAIL
    @property
    def is_warn(self):  return self.tag == WARN
    @property
    def is_pass(self):  return self.tag == PASS


# ── main API ─────────────────────────────────────────────────────────────────

def validate_package(pkg_dir: str) -> Dict:
    """
    Validate a ROS 2 package directory exported by CAD2URDF.

    Returns dict:
      {
        'pkg_dir':   str,
        'urdf_path': str | None,
        'results':   [CheckResult, …],
        'n_pass':    int,
        'n_warn':    int,
        'n_fail':    int,
        'ok':        bool,           # True only if n_fail == 0
        'report':    str,            # human-readable, coloured with ASCII marks
      }
    """
    results: List[CheckResult] = []
    urdf_path: Optional[str] = None

    # 1. Package structure
    urdf_dir  = os.path.join(pkg_dir, 'urdf')
    vis_dir   = os.path.join(pkg_dir, 'meshes', 'visual')
    col_dir   = os.path.join(pkg_dir, 'meshes', 'collision')

    missing_dirs = [d for d in [urdf_dir, vis_dir, col_dir]
                    if not os.path.isdir(d)]
    if missing_dirs:
        results.append(CheckResult(
            FAIL, "Package directory structure",
            "Missing: " + ", ".join(
                os.path.relpath(d, pkg_dir) for d in missing_dirs
            )
        ))
    else:
        results.append(CheckResult(PASS, "Package directory structure"))

    # Find URDF file
    urdf_files = []
    if os.path.isdir(urdf_dir):
        urdf_files = [f for f in os.listdir(urdf_dir)
                      if f.endswith('.urdf')]
    if not urdf_files:
        results.append(CheckResult(FAIL, "URDF file",
                                   f"No .urdf file found in {urdf_dir}"))
        return _finalise(pkg_dir, urdf_path, results)

    urdf_path = os.path.join(urdf_dir, urdf_files[0])
    if len(urdf_files) > 1:
        results.append(CheckResult(WARN, "Multiple URDF files",
                                   f"Using first: {urdf_files[0]}"))

    # 2. XML validity
    try:
        if HAS_LXML:
            tree  = etree.parse(urdf_path)
            root  = tree.getroot()
        else:
            root  = etree.parse(urdf_path).getroot()
    except Exception as e:
        results.append(CheckResult(FAIL, "URDF XML validity", str(e)))
        return _finalise(pkg_dir, urdf_path, results)

    results.append(CheckResult(PASS, "URDF XML validity"))

    if root.tag != 'robot':
        results.append(CheckResult(FAIL, "Root element",
                                   f"Expected <robot>, got <{root.tag}>"))
        return _finalise(pkg_dir, urdf_path, results)

    pkg_name = root.get('name', os.path.basename(pkg_dir))

    # Parse all links and joints
    links  = {el.get('name'): el for el in root.findall('link')}
    joints = {el.get('name'): el for el in root.findall('joint')}
    link_names  = list(links.keys())
    joint_names = list(joints.keys())

    # 3. Mesh URI resolution
    mesh_ok, mesh_fail = 0, []
    for el in root.iter('mesh'):
        uri = el.get('filename', '')
        resolved = _resolve_uri(uri, pkg_name, pkg_dir)
        if resolved is None:
            mesh_fail.append(f"  cannot parse: {uri!r}")
        elif not os.path.isfile(resolved):
            mesh_fail.append(
                f"  missing: {uri}\n"
                f"           → {os.path.relpath(resolved, pkg_dir)}"
            )
        else:
            mesh_ok += 1

    if mesh_fail:
        results.append(CheckResult(
            FAIL,
            f"Mesh files  ({mesh_ok} OK, {len(mesh_fail)} missing)",
            "\n       ".join(mesh_fail[:10])
            + (f"\n       … and {len(mesh_fail)-10} more" if len(mesh_fail) > 10 else "")
        ))
    else:
        results.append(CheckResult(PASS,
                                   f"Mesh files  ({mesh_ok} files verified)"))

    # 4. Duplicate names
    dup_links  = _duplicates(link_names)
    dup_joints = _duplicates(joint_names)
    if dup_links or dup_joints:
        d = ""
        if dup_links:  d += f"links: {dup_links}  "
        if dup_joints: d += f"joints: {dup_joints}"
        results.append(CheckResult(FAIL, "Duplicate names", d))
    else:
        results.append(CheckResult(PASS, "No duplicate link/joint names"))

    # 5. Kinematic chain connectivity
    _check_kinematic_chain(links, joints, results)

    # 6–10. Mass and inertia sanity
    _check_inertia(links, results)

    return _finalise(pkg_dir, urdf_path, results)


def validate_urdf(urdf_path: str) -> Tuple[bool, List[str]]:
    """
    Legacy API: validate a single URDF file (not a full package).
    Returns (is_valid, list_of_errors).
    """
    errors = []
    try:
        if HAS_LXML:
            tree = etree.parse(urdf_path)
            root = tree.getroot()
        else:
            root = etree.parse(urdf_path).getroot()
    except Exception as e:
        return False, [f"XML parse error: {e}"]

    if root.tag != 'robot':
        errors.append(f"Root element must be <robot>, got <{root.tag}>")

    links  = {el.get('name') for el in root.findall('link')}
    joints = root.findall('joint')

    if not links:
        errors.append("URDF has no <link> elements")

    for j in joints:
        jname = j.get('name', '<unnamed>')
        jtype = j.get('type', '')
        for role in ('parent', 'child'):
            el = j.find(role)
            if el is None:
                errors.append(f"Joint '{jname}' missing <{role}>")
            elif el.get('link') not in links:
                errors.append(f"Joint '{jname}' {role} '{el.get('link')}' not defined")
        if jtype in ('revolute', 'prismatic') and j.find('limit') is None:
            errors.append(f"Joint '{jname}' type '{jtype}' missing <limit>")

    for link in root.findall('link'):
        lname = link.get('name', '')
        if lname == 'world':
            continue
        inertial = link.find('inertial')
        if inertial is None:
            errors.append(f"Link '{lname}' missing <inertial>")
        else:
            mass_el = inertial.find('mass')
            if mass_el is not None:
                try:
                    m = float(mass_el.get('value', '0'))
                    if m <= 0:
                        errors.append(f"Link '{lname}' mass must be > 0 (got {m})")
                except ValueError:
                    errors.append(f"Link '{lname}' mass is not a number")

    return len(errors) == 0, errors


# ── internal helpers ─────────────────────────────────────────────────────────

def _resolve_uri(uri: str, pkg_name: str, pkg_dir: str) -> Optional[str]:
    """Resolve package://pkg_name/relative/path → absolute filesystem path."""
    m = re.match(r'^package://([^/]+)/(.+)$', uri)
    if not m:
        return None
    _pkg = m.group(1)   # should match pkg_name but we accept any
    rel  = m.group(2)
    return os.path.join(pkg_dir, rel.replace('/', os.sep))


def _duplicates(names: List[str]) -> List[str]:
    seen, dups = set(), []
    for n in names:
        if n in seen:
            dups.append(n)
        seen.add(n)
    return dups


def _check_kinematic_chain(links: dict, joints: dict,
                            results: List[CheckResult]):
    """BFS from the root link; any unreachable link → error."""
    children: Dict[str, List[str]] = defaultdict(list)
    has_parent: set = set()

    for j in joints.values():
        p = (j.find('parent') or _empty()).get('link', '')
        c = (j.find('child')  or _empty()).get('link', '')
        if p and c:
            children[p].append(c)
            has_parent.add(c)

    # Root = links that are never a child
    roots = [n for n in links if n not in has_parent and n != 'world']

    if not roots:
        results.append(CheckResult(WARN, "Kinematic chain",
                                   "No root link (all links have parents)"))
        return

    # BFS
    visited = {'world'}
    queue   = list(roots)
    while queue:
        node = queue.pop(0)
        if node in visited:
            continue
        visited.add(node)
        queue.extend(children.get(node, []))

    orphans = [n for n in links if n not in visited and n != 'world']
    if orphans:
        results.append(CheckResult(
            WARN, "Kinematic chain",
            f"{len(orphans)} orphan link(s): {orphans[:5]}"
            + (f" …+{len(orphans)-5}" if len(orphans) > 5 else "")
        ))
    else:
        results.append(CheckResult(
            PASS,
            f"Kinematic chain  ({len(links)-1} links reachable from root)"
        ))


def _check_inertia(links: dict, results: List[CheckResult]):
    """Check mass and inertia for all non-world links."""
    low_mass    = []
    zero_inert  = []
    tri_fail    = []
    not_pd      = []

    for lname, el in links.items():
        if lname == 'world':
            continue
        inertial = el.find('inertial')
        if inertial is None:
            continue

        # Mass
        mass_el = inertial.find('mass')
        if mass_el is not None:
            try:
                m = float(mass_el.get('value', '0'))
                if m < MIN_MASS_KG:
                    low_mass.append(f"{lname}: {m:.3e} kg")
            except ValueError:
                pass

        # Inertia
        inertia_el = inertial.find('inertia')
        if inertia_el is None:
            continue
        try:
            ixx = float(inertia_el.get('ixx', '0'))
            iyy = float(inertia_el.get('iyy', '0'))
            izz = float(inertia_el.get('izz', '0'))
            ixy = float(inertia_el.get('ixy', '0'))
            ixz = float(inertia_el.get('ixz', '0'))
            iyz = float(inertia_el.get('iyz', '0'))
        except ValueError:
            continue

        # Diagonal moments must be positive and ≥ MIN_INERTIA_KGM2
        if any(v <= MIN_INERTIA_KGM2 for v in (ixx, iyy, izz)):
            zero_inert.append(
                f"{lname}: ixx={ixx:.2e} iyy={iyy:.2e} izz={izz:.2e}"
            )

        # Triangle inequality (necessary condition for physical rigid body)
        if not (ixx + iyy >= izz and
                ixx + izz >= iyy and
                iyy + izz >= ixx):
            tri_fail.append(lname)

        # Positive definiteness via Sylvester's criterion
        if HAS_NUMPY:
            I = np.array([[ ixx, -ixy, -ixz],
                          [-ixy,  iyy, -iyz],
                          [-ixz, -iyz,  izz]])
            try:
                eigs = np.linalg.eigvalsh(I)
                if not np.all(eigs > 0):
                    not_pd.append(f"{lname}: eigenvalues={eigs}")
            except Exception:
                pass
        else:
            # Sylvester without numpy
            d1 = ixx
            d2 = ixx * iyy - ixy ** 2
            d3 = (ixx * (iyy * izz - iyz ** 2)
                  - ixy * (-ixy * izz - iyz * (-ixz))
                  + (-ixz) * ((-ixy)*(-iyz) - iyy*(-ixz)))
            if not (d1 > 0 and d2 > 0 and d3 > 0):
                not_pd.append(lname)

    if low_mass:
        results.append(CheckResult(
            WARN,
            f"Low-mass links  ({len(low_mass)} of {len(links)-1})",
            "Mass ≤ 1 g — likely clamped from surface model (no solid volume).\n"
            "       Fix: assign realistic mass manually, or check part is a solid.\n"
            "       " + "; ".join(low_mass[:5])
            + (f" …+{len(low_mass)-5}" if len(low_mass) > 5 else "")
        ))
    else:
        results.append(CheckResult(PASS, "Link masses  (all ≥ 1 g)"))

    if zero_inert:
        results.append(CheckResult(
            WARN,
            f"Tiny inertia  ({len(zero_inert)} links at minimum clamp ≤ 1e-8 kg·m²)",
            "Gazebo may become unstable. Cause: part has no solid volume.\n"
            "       Workaround: in Gazebo, add <mu1>/<mu2> and set a realistic inertia\n"
            "       manually in the URDF, or re-model the parts as solids.\n"
            "       " + "; ".join(zero_inert[:3])
            + (f" …+{len(zero_inert)-3}" if len(zero_inert) > 3 else "")
        ))
    else:
        results.append(CheckResult(PASS, "Inertia magnitudes  (all > 1e-8 kg·m²)"))

    if tri_fail:
        results.append(CheckResult(
            FAIL,
            f"Inertia triangle inequality failed  ({len(tri_fail)} links)",
            "; ".join(tri_fail[:5])
        ))
    else:
        results.append(CheckResult(PASS, "Inertia triangle inequality"))

    if not_pd:
        results.append(CheckResult(
            FAIL,
            f"Non-positive-definite inertia  ({len(not_pd)} links)",
            "; ".join(str(x).split(":")[0] for x in not_pd[:5])
        ))
    else:
        results.append(CheckResult(PASS, "Inertia positive-definite"))


class _empty:
    """Dummy element for safe attribute access."""
    def get(self, *a, **kw): return ''


def _finalise(pkg_dir, urdf_path, results) -> Dict:
    n_pass = sum(1 for r in results if r.is_pass)
    n_warn = sum(1 for r in results if r.is_warn)
    n_fail = sum(1 for r in results if r.is_fail)

    lines = [
        f"Package : {pkg_dir}",
        f"URDF    : {urdf_path or 'not found'}",
        "",
    ]
    for r in results:
        lines.append(str(r))
    lines += [
        "",
        "─" * 56,
        f"  {n_pass} passed   {n_warn} warning(s)   {n_fail} failure(s)",
    ]
    if n_fail == 0 and n_warn == 0:
        lines.append("  ✓ Package is ready for ROS 2 / Gazebo")
    elif n_fail == 0:
        lines.append("  ✓ No hard errors — review warnings before simulation")
    else:
        lines.append("  ✗ Fix failures before loading in ROS 2")

    return {
        'pkg_dir':   pkg_dir,
        'urdf_path': urdf_path,
        'results':   results,
        'n_pass':    n_pass,
        'n_warn':    n_warn,
        'n_fail':    n_fail,
        'ok':        n_fail == 0,
        'report':    "\n".join(lines),
    }
