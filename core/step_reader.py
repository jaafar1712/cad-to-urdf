"""
STEP / IGES file reader using pythonocc XDE (XCAFDoc) framework.
Preserves part names, assembly hierarchy, and transformation matrices.
"""
import os
import re
from typing import List, Dict, Optional

from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.XCAFDoc import XCAFDoc_DocumentTool
from OCC.Core.XCAFApp import XCAFApp_Application
from OCC.Core.TDocStd import TDocStd_Document
from OCC.Core.TDF import TDF_LabelSequence, TDF_AttributeIterator
from OCC.Core.TDataStd import TDataStd_Name
from OCC.Core.TopLoc import TopLoc_Location
from OCC.Core.gp import gp_Trsf
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCC.Core.BRepBndLib import brepbndlib_Add
from OCC.Core.Bnd import Bnd_Box

from utils.logger import get_logger

log = get_logger(__name__)


class StepReader:

    def __init__(self):
        self.parts: List[Dict] = []
        self._app = XCAFApp_Application.GetApplication()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, filepath: str) -> bool:
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        ext = os.path.splitext(filepath)[1].lower()
        if ext not in (".step", ".stp", ".iges", ".igs"):
            raise ValueError(f"Unsupported file extension: {ext}")

        self.parts = []

        # Use plain strings — required in pythonocc 7.7.2 (not TCollection_ExtendedString)
        doc = TDocStd_Document("XmlXCAF")
        self._app.NewDocument("XmlXCAF", doc)

        reader = STEPCAFControl_Reader()
        reader.SetNameMode(True)
        reader.SetColorMode(True)
        reader.SetLayerMode(True)

        status = reader.ReadFile(filepath)
        if status != IFSelect_RetDone:
            raise ValueError(f"Cannot read file: {filepath}")

        reader.Transfer(doc)

        shape_tool = XCAFDoc_DocumentTool.ShapeTool(doc.Main())

        free_shapes = TDF_LabelSequence()
        shape_tool.GetFreeShapes(free_shapes)

        log.info(f"Loaded '{filepath}' — {free_shapes.Length()} top-level shape(s)")

        identity_loc = TopLoc_Location()
        self._walk_assembly(shape_tool, free_shapes,
                            parent_name=None, parent_loc=identity_loc)

        if not self.parts:
            raise ValueError("No solid parts found in file")

        log.info(f"Extracted {len(self.parts)} part(s)")
        return True

    def get_parts(self) -> List[Dict]:
        return self.parts

    def get_part_count(self) -> int:
        return len(self.parts)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _walk_assembly(self, shape_tool, labels: TDF_LabelSequence,
                       parent_name: Optional[str], parent_loc: TopLoc_Location):
        for i in range(1, labels.Length() + 1):
            label = labels.Value(i)
            name = self._get_name(label) or f"part_{len(self.parts)}"

            # Get this component's location and compose with parent
            comp_loc = shape_tool.GetLocation(label)
            combined_loc = parent_loc.Multiplied(comp_loc)

            if shape_tool.IsAssembly(label):
                children = TDF_LabelSequence()
                shape_tool.GetComponents(label, children, False)
                log.debug(f"  Assembly: '{name}' — {children.Length()} child(ren)")
                self._walk_assembly(shape_tool, children, name, combined_loc)

            elif shape_tool.IsSimpleShape(label):
                raw_shape = shape_tool.GetShape(label)
                placed_shape = self._apply_location(raw_shape, combined_loc)
                self.parts.append({
                    'name': name,
                    'shape': placed_shape,
                    'raw_shape': raw_shape,
                    'location': combined_loc,
                    'transform': combined_loc.IsIdentity() and None or combined_loc.Transformation(),
                    'parent': parent_name,
                    'label': label,
                    'index': len(self.parts),
                })
                log.debug(f"  Part: '{name}' (parent='{parent_name}')")

            elif shape_tool.IsReference(label):
                # Reference to a definition — get children or treat as simple shape
                referred = TDF_LabelSequence()
                shape_tool.GetComponents(label, referred, False)
                if referred.Length() > 0:
                    self._walk_assembly(shape_tool, referred, parent_name, combined_loc)
                else:
                    raw_shape = shape_tool.GetShape(label)
                    placed_shape = self._apply_location(raw_shape, combined_loc)
                    self.parts.append({
                        'name': name,
                        'shape': placed_shape,
                        'raw_shape': raw_shape,
                        'location': combined_loc,
                        'transform': None,
                        'parent': parent_name,
                        'label': label,
                        'index': len(self.parts),
                    })

    def _apply_location(self, shape, loc: TopLoc_Location):
        """Apply a TopLoc_Location to a shape, returning the placed copy."""
        if loc.IsIdentity():
            return shape
        try:
            trsf = loc.Transformation()
            builder = BRepBuilderAPI_Transform(shape, trsf, True)
            if builder.IsDone():
                return builder.Shape()
        except Exception as e:
            log.warning(f"Could not apply location transform: {e}")
        return shape

    def _get_name(self, label) -> str:
        """
        Extract part name from XDE label.
        In pythonocc 7.7.2, TDataStd_Name.Get() is not exposed in Python;
        we parse the name from DumpToString() instead.
        """
        it = TDF_AttributeIterator(label)
        while it.More():
            attr = it.Value()
            if attr.DynamicType().Name() == "TDataStd_Name":
                try:
                    name_attr = TDataStd_Name.DownCast(attr)
                    dump = name_attr.DumpToString()
                    # Format: "...Name=|actual_name|..."
                    m = re.search(r"Name=\|([^|]+)\|", dump)
                    if m:
                        name = m.group(1).strip()
                        # Filter out OCC internal names
                        if name and not name.startswith("Open CASCADE"):
                            return name
                except Exception:
                    pass
            it.Next()
        return ""

    def get_bounding_box(self, shape) -> Dict:
        box = Bnd_Box()
        brepbndlib_Add(shape, box)
        xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
        return {
            'min':  (xmin * 0.001, ymin * 0.001, zmin * 0.001),
            'max':  (xmax * 0.001, ymax * 0.001, zmax * 0.001),
            'size': ((xmax - xmin) * 0.001,
                     (ymax - ymin) * 0.001,
                     (zmax - zmin) * 0.001),
        }
