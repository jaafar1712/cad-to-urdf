import sys
sys.path.insert(0, '.')
from core.step_reader import StepReader

reader = StepReader()
reader.load('test_arm.step')
parts = reader.get_parts()
print(f'Parts found: {len(parts)}')
for p in parts:
    print(f'  [{p["index"]}] name={p["name"]} parent={p["parent"]}')
print('step_reader OK')
