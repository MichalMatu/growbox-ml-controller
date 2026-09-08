import os
import subprocess
from pathlib import Path

BASE = 'b31982664c85c0903587a2eeaa8fca5d9699f683'
BRANCH = 'mvp/environment-controller'
EXPECTED = sorted([
    'scripts/check_output_rf_ownership.py',
    'scripts/stage27c_crowpanel.sh',
    'src/CMakeLists.txt',
    'src/climate/ClimateV6RealInputRuntime.cpp',
    'src/climate/runtime/Stage28RfDiagnostics.cpp',
    'src/climate/runtime/Stage28RfDiagnostics.h',
])


def run(cmd, env=None):
    print('+', ' '.join(cmd), flush=True)
    subprocess.run(cmd, check=True, env=env)


def out(cmd):
    return subprocess.check_output(cmd, text=True).strip()


def replace_once(path, old, new):
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{path}: expected one replacement, found {count}')
    p.write_text(text.replace(old, new, 1))


run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'HEAD']) != BASE:
    raise SystemExit('A10_3_IDENTITY_FAIL local HEAD mismatch')
if out(['git', 'rev-parse', 'FETCH_HEAD']) != BASE:
    raise SystemExit('A10_3_IDENTITY_FAIL remote branch mismatch')
if out(['git', 'status', '--porcelain']):
    raise SystemExit('A10_3_IDENTITY_FAIL worktree not clean')
print('A10_3_IDENTITY_PASS')

# Remove invisible boot-time TX policy/state from diagnostics. Passive RX and the
# explicit maintenance-only manual TX entry point remain.
replace_once(
    'src/climate/runtime/Stage28RfDiagnostics.h',
    '''  bool passive_capture{false};\n  bool auto_smoke{false};\n  int tx_gpio{8};\n  int rx_gpio{14};\n  rf433::FrameConfig smoke{};\n  std::uint32_t passive_timeout_ms{750U};\n  std::uint32_t smoke_timeout_ms{1'500U};\n  std::uint64_t smoke_after_ms{3'000U};\n''',
    '''  bool passive_capture{false};\n  int tx_gpio{8};\n  int rx_gpio{14};\n  std::uint32_t passive_timeout_ms{750U};\n  std::uint32_t manual_tx_timeout_ms{1'500U};\n''',
)
replace_once(
    'src/climate/runtime/Stage28RfDiagnostics.h',
    '''private:\n  void capturePassive() noexcept;\n  void runSmoke() noexcept;\n\n  Stage28RfDiagnosticsConfig config_{};\n  rf433::Rf433RmtLoopback& radio_;\n  bool ready_{false};\n  bool smoke_attempted_{false};\n  bool capture_ready_logged_{false};\n''',
    '''private:\n  void capturePassive() noexcept;\n\n  Stage28RfDiagnosticsConfig config_{};\n  rf433::Rf433RmtLoopback& radio_;\n  bool ready_{false};\n  bool capture_ready_logged_{false};\n''',
)

replace_once(
    'src/climate/runtime/Stage28RfDiagnostics.cpp',
    '''void Stage28RfDiagnostics::tick(std::uint64_t now_ms) noexcept {\n  if (!ready_) {\n    return;\n  }\n\n  if (config_.passive_capture) {\n    capturePassive();\n    return;\n  }\n\n  if (config_.auto_smoke && !smoke_attempted_ && now_ms >= config_.smoke_after_ms) {\n    runSmoke();\n  }\n}\n''',
    '''void Stage28RfDiagnostics::tick(std::uint64_t now_ms) noexcept {\n  (void)now_ms;\n  if (!ready_) {\n    return;\n  }\n\n  if (config_.passive_capture) {\n    capturePassive();\n  }\n}\n''',
)
replace_once(
    'src/climate/runtime/Stage28RfDiagnostics.cpp',
    '  static_cast<void>(radio_.transmitAndReceive(frame, config_.smoke_timeout_ms, evidence));\n',
    '  static_cast<void>(radio_.transmitAndReceive(frame, config_.manual_tx_timeout_ms, evidence));\n',
)
cpp = Path('src/climate/runtime/Stage28RfDiagnostics.cpp')
text = cpp.read_text()
start = text.find('\nvoid Stage28RfDiagnostics::runSmoke() noexcept {')
if start < 0:
    raise SystemExit('Stage28RfDiagnostics.cpp: runSmoke definition missing')
end = text.find('\n} // namespace growbox::app::climate_io::runtime\n', start)
if end < 0:
    raise SystemExit('Stage28RfDiagnostics.cpp: namespace footer missing after runSmoke')
text = text[:start] + '\n' + text[end:]
cpp.write_text(text)

replace_once(
    'src/climate/ClimateV6RealInputRuntime.cpp',
    '''  config.passive_capture = GROWBOX_RF433_REMOTE_CAPTURE_ENABLED != 0;\n  config.auto_smoke = GROWBOX_RF433_LOOPBACK_AUTO_SMOKE != 0;\n  config.tx_gpio = GROWBOX_RF433_TX_GPIO;\n  config.rx_gpio = GROWBOX_RF433_RX_GPIO;\n  config.smoke = {{static_cast<std::uint32_t>(GROWBOX_RF433_LOOPBACK_SMOKE_CODE),\n                   static_cast<std::uint8_t>(GROWBOX_RF433_LOOPBACK_SMOKE_BITS),\n                   static_cast<std::uint8_t>(GROWBOX_RF433_LOOPBACK_SMOKE_PROTOCOL)},\n                  static_cast<std::uint8_t>(GROWBOX_RF433_LOOPBACK_SMOKE_REPEAT),\n                  static_cast<std::uint16_t>(GROWBOX_RF433_LOOPBACK_SMOKE_PULSE_US)};\n''',
    '''  config.passive_capture = GROWBOX_RF433_REMOTE_CAPTURE_ENABLED != 0;\n  config.tx_gpio = GROWBOX_RF433_TX_GPIO;\n  config.rx_gpio = GROWBOX_RF433_RX_GPIO;\n''',
)

cmake = Path('src/CMakeLists.txt')
text = cmake.read_text()
for line in [
    'set(GROWBOX_RF433_LOOPBACK_AUTO_SMOKE "0" CACHE STRING "Run one Stage28 RF433 boot loopback smoke")\n',
    'set(GROWBOX_RF433_LOOPBACK_SMOKE_CODE "0xA55A" CACHE STRING "Stage28 RF433 loopback smoke code")\n',
    'set(GROWBOX_RF433_LOOPBACK_SMOKE_BITS "16" CACHE STRING "Stage28 RF433 loopback smoke bit length")\n',
    'set(GROWBOX_RF433_LOOPBACK_SMOKE_PROTOCOL "1" CACHE STRING "Stage28 RF433 loopback smoke protocol")\n',
    'set(GROWBOX_RF433_LOOPBACK_SMOKE_REPEAT "3" CACHE STRING "Stage28 RF433 loopback smoke repeat count")\n',
    'set(GROWBOX_RF433_LOOPBACK_SMOKE_PULSE_US "0" CACHE STRING "Stage28 RF433 loopback smoke pulse length; 0 uses protocol default")\n',
    '    GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=${GROWBOX_RF433_LOOPBACK_AUTO_SMOKE}\n',
    '    GROWBOX_RF433_LOOPBACK_SMOKE_CODE=${GROWBOX_RF433_LOOPBACK_SMOKE_CODE}\n',
    '    GROWBOX_RF433_LOOPBACK_SMOKE_BITS=${GROWBOX_RF433_LOOPBACK_SMOKE_BITS}\n',
    '    GROWBOX_RF433_LOOPBACK_SMOKE_PROTOCOL=${GROWBOX_RF433_LOOPBACK_SMOKE_PROTOCOL}\n',
    '    GROWBOX_RF433_LOOPBACK_SMOKE_REPEAT=${GROWBOX_RF433_LOOPBACK_SMOKE_REPEAT}\n',
    '    GROWBOX_RF433_LOOPBACK_SMOKE_PULSE_US=${GROWBOX_RF433_LOOPBACK_SMOKE_PULSE_US}\n',
]:
    if text.count(line) != 1:
        raise SystemExit(f'src/CMakeLists.txt: expected one smoke line, found {text.count(line)}: {line!r}')
    text = text.replace(line, '', 1)
cmake.write_text(text)

script = Path('scripts/stage27c_crowpanel.sh')
text = script.read_text()
for line in [
    'RF433_LOOPBACK_AUTO_SMOKE="${GROWBOX_RF433_LOOPBACK_AUTO_SMOKE:-0}"\n',
    'RF433_LOOPBACK_SMOKE_CODE="${GROWBOX_RF433_LOOPBACK_SMOKE_CODE:-0xA55A}"\n',
    'RF433_LOOPBACK_SMOKE_BITS="${GROWBOX_RF433_LOOPBACK_SMOKE_BITS:-16}"\n',
    'RF433_LOOPBACK_SMOKE_PROTOCOL="${GROWBOX_RF433_LOOPBACK_SMOKE_PROTOCOL:-1}"\n',
    'RF433_LOOPBACK_SMOKE_REPEAT="${GROWBOX_RF433_LOOPBACK_SMOKE_REPEAT:-3}"\n',
    'RF433_LOOPBACK_SMOKE_PULSE_US="${GROWBOX_RF433_LOOPBACK_SMOKE_PULSE_US:-0}"\n',
    '  -D "GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=$RF433_LOOPBACK_AUTO_SMOKE"\n',
    '  -D "GROWBOX_RF433_LOOPBACK_SMOKE_CODE=$RF433_LOOPBACK_SMOKE_CODE"\n',
    '  -D "GROWBOX_RF433_LOOPBACK_SMOKE_BITS=$RF433_LOOPBACK_SMOKE_BITS"\n',
    '  -D "GROWBOX_RF433_LOOPBACK_SMOKE_PROTOCOL=$RF433_LOOPBACK_SMOKE_PROTOCOL"\n',
    '  -D "GROWBOX_RF433_LOOPBACK_SMOKE_REPEAT=$RF433_LOOPBACK_SMOKE_REPEAT"\n',
    '  -D "GROWBOX_RF433_LOOPBACK_SMOKE_PULSE_US=$RF433_LOOPBACK_SMOKE_PULSE_US"\n',
]:
    if text.count(line) != 1:
        raise SystemExit(f'scripts/stage27c_crowpanel.sh: expected one smoke line, found {text.count(line)}: {line!r}')
    text = text.replace(line, '', 1)
script.write_text(text)

Path('scripts/check_output_rf_ownership.py').write_text(r'''#!/usr/bin/env python3
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
''')

run(['git', 'add', '-N', 'scripts/check_output_rf_ownership.py'])
run(['git', 'diff', '--check'])
changed = sorted(filter(None, out(['git', 'diff', '--name-only']).splitlines()))
if changed != EXPECTED:
    raise SystemExit(f'A10_3_ALLOWLIST_FAIL changed={changed!r}')

run(['python3', 'scripts/check_output_rf_ownership.py'])
print('A10_3_STATIC_PASS')

build = 'build/host-tests-a10-3-v1'
run(['cmake', '-S', 'test/host', '-B', build])
targets = [
    'output_maintenance_control_tests',
    'stage28_service_console_tests',
    'output_supervisor_lifecycle_tests',
    'output_manual_control_tests',
]
run(['cmake', '--build', build, '--parallel', '--target', *targets])
regex = '^(' + '|'.join(targets) + ')$'
run(['ctest', '--test-dir', build, '-R', regex, '--output-on-failure'])
print('A10_3_FOCUSED_PASS')

fw_build = 'build/stage27c-a10-3-v1'
Path(fw_build).mkdir(parents=True, exist_ok=True)
env = os.environ.copy()
env.update({
    'STAGE27C_BUILD_DIR': fw_build,
    'STAGE27C_SDKCONFIG': f'{fw_build}/sdkconfig',
    'GROWBOX_RF433_LOOPBACK_ENABLED': '1',
    'GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED': '1',
    # Deliberately set the retired environment knob to 1. The canonical build
    # script must ignore it completely after A10.3.
    'GROWBOX_RF433_LOOPBACK_AUTO_SMOKE': '1',
    'GROWBOX_RF433_REMOTE_CAPTURE_ENABLED': '0',
})
run(['bash', 'scripts/stage27c_crowpanel.sh', 'build'], env=env)
print('A10_3_CANONICAL_BUILD_PASS')

run(['git', 'diff', '--check'])
changed = sorted(filter(None, out(['git', 'diff', '--name-only']).splitlines()))
if changed != EXPECTED:
    raise SystemExit(f'A10_3_FINAL_ALLOWLIST_FAIL changed={changed!r}')

run(['git', 'add', '--', *EXPECTED])
staged = sorted(filter(None, out(['git', 'diff', '--cached', '--name-only']).splitlines()))
if staged != EXPECTED:
    raise SystemExit(f'A10_3_STAGED_ALLOWLIST_FAIL staged={staged!r}')
run(['git', 'commit', '-m', 'Isolate RF smoke diagnostics from production outputs'])
commit = out(['git', 'rev-parse', 'HEAD'])
run(['git', 'push', 'origin', f'HEAD:{BRANCH}'])
run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'FETCH_HEAD']) != commit:
    raise SystemExit('A10_3_REMOTE_VERIFY_FAIL')
if out(['git', 'status', '--porcelain']):
    raise SystemExit('A10_3_CLEAN_VERIFY_FAIL')
print(f'A10_3_PASS commit={commit}')
