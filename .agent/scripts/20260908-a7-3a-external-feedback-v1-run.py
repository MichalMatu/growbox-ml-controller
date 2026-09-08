import subprocess
from pathlib import Path

EXPECTED = '76886b7224fbdbd4807d09562590585b8e51ed3d'
FILES = sorted([
    'lib/environment_control/src/climate/ClimateControlLoop.h',
    'lib/environment_control/src/climate/ClimateControlLoop.cpp',
    'src/climate/ClimateApplication.h',
    'test/test_climate_control_loop/test_main.cpp',
    'test/test_climate_application_composition/test_main.cpp',
])


def run(cmd: str) -> None:
    print('+', cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)

run('git fetch -q origin mvp/environment-controller')
assert subprocess.check_output('git rev-parse HEAD', shell=True, text=True).strip() == EXPECTED
assert subprocess.check_output('git rev-parse FETCH_HEAD', shell=True, text=True).strip() == EXPECTED
assert not subprocess.check_output('git status --porcelain', shell=True, text=True).strip()
print('A7_3A_IDENTITY_PASS', flush=True)

run('git fetch -q origin agent-control')
run("git show FETCH_HEAD:.agent/scripts/20260908-a7-3a-external-feedback-v1.py > /tmp/a7_3a_edit.py")
run('python3 /tmp/a7_3a_edit.py')
run('git diff --check')
changed = sorted(subprocess.check_output('git diff --name-only', shell=True, text=True).strip().splitlines())
assert changed == FILES, changed

loop_h = Path('lib/environment_control/src/climate/ClimateControlLoop.h').read_text()
loop_cpp = Path('lib/environment_control/src/climate/ClimateControlLoop.cpp').read_text()
app_h = Path('src/climate/ClimateApplication.h').read_text()
assert 'setPreviousExecutionFeedback' in loop_h
assert 'previousForInput()' in loop_cpp
assert 'input.previous = previousForInput();' in loop_cpp
assert 'clearPreviousExecutionFeedback();' in loop_cpp
assert 'setPreviousExecutionFeedback' in app_h
print('A7_3A_STATIC_PASS', flush=True)

build = 'build/host-tests-a7-3a-v1'
targets = [
    'climate_control_loop_tests',
    'climate_runtime_parity_tests',
    'climate_virtual_hil_tests',
    'climate_application_composition_tests',
]
run(f'cmake -S test/host -B {build}')
run(f"cmake --build {build} --parallel --target {' '.join(targets)}")
regex = '^(' + '|'.join(targets) + ')$'
run(f"ctest --test-dir {build} -R '{regex}' --output-on-failure")
print('A7_3A_FOCUSED_PASS', flush=True)

run('git diff --check')
run('git add ' + ' '.join(FILES))
run('git diff --cached --check')
run("git commit -m 'Allow external climate execution feedback'")
new = subprocess.check_output('git rev-parse HEAD', shell=True, text=True).strip()
run('git push origin HEAD:mvp/environment-controller')
assert not subprocess.check_output('git status --porcelain', shell=True, text=True).strip()
print(f'A7_3A_PASS commit={new}', flush=True)
