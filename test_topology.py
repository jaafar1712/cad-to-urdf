import sys
sys.path.insert(0, '.')
from core.step_reader import StepReader
from core.topology_explorer import TopologyExplorer

reader = StepReader()
reader.load('test_arm.step')
parts = reader.get_parts()

explorer = TopologyExplorer()
for p in parts:
    topo = explorer.analyze_shape(p['shape'])
    print(f"\nPart '{p['name']}':")
    print(f"  Faces: {topo['face_count']}")
    print(f"  Cylindrical: {len(topo['cylindrical_faces'])}")
    for c in topo['cylindrical_faces']:
        pt = c['axis_point']
        d  = c['axis_dir']
        print(f"    cyl: r={c['radius']:.2f}mm  axis_pt=({pt.X():.1f},{pt.Y():.1f},{pt.Z():.1f})  dir=({d.X():.2f},{d.Y():.2f},{d.Z():.2f})")
    print(f"  Planar: {len(topo['planar_faces'])}")

print('\ntopology_explorer OK')
