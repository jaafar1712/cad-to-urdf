"""
Explores BRep topology of each part shape.
Classifies faces by surface type (cylindrical, planar, etc.)
to provide the geometric evidence needed for joint detection.
"""
from typing import Dict, List

from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.GeomAbs import (GeomAbs_Cylinder, GeomAbs_Plane,
                               GeomAbs_Cone, GeomAbs_Sphere, GeomAbs_Torus)
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.TopoDS import topods
from OCC.Core.GProp import GProp_GProps
from OCC.Core.BRepGProp import brepgprop
brepgprop_SurfaceProperties = brepgprop.SurfaceProperties

from utils.logger import get_logger

log = get_logger(__name__)


class TopologyExplorer:

    def analyze_shape(self, shape) -> Dict:
        """
        Walk all faces of a BRep shape and classify by surface type.

        Returns:
            {
              'cylindrical_faces': [{axis_point, axis_dir, radius, face}],
              'planar_faces':      [{origin, normal, area, face}],
              'conical_faces':     [{apex, axis_dir, half_angle, face}],
              'face_count':        int,
            }
        """
        result: Dict = {
            'cylindrical_faces': [],
            'planar_faces': [],
            'conical_faces': [],
            'face_count': 0,
        }

        if shape is None:
            return result

        explorer = TopExp_Explorer(shape, TopAbs_FACE)
        while explorer.More():
            try:
                face = topods.Face(explorer.Current())
                result['face_count'] += 1
                self._classify_face(face, result)
            except Exception as e:
                log.warning(f"Skipping face due to error: {e}")
            explorer.Next()

        log.debug(
            f"Analyzed shape: {result['face_count']} faces, "
            f"{len(result['cylindrical_faces'])} cylindrical, "
            f"{len(result['planar_faces'])} planar"
        )
        return result

    # ------------------------------------------------------------------

    def _classify_face(self, face, result: Dict):
        adaptor = BRepAdaptor_Surface(face)
        surf_type = adaptor.GetType()

        if surf_type == GeomAbs_Cylinder:
            cyl = adaptor.Cylinder()
            axis = cyl.Axis()
            result['cylindrical_faces'].append({
                'axis_point': axis.Location(),   # gp_Pnt
                'axis_dir':   axis.Direction(),  # gp_Dir
                'radius':     cyl.Radius(),      # mm
                'face':       face,
            })

        elif surf_type == GeomAbs_Plane:
            plane = adaptor.Plane()
            try:
                props = GProp_GProps()
                brepgprop_SurfaceProperties(face, props)
                area = props.Mass()
            except Exception:
                area = 0.0
            result['planar_faces'].append({
                'origin': plane.Location(),
                'normal': plane.Axis().Direction(),
                'area':   area,   # mm²
                'face':   face,
            })

        elif surf_type == GeomAbs_Cone:
            cone = adaptor.Cone()
            axis = cone.Axis()
            result['conical_faces'].append({
                'apex':       cone.Apex(),
                'axis_dir':   axis.Direction(),
                'half_angle': cone.SemiAngle(),  # radians
                'face':       face,
            })

    def get_cylinder_summary(self, topo: Dict) -> List[Dict]:
        """Return cylindrical faces sorted by radius (largest first)."""
        return sorted(topo['cylindrical_faces'],
                      key=lambda c: c['radius'], reverse=True)

    def get_largest_planar_face(self, topo: Dict):
        """Return the planar face with the greatest area, or None."""
        planes = topo['planar_faces']
        if not planes:
            return None
        return max(planes, key=lambda p: p['area'])
