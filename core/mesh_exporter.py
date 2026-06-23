"""
Tessellate BRep shapes and export:
  - Visual mesh: DAE (Collada) — high detail, suitable for RViz rendering
  - Collision mesh: STL (binary) — simplified for physics engine
All output meshes use SI units (meters).
"""
import os
import numpy as np
import trimesh

from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.BRep import BRep_Tool
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.TopoDS import topods

from utils.logger import get_logger

log = get_logger(__name__)


class MeshExporter:

    # Tessellation quality settings
    VISUAL_LINEAR_DEFLECTION   = 0.01    # mm (finer = more triangles)
    VISUAL_ANGULAR_DEFLECTION  = 0.1    # radians
    COLLISION_LINEAR_DEFLECTION  = 0.1   # mm (coarser for physics)
    COLLISION_ANGULAR_DEFLECTION = 0.5   # radians
    COLLISION_MAX_FACES          = 3000  # target face count after decimation

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def export_visual_dae(self, shape, output_path: str) -> str:
        """
        Tessellate the BRep shape and export as Collada (.dae).
        Geometry is converted from mm → m.
        """
        mesh = self._tessellate(
            shape,
            self.VISUAL_LINEAR_DEFLECTION,
            self.VISUAL_ANGULAR_DEFLECTION,
        )
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        mesh.export(output_path)
        log.info(
            f"Visual DAE: {len(mesh.faces)} faces → {output_path}"
        )
        return output_path

    def export_collision_stl(self, shape, output_path: str) -> str:
        """
        Tessellate (coarse) and export as binary STL.
        Simplifies with quadric decimation if face count exceeds limit.
        """
        mesh = self._tessellate(
            shape,
            self.COLLISION_LINEAR_DEFLECTION,
            self.COLLISION_ANGULAR_DEFLECTION,
        )

        if len(mesh.faces) > self.COLLISION_MAX_FACES:
            original = len(mesh.faces)
            mesh = mesh.simplify_quadric_decimation(self.COLLISION_MAX_FACES)
            log.debug(f"Decimated {original} → {len(mesh.faces)} faces")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        mesh.export(output_path, file_type='stl')
        log.info(
            f"Collision STL: {len(mesh.faces)} faces → {output_path}"
        )
        return output_path

    # ------------------------------------------------------------------
    # Tessellation helper
    # ------------------------------------------------------------------

    def _tessellate(self, shape, linear_deflection: float,
                    angular_deflection: float) -> trimesh.Trimesh:
        """
        Convert BRep shape to triangle mesh.
        Returns a trimesh.Trimesh in meters.
        """
        # Trigger OCC tessellation
        mesh_gen = BRepMesh_IncrementalMesh(
            shape,
            linear_deflection,
            False,
            angular_deflection,
        )
        mesh_gen.Perform()

        vertices = []
        triangles = []
        vertex_offset = 0

        explorer = TopExp_Explorer(shape, TopAbs_FACE)
        while explorer.More():
            try:
                face = topods.Face(explorer.Current())
                location = face.Location()
                triangulation = BRep_Tool.Triangulation(face, location)

                if triangulation is None:
                    explorer.Next()
                    continue

                # Get location transform (if not identity)
                trsf = None
                if not location.IsIdentity():
                    try:
                        trsf = location.Transformation()
                    except Exception:
                        trsf = None

                # Collect vertices
                n_nodes = triangulation.NbNodes()
                for i in range(1, n_nodes + 1):
                    node = triangulation.Node(i)
                    if trsf is not None:
                        try:
                            node.Transform(trsf)
                        except Exception:
                            pass
                    vertices.append([
                        node.X() * 0.001,   # mm → m
                        node.Y() * 0.001,
                        node.Z() * 0.001,
                    ])

                # Collect triangles
                n_tris = triangulation.NbTriangles()
                for i in range(1, n_tris + 1):
                    tri = triangulation.Triangle(i)
                    n1, n2, n3 = tri.Get()
                    triangles.append([
                        n1 - 1 + vertex_offset,
                        n2 - 1 + vertex_offset,
                        n3 - 1 + vertex_offset,
                    ])

                vertex_offset += n_nodes

            except Exception as e:
                log.warning(f"Skipping face during tessellation: {e}")

            explorer.Next()

        if not vertices:
            log.warning("No vertices collected — returning empty mesh")
            return trimesh.Trimesh()

        mesh = trimesh.Trimesh(
            vertices=np.array(vertices, dtype=np.float64),
            faces=np.array(triangles, dtype=np.int64),
            process=True,
        )
        mesh.fix_normals()
        mesh.remove_duplicate_faces()
        mesh.remove_unreferenced_vertices()

        return mesh
