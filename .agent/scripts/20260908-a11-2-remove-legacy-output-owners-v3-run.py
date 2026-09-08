import subprocess
from pathlib import Path

SOURCE = '.agent/scripts/20260908-a11-2-remove-legacy-output-owners-v1-run.py'

subprocess.run(['git', 'fetch', '-q', 'origin', 'agent-control'], check=True)
source = subprocess.check_output(['git', 'show', f'FETCH_HEAD:{SOURCE}'], text=True)

# Repair the runtime cleanup assertion: the exact audited baseline contains
# three legacy disableReal() calls and A11.2 removes all three.
disable_line = "replace_once(runtime_path, '    fail_safe_output_driver.disableReal();\\n', '')"
lines = source.splitlines(keepends=True)
disable_matches = [index for index, line in enumerate(lines) if disable_line in line]
if len(disable_matches) != 1:
    raise SystemExit(f'A11_2_V3_PATCH_FAIL disableReal source-line matches={disable_matches!r}')
index = disable_matches[0]
lines[index:index + 1] = ["""text = Path(runtime_path).read_text()
legacy_disable = '    fail_safe_output_driver.disableReal();\\n'
if text.count(legacy_disable) != 3:
    raise SystemExit(
        f'{runtime_path}: expected three legacy disableReal calls, found {text.count(legacy_disable)}'
    )
Path(runtime_path).write_text(text.replace(legacy_disable, ''))
"""]
source = ''.join(lines)

# Repair the focused-test constructor migration assertion: the audited test
# file has exactly two identical legacy fallback constructions. Both must move
# to the supervisor-only constructor before the old fallback test is replaced.
marker = "'''  RecordingFailSafeSink fallback;\\n"
marker_index = source.find(marker)
if marker_index < 0 or source.find(marker, marker_index + 1) >= 0:
    raise SystemExit('A11_2_V3_PATCH_FAIL fallback constructor source marker mismatch')
block_start = source.rfind('replace_once(', 0, marker_index)
block_end = source.find('\n)\n', marker_index)
if block_start < 0 or block_end < 0:
    raise SystemExit('A11_2_V3_PATCH_FAIL fallback constructor call bounds')
block_end += 3
old_call = source[block_start:block_end]
if "test_path" not in old_call or "&fallback" not in old_call:
    raise SystemExit('A11_2_V3_PATCH_FAIL unexpected fallback constructor call')
replacement = """test_text = Path(test_path).read_text()
legacy_fallback_ctor = '''  RecordingFailSafeSink fallback;\n  climate_io::ClimateOutputSupervisorSink sink(makeClimateConfig(), resolver, executor, store,\n                                                &fallback);\n'''
supervisor_ctor = '''  climate_io::ClimateOutputSupervisorSink sink(makeClimateConfig(), resolver, executor, store);\n'''
if test_text.count(legacy_fallback_ctor) != 2:
    raise SystemExit(
        f'{test_path}: expected two legacy fallback constructors, found {test_text.count(legacy_fallback_ctor)}'
    )
Path(test_path).write_text(test_text.replace(legacy_fallback_ctor, supervisor_ctor))
"""
source = source[:block_start] + replacement + source[block_end:]

Path('/tmp/a11_2_v3_inner.py').write_text(source)
subprocess.run(['python3', '/tmp/a11_2_v3_inner.py'], check=True)
