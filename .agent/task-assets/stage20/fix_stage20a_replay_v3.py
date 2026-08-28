from __future__ import annotations

from pathlib import Path

module_path = Path("tools/ml/climate_replay.py")
module = module_path.read_text(encoding="utf-8")
old_mapping = '''    if isinstance(expected, Mapping) and isinstance(actual, Mapping):
        expected_keys = list(expected.keys())
        actual_keys = list(actual.keys())
        if expected_keys != actual_keys:
            return f"{path}.__keys__", expected_keys, actual_keys
        for key in expected_keys:
'''
new_mapping = '''    if isinstance(expected, Mapping) and isinstance(actual, Mapping):
        expected_keys = set(expected.keys())
        actual_keys = set(actual.keys())
        if expected_keys != actual_keys:
            return f"{path}.__keys__", sorted(expected_keys), sorted(actual_keys)
        for key in expected:
'''
if old_mapping not in module:
    raise SystemExit("Stage20A mapping comparison block not found")
module_path.write_text(module.replace(old_mapping, new_mapping, 1), encoding="utf-8")

test_path = Path("tests/test_climate_replay.py")
tests = test_path.read_text(encoding="utf-8")
old_safe = '    record["rule"]["safe"]["heater"] = min(1.0, record["rule"]["safe"]["heater"] + 0.2)\n'
new_safe = '''    current = record["rule"]["safe"]["heater"]
    record["rule"]["safe"]["heater"] = 0.0 if current > 0.0 else 1.0
'''
if old_safe not in tests:
    raise SystemExit("Stage20A safe-action mutation not found")
tests = tests.replace(old_safe, new_safe, 1)
old_applied = '    second["applied"]["heater"] = min(1.0, second["applied"]["heater"] + 0.2)\n'
new_applied = '''    current = second["applied"]["heater"]
    second["applied"]["heater"] = 0.0 if current > 0.0 else 1.0
'''
if old_applied not in tests:
    raise SystemExit("Stage20A applied-action mutation not found")
test_path.write_text(tests.replace(old_applied, new_applied, 1), encoding="utf-8")
