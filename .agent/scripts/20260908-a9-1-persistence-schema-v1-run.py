import subprocess
from pathlib import Path

BASE = '5e716ad7374829ff915ac4b6089dd67851a495be'
BRANCH = 'mvp/environment-controller'
EXPECTED = sorted([
    'src/CMakeLists.txt',
    'src/climate/output/OutputPersistenceSchema.cpp',
    'src/climate/output/OutputPersistenceSchema.h',
    'test/host/CMakeLists.txt',
    'test/test_output_persistence_schema/test_main.cpp',
])


def run(cmd):
    print('+', ' '.join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def out(cmd):
    return subprocess.check_output(cmd, text=True).strip()


run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'HEAD']) != BASE:
    raise SystemExit('A9_1_IDENTITY_FAIL local HEAD mismatch')
if out(['git', 'rev-parse', 'FETCH_HEAD']) != BASE:
    raise SystemExit('A9_1_IDENTITY_FAIL remote branch mismatch')
if out(['git', 'status', '--porcelain']):
    raise SystemExit('A9_1_IDENTITY_FAIL worktree not clean')
print('A9_1_IDENTITY_PASS')

run(['git', 'fetch', '-q', 'origin', 'agent-control'])
Path('/tmp/a9_1_edit.py').write_text(
    out(['git', 'show', 'FETCH_HEAD:.agent/scripts/20260908-a9-1-persistence-schema-v1.py']) + '\n')
run(['python3', '/tmp/a9_1_edit.py'])

run(['git', 'add', '-N',
     'src/climate/output/OutputPersistenceSchema.cpp',
     'src/climate/output/OutputPersistenceSchema.h',
     'test/test_output_persistence_schema/test_main.cpp'])
run(['git', 'diff', '--check'])
changed = sorted(filter(None, out(['git', 'diff', '--name-only']).splitlines()))
if changed != EXPECTED:
    raise SystemExit(f'A9_1_ALLOWLIST_FAIL changed={changed!r}')

header = Path('src/climate/output/OutputPersistenceSchema.h').read_text()
impl = Path('src/climate/output/OutputPersistenceSchema.cpp').read_text()
if 'kOutputPersistenceEncodedSize == 134U' not in header:
    raise SystemExit('A9_1_STATIC_FAIL fixed wire size missing')
if 'PhysicalObservation' in header or 'PhysicalOutputState' in header or 'PhysicalObservation' in impl:
    raise SystemExit('A9_1_STATIC_FAIL physical state leaked into persistence schema')
if 'crc32(' not in impl or 'kOutputPersistenceSchemaVersion' not in header:
    raise SystemExit('A9_1_STATIC_FAIL version/checksum contract missing')
if 'makeSafeOutputPersistenceSnapshot' not in impl:
    raise SystemExit('A9_1_STATIC_FAIL safe-default fallback missing')
print('A9_1_STATIC_PASS')

build = 'build/host-tests-a9-1-v1'
run(['cmake', '-S', 'test/host', '-B', build])
targets = ['output_persistence_schema_tests', 'output_policy_config_tests']
run(['cmake', '--build', build, '--parallel', '--target', *targets])
regex = '^(' + '|'.join(targets) + ')$'
run(['ctest', '--test-dir', build, '-R', regex, '--output-on-failure'])
print('A9_1_FOCUSED_PASS')

run(['git', 'diff', '--check'])
run(['git', 'add', *EXPECTED])
run(['git', 'diff', '--cached', '--check'])
staged = sorted(filter(None, out(['git', 'diff', '--cached', '--name-only']).splitlines()))
if staged != EXPECTED:
    raise SystemExit(f'A9_1_STAGED_ALLOWLIST_FAIL staged={staged!r}')
run(['git', 'commit', '-m', 'Add versioned output policy persistence schema'])
commit = out(['git', 'rev-parse', 'HEAD'])
run(['git', 'push', 'origin', f'HEAD:{BRANCH}'])
run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'FETCH_HEAD']) != commit:
    raise SystemExit('A9_1_PUSH_VERIFY_FAIL')
if out(['git', 'status', '--porcelain']):
    raise SystemExit('A9_1_CLEAN_FAIL')
print(f'A9_1_PASS commit={commit}')
