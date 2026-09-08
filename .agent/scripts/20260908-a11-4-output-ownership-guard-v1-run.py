import subprocess
from pathlib import Path

BASE = 'dac0dcd48180273380380832b3de1fba292a79c3'
BRANCH = 'mvp/environment-controller'
EXPECTED = sorted([
    'scripts/check_output_rf_ownership.py',
    'scripts/quality_gate_push.sh',
    'tests/test_output_execution_ownership.py',
])


def run(cmd, env=None):
    print('+', ' '.join(cmd), flush=True)
    subprocess.run(cmd, check=True, env=env)


def out(cmd):
    return subprocess.check_output(cmd, text=True).strip()


run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'HEAD']) != BASE:
    raise SystemExit('A11_4_IDENTITY_FAIL local HEAD mismatch')
if out(['git', 'rev-parse', 'FETCH_HEAD']) != BASE:
    raise SystemExit('A11_4_IDENTITY_FAIL remote branch mismatch')
if out(['git', 'status', '--porcelain']):
    raise SystemExit('A11_4_IDENTITY_FAIL worktree not clean')
print('A11_4_IDENTITY_PASS')

Path('scripts/check_output_rf_ownership.py').write_text(r'''#!/usr/bin/env python3
"""Final configured-output RF ownership invariant.

Normal climate, schedule, safety, runtime and service-console code may compose
output execution, but must not own RF transmission calls. The only legal
production call sites are the dedicated RF transport layers plus the explicit
maintenance-only adapter.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

LOW_LEVEL_RMT = {
    'rmt_new_tx_channel(': {'src/climate/rf433/Rf433RmtLoopback.cpp'},
    'rmt_transmit(': {'src/climate/rf433/Rf433RmtLoopback.cpp'},
    'rmt_tx_wait_all_done(': {'src/climate/rf433/Rf433RmtLoopback.cpp'},
}
RADIO_TX = {
    'transmitAndReceive(': {
        'src/climate/rf433/Rf433RmtLoopback.cpp',
        'src/climate/rf433/Rf433RmtFrameSender.cpp',
        'src/climate/runtime/Stage28RfDiagnostics.cpp',
    },
    'transmitFrame(': {
        'src/climate/rf433/Rf433RmtFrameSender.cpp',
        'src/climate/rf433/Rf433OutputTransport.cpp',
    },
    'manualTransmit(': {
        'src/climate/runtime/Stage28RfDiagnostics.cpp',
        'src/climate/runtime/Stage28MaintenanceRfTransport.cpp',
    },
}

AUTO_SMOKE_TOKENS = (
    'auto_smoke',
    'smoke_attempted_',
    'runSmoke',
    'GROWBOX_RF433_LOOPBACK_AUTO_SMOKE',
    'GROWBOX_RF433_LOOPBACK_SMOKE_',
)

RUNTIME_FORBIDDEN = (
    'Stage28dRfOutputEndpoint',
    'MappedClimateRoleDriver',
    'SwitchableRoleDriver',
    'ClimateActuatorAdapter',
    'writeScheduledLight(',
    'setSafetyForceExhaust(',
    'forceSafeStateWithRetries',
    'physical_endpoint',
    '.manualTransmit(',
    '.transmitFrame(',
    '.transmitAndReceive(',
    'rmt_transmit(',
)

SERVICE_CONSOLE_FORBIDDEN = (
    'manualTransmit(',
    'transmitFrame(',
    'transmitAndReceive(',
    'rmt_transmit(',
)

LEGACY_FIRMWARE_SOURCES = (
    '"climate/Stage28dBinaryRoleArbiter.cpp"',
    '"climate/Stage28dRfOutputEndpoint.cpp"',
)

RAW_SEND_RE = re.compile(r'(?<![A-Za-z0-9_])(transport_|raw_transport_)\.send\(')
RAW_SEND_ALLOW = {
    'src/climate/output/OutputSupervisorExecutor.cpp',
    'src/climate/output/OutputLifecycleExecutor.cpp',
    'src/climate/output/OutputMaintenanceControl.cpp',
}


def production_cpp(root: Path):
    return sorted((root / 'src').rglob('*.cpp'))


def relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def cpp_sites(root: Path, token: str) -> set[str]:
    sites: set[str] = set()
    for path in production_cpp(root):
        if token in path.read_text():
            sites.add(relative(root, path))
    return sites


def find_violations(root: Path = ROOT) -> list[str]:
    errors: list[str] = []

    required = (
        'src/climate/rf433/Rf433RmtLoopback.cpp',
        'src/climate/rf433/Rf433RmtFrameSender.cpp',
        'src/climate/rf433/Rf433OutputTransport.cpp',
        'src/climate/runtime/Stage28RfDiagnostics.cpp',
        'src/climate/runtime/Stage28MaintenanceRfTransport.cpp',
        'src/climate/output/OutputSupervisorExecutor.cpp',
        'src/climate/output/OutputLifecycleExecutor.cpp',
        'src/climate/output/OutputMaintenanceControl.cpp',
        'src/climate/ClimateV6RealInputRuntime.cpp',
        'src/climate/runtime/Stage28ServiceConsole.cpp',
        'src/climate/runtime/Stage28ServiceConsoleCommand.cpp',
        'src/CMakeLists.txt',
        'scripts/stage27c_crowpanel.sh',
    )
    for rel in required:
        if not (root / rel).is_file():
            errors.append(f'{rel}: required ownership surface missing')

    if errors:
        return errors

    for token, allowed in {**LOW_LEVEL_RMT, **RADIO_TX}.items():
        actual = cpp_sites(root, token)
        unexpected = actual - allowed
        missing = allowed - actual
        for rel in sorted(unexpected):
            errors.append(f'{rel}: forbidden configured-output TX token {token!r}')
        for rel in sorted(missing):
            errors.append(f'{rel}: expected ownership token missing {token!r}')

    raw_send_sites: set[str] = set()
    for path in production_cpp(root):
        if RAW_SEND_RE.search(path.read_text()):
            raw_send_sites.add(relative(root, path))
    for rel in sorted(raw_send_sites - RAW_SEND_ALLOW):
        errors.append(f'{rel}: raw OutputTransport send call outside supervisor/maintenance boundary')
    for rel in sorted(RAW_SEND_ALLOW - raw_send_sites):
        errors.append(f'{rel}: expected supervisor/maintenance transport send call missing')

    runtime_path = root / 'src/climate/ClimateV6RealInputRuntime.cpp'
    runtime = runtime_path.read_text()
    for token in RUNTIME_FORBIDDEN:
        if token in runtime:
            errors.append(f'{relative(root, runtime_path)}: forbidden direct output owner token {token!r}')

    for rel in (
        'src/climate/runtime/Stage28ServiceConsole.cpp',
        'src/climate/runtime/Stage28ServiceConsoleCommand.cpp',
    ):
        text = (root / rel).read_text()
        for token in SERVICE_CONSOLE_FORBIDDEN:
            if token in text:
                errors.append(f'{rel}: service console must not own TX token {token!r}')

    cmake = (root / 'src/CMakeLists.txt').read_text()
    for token in LEGACY_FIRMWARE_SOURCES:
        if token in cmake:
            errors.append(f'src/CMakeLists.txt: legacy execution owner still compiled {token}')

    output_transport = (root / 'src/climate/rf433/Rf433OutputTransport.cpp').read_text()
    for token in ('Stage28RfDiagnostics', 'manualTransmit('):
        if token in output_transport:
            errors.append(
                f'src/climate/rf433/Rf433OutputTransport.cpp: normal transport depends on diagnostics {token!r}'
            )

    maintenance = (root / 'src/climate/runtime/Stage28MaintenanceRfTransport.cpp').read_text()
    for required_token in (
        'OutputSource::Maintenance',
        'OutputReason::MaintenanceRequest',
        'diagnostics_.manualTransmit(',
    ):
        if required_token not in maintenance:
            errors.append(
                'src/climate/runtime/Stage28MaintenanceRfTransport.cpp: '
                f'maintenance-only guard missing {required_token!r}'
            )

    diagnostics = (root / 'src/climate/runtime/Stage28RfDiagnostics.cpp').read_text()
    if 'if (config_.passive_capture)' not in diagnostics or 'capturePassive();' not in diagnostics:
        errors.append('src/climate/runtime/Stage28RfDiagnostics.cpp: passive RX path missing')
    if diagnostics.count('transmitAndReceive(') != 1:
        errors.append(
            'src/climate/runtime/Stage28RfDiagnostics.cpp: TX must remain only in explicit manualTransmit'
        )

    for rel in (
        'src/climate/runtime/Stage28RfDiagnostics.h',
        'src/climate/runtime/Stage28RfDiagnostics.cpp',
        'src/climate/ClimateV6RealInputRuntime.cpp',
        'src/CMakeLists.txt',
        'scripts/stage27c_crowpanel.sh',
    ):
        text = (root / rel).read_text()
        for token in AUTO_SMOKE_TOKENS:
            if token in text:
                errors.append(f'{rel}: forbidden production auto-smoke token {token!r}')

    return errors


def main() -> int:
    errors = find_violations(ROOT)
    if errors:
        for error in errors:
            print(f'OUTPUT_EXECUTION_OWNERSHIP_FAIL {error}', file=sys.stderr)
        return 1
    print('OUTPUT_EXECUTION_OWNERSHIP_PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
''')

quality = Path('scripts/quality_gate_push.sh')
text = quality.read_text()
anchor = 'echo "==> pytest"\n'
if text.count(anchor) != 1:
    raise SystemExit('A11_4_PATCH_FAIL quality gate anchor mismatch')
text = text.replace(
    anchor,
    'echo "==> output execution ownership"\n"$PY" "${ROOT}/scripts/check_output_rf_ownership.py"\n\n' + anchor,
    1,
)
quality.write_text(text)

Path('tests/test_output_execution_ownership.py').write_text(r'''from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'check_output_rf_ownership.py'


def load_guard():
    spec = spec_from_file_location('output_execution_ownership_guard', SCRIPT)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repository_output_execution_ownership_is_single_owner():
    guard = load_guard()
    assert guard.find_violations(ROOT) == []


def test_low_level_rmt_allowlist_rejects_runtime_bypass(tmp_path):
    guard = load_guard()
    allowed = tmp_path / 'src' / 'climate' / 'rf433' / 'Rf433RmtLoopback.cpp'
    allowed.parent.mkdir(parents=True)
    allowed.write_text('rmt_transmit(tx, enc, data, size, cfg);\n')
    runtime = tmp_path / 'src' / 'climate' / 'ClimateV6RealInputRuntime.cpp'
    runtime.parent.mkdir(parents=True, exist_ok=True)
    runtime.write_text('rmt_transmit(tx, enc, data, size, cfg);\n')

    sites = guard.cpp_sites(tmp_path, 'rmt_transmit(')
    assert sites == {
        'src/climate/rf433/Rf433RmtLoopback.cpp',
        'src/climate/ClimateV6RealInputRuntime.cpp',
    }
    assert sites - guard.LOW_LEVEL_RMT['rmt_transmit('] == {
        'src/climate/ClimateV6RealInputRuntime.cpp'
    }


def test_raw_transport_send_allowlist_rejects_new_production_owner(tmp_path):
    guard = load_guard()
    runtime = tmp_path / 'src' / 'climate' / 'ClimateV6RealInputRuntime.cpp'
    runtime.parent.mkdir(parents=True)
    runtime.write_text('transport_.send(command);\n')
    assert guard.RAW_SEND_RE.search(runtime.read_text()) is not None
    assert 'src/climate/ClimateV6RealInputRuntime.cpp' not in guard.RAW_SEND_ALLOW
''')

run(['git', 'add', '-N', *EXPECTED])
changed = sorted(out(['git', 'diff', '--name-only']).splitlines())
if changed != EXPECTED:
    raise SystemExit(f'A11_4_SCOPE_FAIL changed={changed!r} expected={EXPECTED!r}')
run(['git', 'diff', '--check'])
run(['python3', 'scripts/check_output_rf_ownership.py'])
py = '.venv/bin/python' if Path('.venv/bin/python').exists() else 'python3'
run([py, '-m', 'pytest', 'tests/test_output_execution_ownership.py', '-q'])

# Guard this step from accidentally changing production C++.
production_changes = [p for p in changed if p.startswith('src/')]
if production_changes:
    raise SystemExit(f'A11_4_PRODUCTION_SCOPE_FAIL {production_changes!r}')

run(['git', 'add', *EXPECTED])
run(['git', 'commit', '-m', 'Enforce output execution ownership'])
commit = out(['git', 'rev-parse', 'HEAD'])
if out(['git', 'rev-parse', 'HEAD^']) != BASE:
    raise SystemExit('A11_4_PARENT_FAIL')
run(['git', 'push', 'origin', f'HEAD:{BRANCH}'])
run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'FETCH_HEAD']) != commit:
    raise SystemExit('A11_4_PUSH_VERIFY_FAIL')
print(f'A11_4_PASS commit={commit}')
