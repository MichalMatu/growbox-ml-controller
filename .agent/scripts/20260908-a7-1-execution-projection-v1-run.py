import os
import subprocess
from pathlib import Path

EXPECTED = '282d977f8b3d8ca6f062a8eb7660e2f5e9cb2e25'
ALLOW = {
    'src/CMakeLists.txt',
    'src/climate/output/ClimateOutputSupervisorSink.cpp',
    'src/climate/output/OutputExecution.h',
    'src/climate/output/OutputExecutionProjection.cpp',
    'src/climate/output/OutputExecutionProjection.h',
    'test/host/CMakeLists.txt',
    'test/test_output_execution_projection/test_main.cpp',
}


def run(cmd, *, env=None):
    print('+', cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True, env=env)

run('git fetch -q origin mvp/environment-controller')
assert subprocess.check_output('git rev-parse HEAD', shell=True, text=True).strip() == EXPECTED
assert subprocess.check_output('git rev-parse FETCH_HEAD', shell=True, text=True).strip() == EXPECTED
assert not subprocess.check_output('git status --porcelain', shell=True, text=True).strip()
print('A7_1_IDENTITY_PASS', flush=True)

run('git fetch -q origin agent-control')
run("git show FETCH_HEAD:.agent/scripts/20260908-a7-1-execution-projection-v1.py > /tmp/a7_1_edit.py")
run('python3 /tmp/a7_1_edit.py')
run('git add -N src/climate/output/OutputExecutionProjection.cpp src/climate/output/OutputExecutionProjection.h test/test_output_execution_projection/test_main.cpp')
run('git diff --check')
changed = set(subprocess.check_output('git diff --name-only', shell=True, text=True).strip().splitlines())
assert changed == ALLOW, (changed, ALLOW)
text = Path('src/climate/output/OutputExecutionProjection.cpp').read_text()
assert 'state->last_successful_command.state' in text
assert 'state->physical' not in text
assert 'buildExecutedControlProjection' in text
sink = Path('src/climate/output/ClimateOutputSupervisorSink.cpp').read_text()
assert 'buildExecutedControlProjection' in sink
assert 'has_executed_state' in sink
print('A7_1_STATIC_PASS', flush=True)

build = 'build/host-tests-a7-1-v1'
targets = [
    'output_execution_projection_tests',
    'climate_output_supervisor_sink_tests',
    'output_supervisor_executor_tests',
    'output_supervisor_resolver_tests',
    'output_state_store_tests',
    'output_execution_contract_tests',
    'climate_control_loop_tests',
]
run(f'cmake -S test/host -B {build}')
run(f"cmake --build {build} --parallel --target {' '.join(targets)}")
regex = '^(' + '|'.join(targets) + ')$'
run(f"ctest --test-dir {build} -R '{regex}' --output-on-failure")
print('A7_1_FOCUSED_PASS', flush=True)

env = os.environ.copy()
env.update({
    'STAGE27C_BUILD_DIR': 'build/idf-a7-1-v1',
    'STAGE27C_SDKCONFIG': 'build/idf-a7-1-v1/sdkconfig',
    'GROWBOX_RF433_LOOPBACK_ENABLED': '1',
    'GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED': '1',
    'GROWBOX_RF433_LOOPBACK_AUTO_SMOKE': '0',
    'GROWBOX_RF433_REMOTE_CAPTURE_ENABLED': '0',
})
run('bash scripts/stage27c_crowpanel.sh build', env=env)
print('A7_1_CANONICAL_RF_BUILD_PASS', flush=True)

run('git diff --check')
run('git add ' + ' '.join(sorted(ALLOW)))
run('git diff --cached --check')
run("git commit -m 'Add honest climate execution projection'")
new = subprocess.check_output('git rev-parse HEAD', shell=True, text=True).strip()
run('git push origin HEAD:mvp/environment-controller')
assert not subprocess.check_output('git status --porcelain', shell=True, text=True).strip()
print(f'A7_1_PASS commit={new}', flush=True)
