import subprocess

EXPECTED = '9038f6f3b1a9b9179cfa408e430dd610076c82ca'
FILES = [
    'src/CMakeLists.txt',
    'src/climate/output/OutputLifecycleExecutor.cpp',
    'src/climate/output/OutputLifecycleExecutor.h',
    'test/host/CMakeLists.txt',
    'test/test_output_lifecycle_executor/test_main.cpp',
]


def run(cmd: str) -> None:
    print('+', cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)

run('git fetch -q origin mvp/environment-controller')
assert subprocess.check_output('git rev-parse HEAD', shell=True, text=True).strip() == EXPECTED
assert subprocess.check_output('git rev-parse FETCH_HEAD', shell=True, text=True).strip() == EXPECTED
assert not subprocess.check_output('git status --porcelain', shell=True, text=True).strip()
print('A8_3_IDENTITY_PASS', flush=True)

run('git fetch -q origin agent-control')
run("git show FETCH_HEAD:.agent/scripts/20260908-a8-3-lifecycle-executor-v1.py > /tmp/a8_3_edit.py")
run('python3 /tmp/a8_3_edit.py')
run('git add -N src/climate/output/OutputLifecycleExecutor.cpp src/climate/output/OutputLifecycleExecutor.h test/test_output_lifecycle_executor/test_main.cpp')
run('git diff --check')
changed = subprocess.check_output('git diff --name-only', shell=True, text=True).strip().splitlines()
assert sorted(changed) == sorted(FILES), changed
text = open('src/climate/output/OutputLifecycleExecutor.cpp', encoding='utf-8').read()
assert 'sleep(' not in text and 'vTaskDelay' not in text and 'delay(' not in text
assert 'PhysicalOutputState::Unknown' in text
assert 'last_successful_command' in text
assert 'synchronize(command.state' in text
print('A8_3_STATIC_PASS', flush=True)

build = 'build/host-tests-a8-3-v1'
targets = [
    'output_lifecycle_executor_tests',
    'output_supervisor_lifecycle_tests',
    'output_policy_config_tests',
    'output_supervisor_resolver_tests',
    'output_supervisor_executor_tests',
    'output_state_store_tests',
    'binary_actuator_policy_tests',
]
run(f'cmake -S test/host -B {build}')
run(f"cmake --build {build} --parallel --target {' '.join(targets)}")
regex = '^(' + '|'.join(targets) + ')$'
run(f"ctest --test-dir {build} -R '{regex}' --output-on-failure")
print('A8_3_FOCUSED_PASS', flush=True)

fw = 'build/stage27c-a8-3-v1'
sdk = fw + '/sdkconfig'
run(f'rm -rf {fw}')
run('STAGE27C_BUILD_DIR=' + fw + ' STAGE27C_SDKCONFIG=' + sdk +
    ' GROWBOX_RF433_LOOPBACK_ENABLED=1 GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=1'
    ' GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0 GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0'
    ' bash scripts/stage27c_crowpanel.sh build')
print('A8_3_CANONICAL_BUILD_PASS', flush=True)

run('git diff --check')
run('git add ' + ' '.join(FILES))
run('git diff --cached --check')
staged = subprocess.check_output('git diff --cached --name-only', shell=True, text=True).strip().splitlines()
assert sorted(staged) == sorted(FILES), staged
run("git commit -m 'Execute lifecycle output policy non-blockingly'")
new = subprocess.check_output('git rev-parse HEAD', shell=True, text=True).strip()
run('git push origin HEAD:mvp/environment-controller')
assert not subprocess.check_output('git status --porcelain', shell=True, text=True).strip()
print(f'A8_3_PASS commit={new}', flush=True)
