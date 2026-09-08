import subprocess

EXPECTED = '6f12c59036dc531d3aadc397c1946cef66b63e38'
FILES = sorted([
    'lib/environment_control/src/climate/ClimateControlLoop.cpp',
    'lib/environment_control/src/climate/ClimateControlLoop.h',
    'src/climate/output/ClimateOutputSupervisorSink.cpp',
    'src/climate/output/ClimateOutputSupervisorSink.h',
    'test/test_climate_control_loop/test_main.cpp',
    'test/test_climate_output_supervisor_sink/test_main.cpp',
])


def run(cmd: str) -> None:
    print('+', cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)

run('git fetch -q origin mvp/environment-controller')
assert subprocess.check_output('git rev-parse HEAD', shell=True, text=True).strip() == EXPECTED
assert subprocess.check_output('git rev-parse FETCH_HEAD', shell=True, text=True).strip() == EXPECTED
assert not subprocess.check_output('git status --porcelain', shell=True, text=True).strip()
print('A7_3B_IDENTITY_PASS', flush=True)

run('git fetch -q origin agent-control')
run("git show FETCH_HEAD:.agent/scripts/20260908-a7-3b-supervisor-previous-v1.py > /tmp/a7_3b_edit.py")
run('python3 /tmp/a7_3b_edit.py')
run('git diff --check')
changed = sorted(subprocess.check_output('git diff --name-only', shell=True, text=True).strip().splitlines())
assert changed == FILES, changed
assert 'applyAndReportExecution' in open('lib/environment_control/src/climate/ClimateControlLoop.h').read()
assert 'setPreviousExecutionFeedback(execution)' in open('lib/environment_control/src/climate/ClimateControlLoop.cpp').read()
sink_cpp = open('src/climate/output/ClimateOutputSupervisorSink.cpp').read()
assert 'ClimateExecutionKnownAll' in sink_cpp
assert 'PhysicalOutputState' not in sink_cpp
assert 'ClimateV6RealInputRuntime.cpp' not in changed
print('A7_3B_STATIC_PASS', flush=True)

build = 'build/host-tests-a7-3b-v1'
targets = [
    'climate_output_supervisor_sink_tests',
    'output_execution_projection_tests',
    'climate_control_loop_tests',
    'climate_application_composition_tests',
    'climate_fault_soak_tests',
    'climate_runtime_parity_tests',
    'climate_virtual_hil_tests',
]
run(f'cmake -S test/host -B {build}')
run(f"cmake --build {build} --parallel --target {' '.join(targets)}")
regex = '^(' + '|'.join(targets) + ')$'
run(f"ctest --test-dir {build} -R '{regex}' --output-on-failure")
print('A7_3B_FOCUSED_PASS', flush=True)

fw = 'build/stage27c-a7-3b-v1'
cmd = (
    f'STAGE27C_BUILD_DIR={fw} STAGE27C_SDKCONFIG={fw}/sdkconfig '
    'GROWBOX_RF433_LOOPBACK_ENABLED=1 GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=1 '
    'GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0 GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0 '
    'bash scripts/stage27c_crowpanel.sh build'
)
run(cmd)
print('A7_3B_FIRMWARE_BUILD_PASS', flush=True)

run('git diff --check')
changed = sorted(subprocess.check_output('git diff --name-only', shell=True, text=True).strip().splitlines())
assert changed == FILES, changed
run('git add ' + ' '.join(FILES))
run('git diff --cached --check')
run("git commit -m 'Use supervisor projection as climate previous state'")
new = subprocess.check_output('git rev-parse HEAD', shell=True, text=True).strip()
run('git push origin HEAD:mvp/environment-controller')
assert not subprocess.check_output('git status --porcelain', shell=True, text=True).strip()
print(f'A7_3B_PASS commit={new}', flush=True)
