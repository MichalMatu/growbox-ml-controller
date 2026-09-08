import shutil
import subprocess
from pathlib import Path

BASE = '578f902ce43cdb3631798ec7e0a6341082c50a49'
BRANCH = 'mvp/environment-controller'
HOST_DIR = Path('build/host-a12-1-output-stabilization')

TARGETS = [
    'output_execution_contract_tests',
    'output_intents_tests',
    'output_types_tests',
    'rf433_protocol_tests',
    'rf433_output_transport_tests',
    'output_state_store_tests',
    'binary_actuator_policy_tests',
    'stage28d_lamp_safety_tests',
    'stage27_schedule_intent_tests',
    'stage28d_output_intent_parity_tests',
    'output_supervisor_resolver_tests',
    'output_supervisor_executor_tests',
    'output_supervisor_lifecycle_tests',
    'output_lifecycle_executor_tests',
    'output_runtime_lifecycle_control_tests',
    'output_automation_control_tests',
    'output_manual_control_tests',
    'output_maintenance_control_tests',
    'climate_output_supervisor_sink_tests',
    'output_execution_projection_tests',
    'climate_control_loop_tests',
    'climate_application_composition_tests',
    'climate_runtime_parity_tests',
    'climate_virtual_hil_tests',
    'climate_fault_soak_tests',
    'output_persistence_schema_tests',
    'output_persistence_store_tests',
    'output_persistence_coordinator_tests',
    'stage28_service_console_tests',
    'output_execution_telemetry_tests',
    'stage27_telemetry_tests',
]


def run(cmd):
    print('+', ' '.join(str(x) for x in cmd), flush=True)
    subprocess.run([str(x) for x in cmd], check=True)


def out(cmd):
    return subprocess.check_output([str(x) for x in cmd], text=True).strip()


run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'HEAD']) != BASE:
    raise SystemExit('A12_1_IDENTITY_FAIL local HEAD mismatch')
if out(['git', 'rev-parse', 'FETCH_HEAD']) != BASE:
    raise SystemExit('A12_1_IDENTITY_FAIL remote branch mismatch')
if out(['git', 'status', '--porcelain']):
    raise SystemExit('A12_1_IDENTITY_FAIL worktree not clean')
print('A12_1_IDENTITY_PASS')

run(['git', 'diff', '--check'])
run(['python3', 'scripts/check_output_rf_ownership.py'])
py = '.venv/bin/python' if Path('.venv/bin/python').exists() else 'python3'
run([py, '-m', 'pytest', 'tests/test_output_execution_ownership.py', '-q'])

shutil.rmtree(HOST_DIR, ignore_errors=True)
run(['cmake', '-S', 'test/host', '-B', HOST_DIR])
run(['cmake', '--build', HOST_DIR, '--parallel', '--target', *TARGETS])
regex = '^(' + '|'.join(TARGETS) + ')$'
run(['ctest', '--test-dir', HOST_DIR, '--output-on-failure', '-R', regex])

if out(['git', 'status', '--porcelain']):
    raise SystemExit('A12_1_CLEAN_FAIL focused sweep changed tracked worktree')
run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'FETCH_HEAD']) != BASE:
    raise SystemExit('A12_1_REMOTE_MOVED_FAIL')

print(f'A12_1_PASS sha={BASE} focused_targets={len(TARGETS)} no_commit=1 hardware_started=0')
