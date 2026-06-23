import sys, os
sys.path.insert(0, '.')
from core.step_reader import StepReader
from core.mesh_exporter import MeshExporter
import trimesh

os.makedirs('test_output/meshes/visual',    exist_ok=True)
os.makedirs('test_output/meshes/collision', exist_ok=True)

reader = StepReader()
reader.load('test_arm.step')
parts = reader.get_parts()

exporter = MeshExporter()

for p in parts:
    name = p['name']
    dae_path = f'test_output/meshes/visual/{name}.dae'
    stl_path = f'test_output/meshes/collision/{name}.stl'

    exporter.export_visual_dae(p['shape'], dae_path)
    exporter.export_collision_stl(p['shape'], stl_path)

    # Verify files exist and are non-empty
    assert os.path.exists(dae_path) and os.path.getsize(dae_path) > 100, f"DAE missing: {dae_path}"
    assert os.path.exists(stl_path) and os.path.getsize(stl_path) > 100, f"STL missing: {stl_path}"

    # Verify STL is loadable
    m = trimesh.load(stl_path)
    print(f"  {name}: DAE {os.path.getsize(dae_path)//1024}KB, STL {os.path.getsize(stl_path)//1024}KB, stl_faces={len(m.faces)}")

print('\nmesh_exporter OK')
