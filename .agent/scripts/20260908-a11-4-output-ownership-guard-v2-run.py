import subprocess
from pathlib import Path

SOURCE = '.agent/scripts/20260908-a11-4-output-ownership-guard-v1-run.py'

subprocess.run(['git', 'fetch', '-q', 'origin', 'agent-control'], check=True)
source = subprocess.check_output(['git', 'show', f'FETCH_HEAD:{SOURCE}'], text=True)

old = r'''RAW_SEND_ALLOW = {
    'src/climate/output/OutputSupervisorExecutor.cpp',
    'src/climate/output/OutputLifecycleExecutor.cpp',
    'src/climate/output/OutputMaintenanceControl.cpp',
}


def production_cpp(root: Path):
    return sorted((root / 'src').rglob('*.cpp'))
'''
new = r'''RAW_SEND_ALLOW = {
    'src/climate/output/OutputSupervisorExecutor.cpp',
    'src/climate/output/OutputLifecycleExecutor.cpp',
    'src/climate/output/OutputMaintenanceControl.cpp',
}

# These files remain only as host compatibility/parity evidence. A separate
# CMake invariant below forbids compiling them into production firmware again.
RETIRED_COMPAT_CPP = {
    'src/climate/Stage28dBinaryRoleArbiter.cpp',
    'src/climate/Stage28dRfOutputEndpoint.cpp',
}


def production_cpp(root: Path):
    return sorted(
        path
        for path in (root / 'src').rglob('*.cpp')
        if path.relative_to(root).as_posix() not in RETIRED_COMPAT_CPP
    )
'''
if source.count(old) != 1:
    raise SystemExit(f'A11_4_V2_PATCH_FAIL production scan target count={source.count(old)}')
source = source.replace(old, new, 1)

anchor = r'''def test_low_level_rmt_allowlist_rejects_runtime_bypass(tmp_path):
'''
insert = r'''def test_retired_compatibility_sources_are_not_production_scan_targets(tmp_path):
    guard = load_guard()
    retired = tmp_path / 'src' / 'climate' / 'Stage28dRfOutputEndpoint.cpp'
    retired.parent.mkdir(parents=True)
    retired.write_text('transport_.send(command);\n')
    active = tmp_path / 'src' / 'climate' / 'output' / 'OutputSupervisorExecutor.cpp'
    active.parent.mkdir(parents=True)
    active.write_text('transport_.send(command);\n')
    assert [guard.relative(tmp_path, path) for path in guard.production_cpp(tmp_path)] == [
        'src/climate/output/OutputSupervisorExecutor.cpp'
    ]


def test_low_level_rmt_allowlist_rejects_runtime_bypass(tmp_path):
'''
if source.count(anchor) != 1:
    raise SystemExit(f'A11_4_V2_PATCH_FAIL test anchor count={source.count(anchor)}')
source = source.replace(anchor, insert, 1)

Path('/tmp/a11_4_v2_inner.py').write_text(source)
subprocess.run(['python3', '/tmp/a11_4_v2_inner.py'], check=True)
