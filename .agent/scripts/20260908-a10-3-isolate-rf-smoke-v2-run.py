import subprocess
from pathlib import Path

SOURCE = '.agent/scripts/20260908-a10-3-isolate-rf-smoke-v1-run.py'

subprocess.run(['git', 'fetch', '-q', 'origin', 'agent-control'], check=True)
source = subprocess.check_output(['git', 'show', f'FETCH_HEAD:{SOURCE}'], text=True)

marker = '# Remove invisible boot-time TX policy/state from diagnostics. Passive RX and the\n'
if source.count(marker) != 1:
    raise SystemExit('A10_3_V2_PATCH_FAIL insertion marker mismatch')

fix = r'''# Remove retired production auto-smoke fallback macros from the runtime itself.
replace_once(
    'src/climate/ClimateV6RealInputRuntime.cpp',
    ''' + "'''" + r'''#ifndef GROWBOX_RF433_LOOPBACK_AUTO_SMOKE
#define GROWBOX_RF433_LOOPBACK_AUTO_SMOKE 0
#endif
#ifndef GROWBOX_RF433_REMOTE_CAPTURE_ENABLED
#define GROWBOX_RF433_REMOTE_CAPTURE_ENABLED 0
#endif
#ifndef GROWBOX_RF433_LOOPBACK_SMOKE_CODE
#define GROWBOX_RF433_LOOPBACK_SMOKE_CODE 0xA55A
#endif
#ifndef GROWBOX_RF433_LOOPBACK_SMOKE_BITS
#define GROWBOX_RF433_LOOPBACK_SMOKE_BITS 16
#endif
#ifndef GROWBOX_RF433_LOOPBACK_SMOKE_PROTOCOL
#define GROWBOX_RF433_LOOPBACK_SMOKE_PROTOCOL 1
#endif
#ifndef GROWBOX_RF433_LOOPBACK_SMOKE_REPEAT
#define GROWBOX_RF433_LOOPBACK_SMOKE_REPEAT 3
#endif
#ifndef GROWBOX_RF433_LOOPBACK_SMOKE_PULSE_US
#define GROWBOX_RF433_LOOPBACK_SMOKE_PULSE_US 0
#endif
''' + "'''" + r''',
    ''' + "'''" + r'''#ifndef GROWBOX_RF433_REMOTE_CAPTURE_ENABLED
#define GROWBOX_RF433_REMOTE_CAPTURE_ENABLED 0
#endif
''' + "'''" + r''',
)

'''
source = source.replace(marker, fix + marker, 1)
Path('/tmp/a10_3_v2_inner.py').write_text(source)
subprocess.run(['python3', '/tmp/a10_3_v2_inner.py'], check=True)
