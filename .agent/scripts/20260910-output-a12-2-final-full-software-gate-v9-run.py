import subprocess

OLD = '1c59f3cfa239abbfbae721247d01d65a39d4bdfc'
NEW = '02208d23f403bca3540dbbd652eb55703a044833'
SOURCE = '.agent/scripts/20260909-output-a12-2-final-full-software-gate-v8-run.py'

script = subprocess.check_output(['git', 'show', f'FETCH_HEAD:{SOURCE}'], text=True)
if script.count(OLD) != 1:
    raise SystemExit(f'A12_2_V9_RUNNER_FAIL expected one candidate SHA occurrence, found={script.count(OLD)}')
script = script.replace(OLD, NEW)
exec(compile(script, SOURCE, 'exec'))
