"""
Full end-to-end pipeline test (no GUI).
Simulates what the application does when the user clicks Export.
"""
import sys, os, shutil
sys.path.insert(0, '.')

OUTPUT_DIR = 'test_output/ros_packages'

def run():
    print("=== CAD2URDF Full Pipeline Test ===\n")

    # 1. Generate test STEP file
    from test_generator import create_test_step
    step_path = 'test_arm.step'
    if not os.path.exists(step_path):
        create_test_step(step_path)
    print(f"[1] STEP file: {os.path.abspath(step_path)}")

    # 2. Read STEP
    from core.step_reader import StepReader
    reader = StepReader()
    reader.load(step_path)
    parts = reader.get_parts()
    print(f"[2] Parts loaded: {len(parts)}")
    assert len(parts) == 2, f"Expected 2 parts, got {len(parts)}"
    for p in parts:
        print(f"    - {p['name']} (parent={p['parent']})")

    # 3. Topology analysis
    from core.topology_explorer import TopologyExplorer
    explorer = TopologyExplorer()
    topos = [explorer.analyze_shape(p['shape']) for p in parts]
    print(f"[3] Topology: part_0 has {len(topos[0]['cylindrical_faces'])} cyl faces, "
          f"part_1 has {len(topos[1]['cylindrical_faces'])} cyl faces")

    # 4. Joint detection
    from core.joint_detector import JointDetector, JointType
    detector = JointDetector()
    joints = detector.detect_all_joints(parts, topos)
    print(f"[4] Joints: {len(joints)}")
    for j in joints:
        print(f"    * {j.parent_link}->{j.child_link}  [{j.joint_type.value}]  conf={j.confidence:.2f}")
    assert len(joints) == 1

    # 5. Inertia calculation
    from core.inertia_calculator import InertiaCalculator
    calc = InertiaCalculator()
    links = []
    for p in parts:
        inertia = calc.calculate(p['shape'])
        link = {'name': p['name']}
        link.update(inertia)
        links.append(link)
        print(f"[5] {p['name']}: mass={inertia['mass']:.3f}kg  "
              f"ixx={inertia['ixx']:.2e}  izz={inertia['izz']:.2e}")
    assert all(l['mass'] > 0 for l in links), "All masses must be > 0"

    # 6. Mesh export
    from core.mesh_exporter import MeshExporter
    exporter = MeshExporter()
    vis_dir  = 'test_output/meshes/visual'
    col_dir  = 'test_output/meshes/collision'
    os.makedirs(vis_dir, exist_ok=True)
    os.makedirs(col_dir, exist_ok=True)

    visual_paths    = []
    collision_paths = []
    for p in parts:
        dae = os.path.join(vis_dir, f"{p['name']}.dae")
        stl = os.path.join(col_dir, f"{p['name']}.stl")
        exporter.export_visual_dae(p['shape'], dae)
        exporter.export_collision_stl(p['shape'], stl)
        visual_paths.append(dae)
        collision_paths.append(stl)
        print(f"[6] {p['name']}: DAE={os.path.getsize(dae)//1024}KB  "
              f"STL={os.path.getsize(stl)//1024}KB")

    # 7. URDF generation
    from core.urdf_generator import URDFGenerator
    gen = URDFGenerator()
    urdf_path = 'test_output/test_arm.urdf'
    os.makedirs(os.path.dirname(urdf_path), exist_ok=True)
    joint_dicts = [j.to_dict() for j in joints]
    gen.generate(links, joint_dicts, 'test_arm', urdf_path)
    print(f"[7] URDF: {urdf_path}  ({os.path.getsize(urdf_path)} bytes)")

    # 8. URDF validation
    from utils.urdf_validator import validate_urdf
    valid, errors = validate_urdf(urdf_path)
    print(f"[8] URDF valid: {valid}")
    if errors:
        for e in errors:
            print(f"    ERROR: {e}")
    assert valid, f"URDF validation failed: {errors}"

    # 9. ROS 2 package build
    from core.ros_package_builder import ROSPackageBuilder
    builder = ROSPackageBuilder()
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    pkg_dir = builder.build(
        'test_arm',
        OUTPUT_DIR,
        urdf_path,
        visual_paths,
        collision_paths,
    )
    print(f"[9] ROS 2 package: {pkg_dir}")

    # Verify package structure
    expected = [
        'package.xml',
        'CMakeLists.txt',
        'urdf/test_arm.urdf',
        'launch/display.launch.py',
        'launch/gazebo.launch.py',
        'config/controllers.yaml',
        'worlds/empty.world',
    ]
    for f in expected:
        path = os.path.join(pkg_dir, f)
        assert os.path.exists(path), f"Missing: {f}"
        print(f"    OK {f}  ({os.path.getsize(path)} bytes)")

    print("\n=== ALL TESTS PASSED ===")
    return pkg_dir


if __name__ == '__main__':
    run()
