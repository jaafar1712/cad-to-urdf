import sys
sys.path.insert(0, '.')
from core.step_reader import StepReader
from core.topology_explorer import TopologyExplorer
from core.joint_detector import JointDetector, JointType

reader = StepReader()
reader.load('test_arm.step')
parts = reader.get_parts()

explorer = TopologyExplorer()
topos = [explorer.analyze_shape(p['shape']) for p in parts]

detector = JointDetector()
joints = detector.detect_all_joints(parts, topos)

print(f"\nJoints detected: {len(joints)}")
for j in joints:
    print(f"  {j.parent_link} -> {j.child_link}")
    print(f"    type       = {j.joint_type.value}")
    print(f"    confidence = {j.confidence:.2f}")
    print(f"    origin_xyz = {tuple(round(v,4) for v in j.origin_xyz)}")
    print(f"    axis_xyz   = {tuple(round(v,4) for v in j.axis_xyz)}")
    print(f"    evidence   = {j.evidence}")

# Validate
assert len(joints) == 1, f"Expected 1 joint, got {len(joints)}"
j = joints[0]
# part_0 is a box (no cylinder), part_1 is a cylinder
# box has no cylinder → expected result depends on topology
if j.joint_type == JointType.REVOLUTE:
    print("\nExpected REVOLUTE detected!")
elif j.joint_type == JointType.FIXED:
    print("\nFIXED detected (box has no cylinder face — correct fallback)")
else:
    print(f"\nGot {j.joint_type.value}")
print('joint_detector OK')
