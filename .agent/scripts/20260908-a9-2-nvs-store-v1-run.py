import os
import subprocess
from pathlib import Path

BASE = '7e67aeb32e78095a07920988844d700cb221424d'
BRANCH = 'mvp/environment-controller'
EXPECTED = sorted([
    'src/CMakeLists.txt',
    'src/climate/output/OutputNvsBackend.cpp',
    'src/climate/output/OutputNvsBackend.h',
    'src/climate/output/OutputPersistenceStore.cpp',
    'src/climate/output/OutputPersistenceStore.h',
    'test/host/CMakeLists.txt',
    'test/test_output_persistence_store/test_main.cpp',
])


def run(cmd, env=None):
    print('+', ' '.join(cmd), flush=True)
    subprocess.run(cmd, check=True, env=env)


def out(cmd):
    return subprocess.check_output(cmd, text=True).strip()

run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'HEAD']) != BASE:
    raise SystemExit('A9_2_IDENTITY_FAIL local HEAD mismatch')
if out(['git', 'rev-parse', 'FETCH_HEAD']) != BASE:
    raise SystemExit('A9_2_IDENTITY_FAIL remote branch mismatch')
if out(['git', 'status', '--porcelain']):
    raise SystemExit('A9_2_IDENTITY_FAIL worktree not clean')
print('A9_2_IDENTITY_PASS')

run(['git', 'fetch', '-q', 'origin', 'agent-control'])
Path('/tmp/a9_2_edit.py').write_text(
    out(['git', 'show', 'FETCH_HEAD:.agent/scripts/20260908-a9-2-nvs-store-v1.py']) + '\n')
run(['python3', '/tmp/a9_2_edit.py'])

run(['git', 'add', '-N',
     'src/climate/output/OutputNvsBackend.cpp',
     'src/climate/output/OutputNvsBackend.h',
     'src/climate/output/OutputPersistenceStore.cpp',
     'src/climate/output/OutputPersistenceStore.h',
     'test/test_output_persistence_store/test_main.cpp'])
run(['git', 'diff', '--check'])
changed = sorted(filter(None, out(['git', 'diff', '--name-only']).splitlines()))
if changed != EXPECTED:
    raise SystemExit(f'A9_2_ALLOWLIST_FAIL changed={changed!r}')

nvs_cpp = Path('src/climate/output/OutputNvsBackend.cpp').read_text()
store_cpp = Path('src/climate/output/OutputPersistenceStore.cpp').read_text()
if 'nvs_flash_init' in nvs_cpp or 'nvs_flash_erase' in nvs_cpp or '#include <nvs_flash.h>' in nvs_cpp:
    raise SystemExit('A9_2_STATIC_FAIL output NVS backend owns platform init/erase')
for token in ('nvs_open', 'nvs_get_blob', 'nvs_set_blob', 'nvs_commit', 'nvs_close'):
    if token not in nvs_cpp:
        raise SystemExit(f'A9_2_STATIC_FAIL missing {token}')
if 'decodeOutputPersistence' not in store_cpp or 'encodeOutputPersistence' not in store_cpp:
    raise SystemExit('A9_2_STATIC_FAIL persistence store bypasses schema codec')
if any(path.startswith('src/climate/ClimateV6') or 'BleClimateScanner' in path for path in changed):
    raise SystemExit('A9_2_STATIC_FAIL runtime or BLE init changed')
print('A9_2_STATIC_PASS')

build = 'build/host-tests-a9-2-v1'
run(['cmake', '-S', 'test/host', '-B', build])
targets = ['output_persistence_store_tests', 'output_persistence_schema_tests', 'output_policy_config_tests']
run(['cmake', '--build', build, '--parallel', '--target', *targets])
regex = '^(' + '|'.join(targets) + ')$'
run(['ctest', '--test-dir', build, '-R', regex, '--output-on-failure'])
print('A9_2_FOCUSED_PASS')

fw_build = 'build/stage27c-a9-2-v1'
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
print('A9_2_CANONICAL_BUILD_PASS')

run(['git', 'diff', '--check'])
run(['git', 'add', *EXPECTED])
run(['git', 'diff', '--cached', '--check'])
staged = sorted(filter(None, out(['git', 'diff', '--cached', '--name-only']).splitlines()))
if staged != EXPECTED:
    raise SystemExit(f'A9_2_STAGED_ALLOWLIST_FAIL staged={staged!r}')
run(['git', 'commit', '-m', 'Add NVS output policy store'])
commit = out(['git', 'rev-parse', 'HEAD'])
run(['git', 'push', 'origin', f'HEAD:{BRANCH}'])
run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'FETCH_HEAD']) != commit:
    raise SystemExit('A9_2_PUSH_VERIFY_FAIL')
if out(['git', 'status', '--porcelain']):
    raise SystemExit('A9_2_CLEAN_FAIL')
print(f'A9_2_PASS commit={commit}')
