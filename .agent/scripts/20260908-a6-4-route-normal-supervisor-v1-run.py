import os
import subprocess
from pathlib import Path

EXPECTED = '9c48a767a68ad2b85485cabfaf32d04a10b38ff9'
TARGET = 'src/climate/ClimateV6RealInputRuntime.cpp'


def run(cmd, *, env=None):
    print('+', cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True, env=env)

run('git fetch -q origin mvp/environment-controller')
assert subprocess.check_output('git rev-parse HEAD', shell=True, text=True).strip() == EXPECTED
assert subprocess.check_output('git rev-parse FETCH_HEAD', shell=True, text=True).strip() == EXPECTED
assert not subprocess.check_output('git status --porcelain', shell=True, text=True).strip()
print('A6_4_IDENTITY_PASS', flush=True)

run('git fetch -q origin agent-control')
run("git show FETCH_HEAD:.agent/scripts/20260908-a6-4-route-normal-supervisor-v1.py > /tmp/a6_4_edit.py")
run('python3 /tmp/a6_4_edit.py')
run(f'git add -N {TARGET}')
run('git diff --check')
changed = subprocess.check_output('git diff --name-only', shell=True, text=True).strip().splitlines()
assert changed == [TARGET], changed
text = Path(TARGET).read_text()
assert 'ClimateOutputSupervisorSink supervisor_sink' in text
assert 'OutputSupervisorResolver supervisor_resolver' in text
assert 'OutputSupervisorExecutor supervisor_executor' in text
assert 'buildStage27ScheduleIntent' in text
assert 'buildLampSafetyEnvelope' in text
assert 'ClimateApplication application(runtime_controller, composite, supervisor_sink);' in text
assert 'supervisor_sink.setCycleContext(supervisor_context);' in text
assert 'Stage28dBinaryRoleArbiter binary_arbiter' not in text
assert 'binary_arbiter.setSafetyForceExhaust' not in text
assert text.count('physical_endpoint.setSafetyForceExhaust(') == 1
assert text.count('physical_endpoint.writeScheduledLight(') == 1
print('A6_4_STATIC_PASS', flush=True)

build = 'build/host-tests-a6-4-v1'
targets = [
    'output_supervisor_resolver_tests',
    'output_supervisor_executor_tests',
    'climate_output_supervisor_sink_tests',
    'climate_application_composition_tests',
    'climate_control_loop_tests',
    'stage27_schedule_intent_tests',
    'stage28d_output_intent_parity_tests',
    'stage28d_lamp_safety_tests',
    'binary_actuator_policy_tests',
    'stage28d_rf_output_endpoint_tests',
    'rf433_output_transport_tests',
]
run(f'cmake -S test/host -B {build}')
run(f"cmake --build {build} --parallel --target {' '.join(targets)}")
regex = '^(' + '|'.join(targets) + ')$'
run(f"ctest --test-dir {build} -R '{regex}' --output-on-failure")
print('A6_4_FOCUSED_PASS', flush=True)

env = os.environ.copy()
env.update({
    'STAGE27C_BUILD_DIR': 'build/idf-a6-4-v1',
    'STAGE27C_SDKCONFIG': 'build/idf-a6-4-v1/sdkconfig',
    'GROWBOX_RF433_LOOPBACK_ENABLED': '1',
    'GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED': '1',
    'GROWBOX_RF433_LOOPBACK_AUTO_SMOKE': '0',
    'GROWBOX_RF433_REMOTE_CAPTURE_ENABLED': '0',
})
run('bash scripts/stage27c_crowpanel.sh build', env=env)
print('A6_4_CANONICAL_RF_BUILD_PASS', flush=True)

run('git diff --check')
run(f'git add {TARGET}')
run('git diff --cached --check')
run("git commit -m 'Route normal outputs through output supervisor'")
new = subprocess.check_output('git rev-parse HEAD', shell=True, text=True).strip()
run('git push origin HEAD:mvp/environment-controller')
assert not subprocess.check_output('git status --porcelain', shell=True, text=True).strip()
print(f'A6_4_PASS commit={new}', flush=True)
