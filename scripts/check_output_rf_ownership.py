#!/usr/bin/env python3
"""Narrow A10.3 RF diagnostics/output ownership guard.

This is intentionally a draft guard. A11.4 will enforce the full production
output-owner allowlist after legacy startup/fault paths are removed.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text()


errors: list[str] = []
diag_h = read('src/climate/runtime/Stage28RfDiagnostics.h')
diag_cpp = read('src/climate/runtime/Stage28RfDiagnostics.cpp')
runtime = read('src/climate/ClimateV6RealInputRuntime.cpp')
cmake = read('src/CMakeLists.txt')
canonical = read('scripts/stage27c_crowpanel.sh')

for token in (
    'auto_smoke',
    'smoke_attempted_',
    'runSmoke',
    'GROWBOX_RF433_LOOPBACK_AUTO_SMOKE',
    'GROWBOX_RF433_LOOPBACK_SMOKE_',
):
    for rel, text in (
        ('Stage28RfDiagnostics.h', diag_h),
        ('Stage28RfDiagnostics.cpp', diag_cpp),
        ('ClimateV6RealInputRuntime.cpp', runtime),
        ('src/CMakeLists.txt', cmake),
        ('scripts/stage27c_crowpanel.sh', canonical),
    ):
        if token in text:
            errors.append(f'{rel}: forbidden production auto-smoke token {token!r}')

if 'if (config_.passive_capture)' not in diag_cpp or 'capturePassive();' not in diag_cpp:
    errors.append('Stage28RfDiagnostics.cpp: passive receive path missing')
if 'manualReceive(' not in diag_cpp:
    errors.append('Stage28RfDiagnostics.cpp: explicit receive API missing')
if diag_cpp.count('transmitAndReceive(') != 1:
    errors.append('Stage28RfDiagnostics.cpp: expected exactly one explicit TX implementation')

manual_tx = re.search(
    r'bool Stage28RfDiagnostics::manualTransmit\(.*?\n\}', diag_cpp, flags=re.S
)
if manual_tx is None or 'transmitAndReceive(' not in manual_tx.group(0):
    errors.append('Stage28RfDiagnostics.cpp: TX must remain inside manualTransmit only')

allowed_cpp = {
    'src/climate/runtime/Stage28RfDiagnostics.cpp',
    'src/climate/runtime/Stage28MaintenanceRfTransport.cpp',
}
for path in (ROOT / 'src').rglob('*.cpp'):
    text = path.read_text()
    if 'manualTransmit(' not in text:
        continue
    rel = path.relative_to(ROOT).as_posix()
    if rel not in allowed_cpp:
        errors.append(f'{rel}: diagnostics manualTransmit call is not maintenance-only')

maintenance = read('src/climate/runtime/Stage28MaintenanceRfTransport.cpp')
if 'diagnostics_.manualTransmit(' not in maintenance:
    errors.append('Stage28MaintenanceRfTransport.cpp: explicit maintenance TX call missing')
if 'rf_diagnostics.tick(now_ms);' not in runtime:
    errors.append('ClimateV6RealInputRuntime.cpp: diagnostics tick unexpectedly removed')

if errors:
    for error in errors:
        print(f'OUTPUT_RF_OWNERSHIP_FAIL {error}', file=sys.stderr)
    raise SystemExit(1)
print('OUTPUT_RF_OWNERSHIP_PASS')
