import subprocess

EXPECTED = '34ed66f92c7b11aa4038f34ddcbf63a38da93cff'
FILES = [
    'lib/environment_control/src/climate/ClimateTypes.h',
    'lib/environment_control/src/climate/ClimateRuntimeController.h',
    'lib/environment_control/src/climate/ClimateRuntimeController.cpp',
    'lib/environment_control/src/climate/ClimateControlLoop.cpp',
    'test/test_climate_v6/test_main.cpp',
]


def run(cmd: str) -> None:
    print('+', cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)

run('git fetch -q origin mvp/environment-controller')
assert subprocess.check_output('git rev-parse HEAD', shell=True, text=True).strip() == EXPECTED
assert subprocess.check_output('git rev-parse FETCH_HEAD', shell=True, text=True).strip() == EXPECTED
assert not subprocess.check_output('git status --porcelain', shell=True, text=True).strip()
print('A7_2_IDENTITY_PASS', flush=True)

run('git fetch -q origin agent-control')
run("git show FETCH_HEAD:.agent/scripts/20260908-a7-2-estimator-reconcile-v1.py > /tmp/a7_2_edit.py")
run('python3 /tmp/a7_2_edit.py')
run('git diff --check')
changed = subprocess.check_output('git diff --name-only', shell=True, text=True).strip().splitlines()
assert changed == FILES, changed
print('A7_2_STATIC_PASS', flush=True)

build = 'build/host-tests-a7-2-v1'
targets = [
    'climate_v6_tests',
    'climate_runtime_parity_tests',
    'climate_virtual_hil_tests',
    'climate_control_loop_tests',
]
run(f'cmake -S test/host -B {build}')
run(f"cmake --build {build} --parallel --target {' '.join(targets)}")
regex = '^(' + '|'.join(targets) + ')$'
run(f"ctest --test-dir {build} -R '{regex}' --output-on-failure")
print('A7_2_FOCUSED_PASS', flush=True)

run('git diff --check')
run('git add ' + ' '.join(FILES))
run('git diff --cached --check')
run("git commit -m 'Reconcile climate estimator from execution reports'")
new = subprocess.check_output('git rev-parse HEAD', shell=True, text=True).strip()
run('git push origin HEAD:mvp/environment-controller')
assert not subprocess.check_output('git status --porcelain', shell=True, text=True).strip()
print(f'A7_2_PASS commit={new}', flush=True)
