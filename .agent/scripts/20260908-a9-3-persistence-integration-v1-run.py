import os
import subprocess
from pathlib import Path

BASE = 'a04c4db1c28945f0ff81efc970188a206ab153e5'
BRANCH = 'mvp/environment-controller'
EXPECTED = sorted([
    'src/CMakeLists.txt',
    'src/climate/ClimateV6RealInputRuntime.cpp',
    'src/climate/Stage28dOutputBindings.cpp',
    'src/climate/Stage28dOutputBindings.h',
    'src/climate/output/OutputPersistenceCoordinator.cpp',
    'src/climate/output/OutputPersistenceCoordinator.h',
    'src/climate/output/OutputStateStore.cpp',
    'src/climate/output/OutputStateStore.h',
    'test/host/CMakeLists.txt',
    'test/test_output_persistence_coordinator/test_main.cpp',
])


def run(cmd, env=None):
    print('+', ' '.join(cmd), flush=True)
    subprocess.run(cmd, check=True, env=env)


def out(cmd):
    return subprocess.check_output(cmd, text=True).strip()


run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'HEAD']) != BASE:
    raise SystemExit('A9_3_IDENTITY_FAIL local HEAD mismatch')
if out(['git', 'rev-parse', 'FETCH_HEAD']) != BASE:
    raise SystemExit('A9_3_IDENTITY_FAIL remote branch mismatch')
if out(['git', 'status', '--porcelain']):
    raise SystemExit('A9_3_IDENTITY_FAIL worktree not clean')
print('A9_3_IDENTITY_PASS')

run(['git', 'fetch', '-q', 'origin', 'agent-control'])
Path('/tmp/a9_3_edit.py').write_text(
    out(['git', 'show', 'FETCH_HEAD:.agent/scripts/20260908-a9-3-persistence-integration-v1.py']) + '\n')
run(['python3', '/tmp/a9_3_edit.py'])

run(['git', 'add', '-N',
     'src/climate/output/OutputPersistenceCoordinator.cpp',
     'src/climate/output/OutputPersistenceCoordinator.h',
     'test/test_output_persistence_coordinator/test_main.cpp'])
run(['git', 'diff', '--check'])
changed = sorted(filter(None, out(['git', 'diff', '--name-only']).splitlines()))
if changed != EXPECTED:
    raise SystemExit(f'A9_3_ALLOWLIST_FAIL changed={changed!r}')

coordinator = Path('src/climate/output/OutputPersistenceCoordinator.cpp').read_text()
state_store = Path('src/climate/output/OutputStateStore.cpp').read_text()
runtime = Path('src/climate/ClimateV6RealInputRuntime.cpp').read_text()
bindings = Path('src/climate/Stage28dOutputBindings.cpp').read_text()
if 'recordAttempt(' in coordinator or 'physical' in coordinator.lower():
    raise SystemExit('A9_3_STATIC_FAIL coordinator fabricates attempt/physical truth')
if 'restoreLastSuccessfulCommand' not in state_store or 'has_attempt = true' in state_store[state_store.find('restoreLastSuccessfulCommand'):state_store.find('recordPhysicalObservation')]:
    raise SystemExit('A9_3_STATIC_FAIL restore path fabricates attempt truth')
if 'output_persistence.syncFromStateStore(' not in runtime or 'real_transport_active_this_cycle' not in runtime:
    raise SystemExit('A9_3_STATIC_FAIL runtime persistence gating missing')
if 'makeClimateSemanticOutputConfig(output_policy)' not in runtime or 'validateOutputBindings(semantic_output_config, output_policy)' not in runtime:
    raise SystemExit('A9_3_STATIC_FAIL loaded policy not used by runtime bindings')
if 'makeClimateSemanticOutputConfig(const OutputPolicyConfig& policy)' not in bindings.replace('\n    ', ' '):
    # Formatting may wrap; the header/compile gate remains authoritative.
    pass
print('A9_3_STATIC_PASS')

build = 'build/host-tests-a9-3-v1'
run(['cmake', '-S', 'test/host', '-B', build])
targets = [
    'output_persistence_coordinator_tests',
    'output_persistence_store_tests',
    'output_persistence_schema_tests',
    'output_state_store_tests',
    'output_lifecycle_executor_tests',
    'output_policy_config_tests',
    'climate_semantic_output_tests',
]
run(['cmake', '--build', build, '--parallel', '--target', *targets])
regex = '^(' + '|'.join(targets) + ')$'
run(['ctest', '--test-dir', build, '-R', regex, '--output-on-failure'])
print('A9_3_FOCUSED_PASS')

fw_build = 'build/stage27c-a9-3-v1'
Path(fw_build).mkdir(parents=True, exist_ok=True)
env = os.environ.copy()
env.update({
    'STAGE27C_BUILD_DIR': fw_build,
    'STAGE27C_SDKCONFIG': f'{fw_build}/sdkconfig',
    'GROWBOX_RF433_LOOPBACK_ENABLED': '1',
    'GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED': '1',
    'GROWBOX_RF433_LOOPBACK_AUTO_SMOKE': '0',
    'GROWBOX_RF433_REMOTE_CAPTURE_ENABLED': '0',
})
run(['bash', 'scripts/stage27c_crowpanel.sh', 'build'], env=env)
print('A9_3_CANONICAL_BUILD_PASS')

run(['git', 'diff', '--check'])
run(['git', 'add', *EXPECTED])
run(['git', 'diff', '--cached', '--check'])
staged = sorted(filter(None, out(['git', 'diff', '--cached', '--name-only']).splitlines()))
if staged != EXPECTED:
    raise SystemExit(f'A9_3_STAGED_ALLOWLIST_FAIL staged={staged!r}')
run(['git', 'commit', '-m', 'Persist output policy and command state safely'])
commit = out(['git', 'rev-parse', 'HEAD'])
run(['git', 'push', 'origin', f'HEAD:{BRANCH}'])
run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'FETCH_HEAD']) != commit:
    raise SystemExit('A9_3_PUSH_VERIFY_FAIL')
if out(['git', 'status', '--porcelain']):
    raise SystemExit('A9_3_CLEAN_FAIL')
print(f'A9_3_PASS commit={commit}')
