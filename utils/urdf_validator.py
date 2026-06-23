from lxml import etree
from utils.logger import get_logger

log = get_logger(__name__)


def validate_urdf(urdf_path: str) -> tuple[bool, list[str]]:
    """
    Basic structural validation of a URDF file.
    Returns (is_valid, list_of_errors).
    """
    errors = []
    try:
        tree = etree.parse(urdf_path)
        root = tree.getroot()
    except etree.XMLSyntaxError as e:
        return False, [f"XML syntax error: {e}"]

    if root.tag != "robot":
        errors.append(f"Root element must be <robot>, got <{root.tag}>")

    links = {el.get("name") for el in root.findall("link")}
    joints = root.findall("joint")

    if not links:
        errors.append("URDF has no <link> elements")

    for j in joints:
        jname = j.get("name", "<unnamed>")
        jtype = j.get("type", "")

        parent_el = j.find("parent")
        child_el  = j.find("child")

        if parent_el is None:
            errors.append(f"Joint '{jname}' missing <parent>")
        elif parent_el.get("link") not in links:
            errors.append(f"Joint '{jname}' parent link '{parent_el.get('link')}' not defined")

        if child_el is None:
            errors.append(f"Joint '{jname}' missing <child>")
        elif child_el.get("link") not in links:
            errors.append(f"Joint '{jname}' child link '{child_el.get('link')}' not defined")

        if jtype in ("revolute", "prismatic") and j.find("limit") is None:
            errors.append(f"Joint '{jname}' type '{jtype}' missing <limit>")

    # Check inertia for non-world links
    for link in root.findall("link"):
        lname = link.get("name", "")
        if lname == "world":
            continue
        inertial = link.find("inertial")
        if inertial is None:
            errors.append(f"Link '{lname}' missing <inertial>")
        else:
            mass_el = inertial.find("mass")
            if mass_el is not None:
                try:
                    m = float(mass_el.get("value", "0"))
                    if m <= 0:
                        errors.append(f"Link '{lname}' mass must be > 0 (got {m})")
                except ValueError:
                    errors.append(f"Link '{lname}' mass value is not a number")

    is_valid = len(errors) == 0
    if is_valid:
        log.info(f"URDF validation PASSED: {urdf_path}")
    else:
        for e in errors:
            log.warning(f"URDF validation error: {e}")
    return is_valid, errors
