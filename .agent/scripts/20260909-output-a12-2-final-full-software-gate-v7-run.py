import subprocess

OLD = 'f1b185b6240f3bd1264d8295b988be2a9d39caea'
NEW = 'b5e03a5e73d42579e2cce47f74f9071472981827'
SOURCE = '.agent/scripts/20260909-output-a12-2-final-full-software-gate-v6-run.py'

script = subprocess.check_output(['git', 'show', f'FETCH_HEAD:{SOURCE}'], text=True)
if script.count(OLD) != 1:
    raise SystemExit(f'A12_2_V7_RUNNER_FAIL expected one candidate SHA occurrence, found={script.count(OLD)}')
script = script.replace(OLD, NEW)
exec(compile(script, SOURCE, 'exec'))
