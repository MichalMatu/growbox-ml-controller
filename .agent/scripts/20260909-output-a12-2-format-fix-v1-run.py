import subprocess
from pathlib import Path

BASE = '578f902ce43cdb3631798ec7e0a6341082c50a49'
BRANCH = 'mvp/environment-controller'


def run(cmd, check=True):
    print('+', ' '.join(str(x) for x in cmd), flush=True)
    return subprocess.run([str(x) for x in cmd], check=check)


def out(cmd):
    return subprocess.check_output([str(x) for x in cmd], text=True).strip()


run(['git', 'fetch', '-q', 'origin', BRANCH])
remote = out(['git', 'rev-parse', 'FETCH_HEAD'])
if remote != BASE:
    raise SystemExit(f'A12_2_FORMAT_FIX_IDENTITY_FAIL remote={remote} expected={BASE}')
run(['git', 'reset', '--hard', BASE])
run(['git', 'clean', '-fd'])
if out(['git', 'status', '--porcelain']):
    raise SystemExit('A12_2_FORMAT_FIX_CLEAN_FAIL after reset')

passed = False
for attempt in range(1, 4):
    print(f'A12_2_FORMAT_FIX_PRECOMMIT_ATTEMPT attempt={attempt}', flush=True)
    result = run(['.venv/bin/pre-commit', 'run', '--all-files'], check=False)
    changed = out(['git', 'diff', '--name-only'])
    print('A12_2_FORMAT_FIX_CHANGED_FILES\n' + changed, flush=True)
    if result.returncode == 0:
        passed = True
        break
if not passed:
    raise SystemExit('A12_2_FORMAT_FIX_PRECOMMIT_FAIL after 3 attempts')

run(['git', 'diff', '--check'])
run(['bash', 'scripts/check_schema.sh'])
run(['.venv/bin/python', '-m', 'py_compile', 'scripts/growbox_log_pull.py'])

changed = [line for line in out(['git', 'diff', '--name-only']).splitlines() if line]
if not changed:
    raise SystemExit('A12_2_FORMAT_FIX_NO_CHANGES')
print('A12_2_FORMAT_FIX_FINAL_FILES ' + ' '.join(changed), flush=True)

run(['git', 'add', '--all'])
run(['git', 'commit', '-m', 'Fix repository formatting gate'])
new_sha = out(['git', 'rev-parse', 'HEAD'])
run(['git', 'push', 'origin', f'HEAD:{BRANCH}'])
run(['git', 'fetch', '-q', 'origin', BRANCH])
remote_after = out(['git', 'rev-parse', 'FETCH_HEAD'])
if remote_after != new_sha:
    raise SystemExit(f'A12_2_FORMAT_FIX_PUSH_FAIL local={new_sha} remote={remote_after}')
if out(['git', 'status', '--porcelain']):
    raise SystemExit('A12_2_FORMAT_FIX_DIRTY_AFTER_COMMIT')
print(f'A12_2_FORMAT_FIX_PASS sha={new_sha} precommit=PASS schema=PASS py_compile=PASS hardware_started=0')
