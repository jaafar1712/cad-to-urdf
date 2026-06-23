"""
Calculate mass, center of mass, and 3×3 inertia tensor from BRep geometry.
Uses pythonocc GProp volume integration.

UNIT NOTE: STEP files are typically in millimeters.
OCC volume properties are in the same units as the geometry (mm³, mm⁵, etc.).
All outputs are converted to SI (kg, m, kg·m²).
"""
import numpy as np
from typing import Dict

from OCC.Core.GProp import GProp_GProps
from OCC.Core.BRepGProp import brepgprop

from utils.logger import get_logger

log = get_logger(__name__)


MATERIAL_DENSITIES: Dict[str, float] = {
    'steel':        7850.0,
    'aluminum':     2700.0,
    'abs_plastic':  1050.0,
    'titanium':     4500.0,
    'carbon_fiber': 1600.0,
    'brass':        8500.0,
    'pla':           1250.0,
}

MIN_MASS    = 1e-3    # 1 gram minimum
MIN_INERTIA = 1e-9   # kg·m²


class InertiaCalculator:

    def calculate(self, shape, material: str = 'steel') -> Dict:
        """
        Returns dict with mass, CoM, and inertia components in SI units.

        Keys: mass, center_of_mass, ixx, iyy, izz, ixy, ixz, iyz
        """
        density_kg_m3 = MATERIAL_DENSITIES.get(material, 7850.0)
        density_kg_mm3 = density_kg_m3 * 1e-9   # kg/mm³

        props = GProp_GProps()
        try:
            # Compute volume properties (density=1 → "mass" = volume in mm³)
            brepgprop.VolumeProperties(shape, props, 1e-5)
        except Exception as e:
            log.warning(f"VolumeProperties failed: {e} — using surface fallback")
            try:
                brepgprop.SurfaceProperties(shape, props)
            except Exception as e2:
                log.error(f"SurfaceProperties also failed: {e2}")
                return self._fallback_inertia(material)

        volume_mm3 = props.Mass()   # density=1 → Mass() == volume in mm³
        mass_kg    = volume_mm3 * density_kg_mm3

        if mass_kg < MIN_MASS:
            log.warning(f"Computed mass {mass_kg:.2e} kg too small — clamping to {MIN_MASS} kg")
            mass_kg = MIN_MASS

        # Center of mass (mm → m)
        com = props.CentreOfMass()
        com_m = (com.X() * 0.001, com.Y() * 0.001, com.Z() * 0.001)

        # Inertia matrix
        # OCC returns matrix components in units of [density * length^5].
        # With density=1 and geometry in mm: units = mm^5.
        # To get kg·m²: multiply by (density_kg/mm³) * (mm→m)^5
        #   = density_kg_mm3 * (0.001)^5 = density_kg_mm3 * 1e-15
        # But (0.001)^5 = 1e-15 and density_kg_mm3 = density_kg_m3 * 1e-9,
        # so scale = density_kg_m3 * 1e-9 * 1e-15 = density_kg_m3 * 1e-24 ...
        #
        # Simpler rederivation:
        #   I_SI [kg·m²] = I_OCC [mm^5] * density [kg/mm³] * (mm/m)^2
        #                = I_OCC * density_kg_mm3 * (0.001)^2
        # This is because:
        #   I = ∫ r² ρ dV   (r in m, ρ in kg/m³, dV in m³)
        #   OCC computes with density=1, r in mm, dV in mm³: I_OCC = ∫ r_mm² dV_mm
        #   Convert: r_mm² = r_m² / (0.001)²,  dV_mm = dV_m / (0.001)³
        #   → I_OCC = ∫ r_m² / 1e-6 * dV_m / 1e-9 * (1/density_occ) ... complex
        #
        # Practical formula verified against known results:
        #   scale = density_kg_m3 * 1e-9 * (0.001)^2 = density_kg_m3 * 1e-15
        # This matches: volume_m3 = volume_mm3 * 1e-9,
        #               I_characteristic = mass * r_m² = (vol_m3 * density) * r_m²
        scale = density_kg_mm3 * (0.001 ** 2)

        mat = props.MatrixOfInertia()

        # OCC uses positive sign for off-diagonal; URDF convention uses negative
        ixx = mat.Value(1, 1) * scale
        iyy = mat.Value(2, 2) * scale
        izz = mat.Value(3, 3) * scale
        ixy = -mat.Value(1, 2) * scale
        ixz = -mat.Value(1, 3) * scale
        iyz = -mat.Value(2, 3) * scale

        # Clamp principal moments to physical minimum (must be > 0)
        ixx = max(abs(ixx), MIN_INERTIA)
        iyy = max(abs(iyy), MIN_INERTIA)
        izz = max(abs(izz), MIN_INERTIA)

        result = {
            'mass':           mass_kg,
            'center_of_mass': com_m,
            'ixx': ixx, 'iyy': iyy, 'izz': izz,
            'ixy': ixy, 'ixz': ixz, 'iyz': iyz,
        }
        log.debug(
            f"Inertia: mass={mass_kg:.4f}kg  "
            f"CoM=({com_m[0]:.4f},{com_m[1]:.4f},{com_m[2]:.4f})m  "
            f"ixx={ixx:.2e}  iyy={iyy:.2e}  izz={izz:.2e}"
        )
        return result

    def _fallback_inertia(self, material: str) -> Dict:
        """Return a minimal valid inertia dict when geometry fails."""
        return {
            'mass':           0.1,
            'center_of_mass': (0.0, 0.0, 0.0),
            'ixx': 1e-4, 'iyy': 1e-4, 'izz': 1e-4,
            'ixy': 0.0,  'ixz': 0.0,  'iyz': 0.0,
        }

    def validate_positive_definite(self, result: Dict) -> bool:
        """Check whether the 3×3 inertia matrix is positive definite."""
        I = np.array([
            [result['ixx'], -result['ixy'], -result['ixz']],
            [-result['ixy'],  result['iyy'], -result['iyz']],
            [-result['ixz'], -result['iyz'],  result['izz']],
        ])
        try:
            eigenvalues = np.linalg.eigvalsh(I)
            return bool(np.all(eigenvalues > 0))
        except Exception:
            return False
