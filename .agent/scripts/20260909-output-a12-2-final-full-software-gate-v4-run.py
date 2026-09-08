import subprocess

OLD = '578f902ce43cdb3631798ec7e0a6341082c50a49'
NEW = 'f1b185b6240f3bd1264d8295b988be2a9d39caea'
SOURCE = '.agent/scripts/20260909-output-a12-2-final-full-software-gate-v3-run.py'

script = subprocess.check_output(['git', 'show', f'FETCH_HEAD:{SOURCE}'], text=True)
if script.count(OLD) != 1:
    raise SystemExit(f'A12_2_V4_RUNNER_FAIL expected one base SHA occurrence, found={script.count(OLD)}')
script = script.replace(OLD, NEW)
exec(compile(script, SOURCE, 'exec'))
