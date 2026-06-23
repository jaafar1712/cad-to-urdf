"""
Generate a simple 2-link arm STEP file for testing the full pipeline.
Link 1: a box (base), Link 2: a cylinder (arm) on top.
They share a collinear cylinder axis — should detect as REVOLUTE joint.
"""
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeBox
from OCC.Core.gp import gp_Ax2, gp_Pnt, gp_Dir, gp_Trsf, gp_Vec
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCC.Core.STEPControl import STEPControl_Writer, STEPControl_AsIs
from OCC.Core.IFSelect import IFSelect_RetDone
import os


def create_test_step(output_path: str = "test_arm.step"):
    """
    Creates a STEP file with two shapes:
    - A box 100×100×50 mm at origin (base link)
    - A cylinder radius=20mm, height=150mm centered on top of the box
      sharing the same Z-axis (for revolute joint detection)
    """
    # Base box: 100 x 100 x 50 mm
    base_box = BRepPrimAPI_MakeBox(100.0, 100.0, 50.0).Shape()

    # Arm cylinder: radius=20mm, height=150mm
    # Place it centered on top of the base (x=50, y=50, z=50)
    arm_axis = gp_Ax2(gp_Pnt(50.0, 50.0, 50.0), gp_Dir(0.0, 0.0, 1.0))
    arm_cyl = BRepPrimAPI_MakeCylinder(arm_axis, 20.0, 150.0).Shape()

    # Write STEP with both shapes as separate entities
    writer = STEPControl_Writer()
    writer.Transfer(base_box, STEPControl_AsIs)
    writer.Transfer(arm_cyl, STEPControl_AsIs)
    status = writer.Write(output_path)

    if status == IFSelect_RetDone:
        print(f"[OK] Test STEP file created: {os.path.abspath(output_path)}")
        return output_path
    else:
        raise RuntimeError("Failed to write STEP file")


if __name__ == "__main__":
    create_test_step()
