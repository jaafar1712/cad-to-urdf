import sys, os
sys.path.insert(0, '.')
from core.step_reader import StepReader
from core.topology_explorer import TopologyExplorer
from core.joint_detector import JointDetector
from core.inertia_calculator import InertiaCalculator
from core.urdf_generator import URDFGenerator
from utils.urdf_validator import validate_urdf

reader = StepReader()
reader.load('test_arm.step')
parts = reader.get_parts()

explorer  = TopologyExplorer()
detector  = JointDetector()
calc      = InertiaCalculator()
gen       = URDFGenerator()

topos  = [explorer.analyze_shape(p['shape']) for p in parts]
joints = detector.detect_all_joints(parts, topos)

# Build link data
links = []
for p in parts:
    inertia = calc.calculate(p['shape'])
    link = {'name': p['name']}
    link.update(inertia)
    links.append(link)

# Build joint data
joint_dicts = [j.to_dict() for j in joints]

os.makedirs('test_output/urdf', exist_ok=True)
out = 'test_output/urdf/test_arm.urdf'
gen.generate(links, joint_dicts, 'test_arm', out)

# Validate
valid, errors = validate_urdf(out)
print(f'\nURDF valid: {valid}')
for e in errors:
    print(f'  ERROR: {e}')
assert valid, f"URDF validation failed: {errors}"

# Show URDF content
with open(out) as f:
    print(f.read())
print('urdf_generator OK')
