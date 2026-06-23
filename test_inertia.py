import sys
sys.path.insert(0, '.')
from core.step_reader import StepReader
from core.inertia_calculator import InertiaCalculator
import numpy as np

reader = StepReader()
reader.load('test_arm.step')
parts = reader.get_parts()

calc = InertiaCalculator()

for p in parts:
    result = calc.calculate(p['shape'], material='steel')
    print(f"\nPart '{p['name']}' (steel):")
    print(f"  mass          = {result['mass']:.4f} kg")
    print(f"  CoM (m)       = {tuple(round(v,4) for v in result['center_of_mass'])}")
    print(f"  ixx={result['ixx']:.3e}  iyy={result['iyy']:.3e}  izz={result['izz']:.3e}")
    print(f"  positive def  = {calc.validate_positive_definite(result)}")

    # Sanity checks
    assert result['mass'] > 0, "Mass must be > 0"
    assert result['ixx'] > 0, "ixx must be > 0"
    assert result['iyy'] > 0, "iyy must be > 0"
    assert result['izz'] > 0, "izz must be > 0"
    assert calc.validate_positive_definite(result), "Inertia must be positive definite"

print('\ninertia_calculator OK')
