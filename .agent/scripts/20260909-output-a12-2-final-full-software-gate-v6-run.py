import os
import shutil
import stat
import subprocess
from pathlib import Path

OLD = '578f902ce43cdb3631798ec7e0a6341082c50a49'
NEW = 'f1b185b6240f3bd1264d8295b988be2a9d39caea'
SOURCE = '.agent/scripts/20260909-output-a12-2-final-full-software-gate-v3-run.py'
WRAP_DIR = Path('/tmp/a12-v6-bin')

real_cmake = shutil.which('cmake')
real_ninja = shutil.which('ninja')
if not real_cmake:
    raise SystemExit('A12_2_V6_RUNNER_FAIL cmake not found')

WRAP_DIR.mkdir(parents=True, exist_ok=True)
cmake_wrapper = WRAP_DIR / 'cmake'
cmake_wrapper.write_text(
    '#!/usr/bin/env python3\n'
    'import os, sys\n'
    f'REAL = {real_cmake!r}\n'
    'args = sys.argv[1:]\n'
    'out = []\n'
    'i = 0\n'
    'while i < len(args):\n'
    '    arg = args[i]\n'
    '    out.append(arg)\n'
    '    if arg == "--parallel":\n'
    '        if i + 1 >= len(args) or args[i + 1].startswith("-") or not args[i + 1].isdigit():\n'
    '            out.append("2")\n'
    '    i += 1\n'
    'os.execv(REAL, [REAL, *out])\n'
)
cmake_wrapper.chmod(cmake_wrapper.stat().st_mode | stat.S_IXUSR)

if real_ninja:
    ninja_wrapper = WRAP_DIR / 'ninja'
    ninja_wrapper.write_text(
        '#!/usr/bin/env python3\n'
        'import os, sys\n'
        f'REAL = {real_ninja!r}\n'
        'args = sys.argv[1:]\n'
        'has_jobs = any(a == "-j" or a.startswith("-j") or a == "--jobs" or a.startswith("--jobs=") for a in args)\n'
        'if not has_jobs:\n'
        '    args = ["-j2", *args]\n'
        'os.execv(REAL, [REAL, *args])\n'
    )
    ninja_wrapper.chmod(ninja_wrapper.stat().st_mode | stat.S_IXUSR)

os.environ['PATH'] = str(WRAP_DIR) + os.pathsep + os.environ.get('PATH', '')
os.environ['CMAKE_BUILD_PARALLEL_LEVEL'] = '2'
os.environ['NINJAFLAGS'] = '-j2'

script = subprocess.check_output(['git', 'show', f'FETCH_HEAD:{SOURCE}'], text=True)
if script.count(OLD) != 1:
    raise SystemExit(f'A12_2_V6_RUNNER_FAIL expected one base SHA occurrence, found={script.count(OLD)}')
script = script.replace(OLD, NEW)
exec(compile(script, SOURCE, 'exec'))
