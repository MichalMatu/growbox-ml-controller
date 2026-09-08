import subprocess

OLD = 'b5e03a5e73d42579e2cce47f74f9071472981827'
NEW = '1c59f3cfa239abbfbae721247d01d65a39d4bdfc'
SOURCE = '.agent/scripts/20260909-output-a12-2-final-full-software-gate-v7-run.py'

script = subprocess.check_output(['git', 'show', f'FETCH_HEAD:{SOURCE}'], text=True)
if script.count(OLD) != 1:
    raise SystemExit(f'A12_2_V8_RUNNER_FAIL expected one candidate SHA occurrence, found={script.count(OLD)}')
script = script.replace(OLD, NEW)
exec(compile(script, SOURCE, 'exec'))
