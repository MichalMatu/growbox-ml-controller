import subprocess
from pathlib import Path

SOURCE = '.agent/scripts/20260908-a10-1-manual-supervisor-v1-run.py'

subprocess.run(['git', 'fetch', '-q', 'origin', 'agent-control'], check=True)
source = subprocess.check_output(['git', 'show', f'FETCH_HEAD:{SOURCE}'], text=True)
marker = "run(['git', 'add', '-N',"
if source.count(marker) != 1:
    raise SystemExit('A10_1_V2_PATCH_FAIL runner marker mismatch')
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
        raise SystemExit(f'A10_1_V2_FIXUP_FAIL expected one malformed CRLF, found {count}')
    console_bytes = console_bytes.replace(old, new, 1)
console_path.write_bytes(console_bytes)
print('A10_1_V2_STRING_FIXUP_PASS')

'''
patched = source.replace(marker, fixup + marker, 1)
Path('/tmp/a10_1_v2_inner.py').write_text(patched)
subprocess.run(['python3', '/tmp/a10_1_v2_inner.py'], check=True)
