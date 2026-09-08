import subprocess
from pathlib import Path

SOURCE = '.agent/scripts/20260908-a10-1-manual-supervisor-v1-run.py'

subprocess.run(['git', 'fetch', '-q', 'origin', 'agent-control'], check=True)
source = subprocess.check_output(['git', 'show', f'FETCH_HEAD:{SOURCE}'], text=True)

old_guard = """if resolver.find('findSafetyConstraint') < resolver.find('input.manual.endpoints'):\n    raise SystemExit('A10_1_STATIC_FAIL safety precedence check ordering unexpected')\n"""
new_guard = """manual_pos = resolver.find('input.manual.endpoints')\nsafety_pos = resolver.find('if (const auto* safety = findSafetyConstraint', manual_pos)\nif manual_pos < 0 or safety_pos < 0 or safety_pos <= manual_pos:\n    raise SystemExit('A10_1_STATIC_FAIL safety precedence check ordering unexpected')\n"""
if source.count(old_guard) != 1:
    raise SystemExit('A10_1_V4_PATCH_FAIL static guard mismatch')
source = source.replace(old_guard, new_guard, 1)

old_include = '#include "climate/output/OutputPolicyConfig.h"\n#include "climate/output/OutputSupervisorLifecycle.h"'
new_include = '#include "climate/output/OutputIntents.h"\n#include "climate/output/OutputPolicyConfig.h"\n#include "climate/output/OutputSupervisorLifecycle.h"'
if source.count(old_include) != 1:
    raise SystemExit(f'A10_1_V4_PATCH_FAIL include anchor count={source.count(old_include)}')
source = source.replace(old_include, new_include, 1)

marker = "run(['git', 'add', '-N',"
if source.count(marker) != 1:
    raise SystemExit('A10_1_V4_PATCH_FAIL runner marker mismatch')
fixup = r'''
console_path = Path('src/climate/runtime/Stage28ServiceConsole.cpp')
console_bytes = console_path.read_bytes()
replacements = [
    (b'writeText("error: manual output control unavailable\r\n");',
     b'writeText("error: manual output control unavailable\\r\\n");'),
    (b'"sequence=%llu outputs=%s physical_state=unconfirmed\r\n",',
     b'"sequence=%llu outputs=%s physical_state=unconfirmed\\r\\n",'),
]
for old, new in replacements:
    count = console_bytes.count(old)
    if count != 1:
        raise SystemExit(f'A10_1_V4_FIXUP_FAIL expected one malformed CRLF, found {count}')
    console_bytes = console_bytes.replace(old, new, 1)
console_path.write_bytes(console_bytes)
print('A10_1_V4_STRING_FIXUP_PASS')

'''
source = source.replace(marker, fixup + marker, 1)
Path('/tmp/a10_1_v4_inner.py').write_text(source)
subprocess.run(['python3', '/tmp/a10_1_v4_inner.py'], check=True)
