import subprocess
from pathlib import Path

BASE = '5d56478a24738e54136fd554cbccc0cb05fcd5d1'
BRANCH = 'mvp/environment-controller'
AUDIT = Path('docs/OUTPUT_EXECUTION_ARCHITECTURE_R5_AUDIT.md')
HOST_DIR = Path('build/host-r5-output-audit')


def run(cmd):
    print('+', ' '.join(str(x) for x in cmd), flush=True)
    subprocess.run([str(x) for x in cmd], check=True)


def out(cmd):
    return subprocess.check_output([str(x) for x in cmd], text=True).strip()


run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'HEAD']) != BASE:
    raise SystemExit('R5_IDENTITY_FAIL local HEAD mismatch')
if out(['git', 'rev-parse', 'FETCH_HEAD']) != BASE:
    raise SystemExit('R5_IDENTITY_FAIL remote branch mismatch')
if out(['git', 'status', '--porcelain']):
    raise SystemExit('R5_IDENTITY_FAIL worktree not clean')
print('R5_IDENTITY_PASS')

# Final architecture invariant: no configured-output TX owner outside the
# dedicated transport/supervisor/lifecycle/maintenance boundaries.
run(['python3', 'scripts/check_output_rf_ownership.py'])
py = '.venv/bin/python' if Path('.venv/bin/python').exists() else 'python3'
run([py, '-m', 'pytest', 'tests/test_output_execution_ownership.py', '-q'])

# Focused architecture behavior only. This is intentionally not the A12 full gate.
run(['cmake', '-S', 'test/host', '-B', str(HOST_DIR)])
targets = [
    'output_supervisor_resolver_tests',
    'output_supervisor_executor_tests',
    'output_supervisor_lifecycle_tests',
    'output_lifecycle_executor_tests',
    'output_runtime_lifecycle_control_tests',
    'output_automation_control_tests',
    'output_manual_control_tests',
    'output_maintenance_control_tests',
    'output_state_store_tests',
    'output_execution_telemetry_tests',
    'climate_output_supervisor_sink_tests',
    'output_persistence_coordinator_tests',
]
run(['cmake', '--build', str(HOST_DIR), '--parallel', '--target', *targets])
regex = '^(' + '|'.join(targets) + ')$'
run(['ctest', '--test-dir', str(HOST_DIR), '-R', regex, '--output-on-failure'])

runtime = Path('src/climate/ClimateV6RealInputRuntime.cpp').read_text()
cmake = Path('src/CMakeLists.txt').read_text()
state_store = Path('src/climate/output/OutputStateStore.cpp').read_text()
resolver = Path('src/climate/output/OutputSupervisorResolver.cpp').read_text()
executor = Path('src/climate/output/OutputSupervisorExecutor.cpp').read_text()
lifecycle = Path('src/climate/output/OutputLifecycleExecutor.cpp').read_text()
maintenance = Path('src/climate/output/OutputMaintenanceControl.cpp').read_text()
maintenance_transport = Path('src/climate/runtime/Stage28MaintenanceRfTransport.cpp').read_text()
diagnostics = Path('src/climate/runtime/Stage28RfDiagnostics.cpp').read_text()
stack_defaults = Path('config/idf/sdkconfig.defaults.stage28rf').read_text()

required_runtime = (
    'static RuntimeOutputOwner runtime_output_owner(',
    'runtime_lifecycle.beginBoot(',
    'runtime_lifecycle.requestFault(',
    'runtime_lifecycle.tick(',
    'automation_control.tick(',
    'maintenance_control.tick(',
    'supervisor_sink.setCycleContext(',
    'application.tick(',
    'buildOutputExecutionTelemetry(',
)
for token in required_runtime:
    if token not in runtime:
        raise SystemExit(f'R5_RUNTIME_FAIL missing {token!r}')

for token in (
    'Stage28dRfOutputEndpoint',
    'MappedClimateRoleDriver',
    'SwitchableRoleDriver',
    'ClimateActuatorAdapter',
    'forceSafeStateWithRetries',
    'writeScheduledLight(',
    '.manualTransmit(',
    'rmt_transmit(',
):
    if token in runtime:
        raise SystemExit(f'R5_RUNTIME_FAIL retired/direct owner returned {token!r}')

for token in ('"climate/Stage28dRfOutputEndpoint.cpp"', '"climate/Stage28dBinaryRoleArbiter.cpp"'):
    if token in cmake:
        raise SystemExit(f'R5_CMAKE_FAIL retired production source returned {token!r}')

if 'PhysicalOutputState::Unknown' not in executor or 'transport_.send(command)' not in executor:
    raise SystemExit('R5_EXECUTOR_FAIL normal supervisor truth contract missing')
if 'PhysicalOutputState::Unknown' not in lifecycle or 'transport_.send(step.command)' not in lifecycle:
    raise SystemExit('R5_LIFECYCLE_FAIL lifecycle truth contract missing')
if 'raw_transport_.send(raw_command_)' not in maintenance:
    raise SystemExit('R5_MAINTENANCE_FAIL maintenance transport boundary missing')
for token in ('OutputSource::Maintenance', 'OutputReason::MaintenanceRequest', 'diagnostics_.manualTransmit('):
    if token not in maintenance_transport:
        raise SystemExit(f'R5_MAINTENANCE_FAIL maintenance adapter guard missing {token!r}')
if diagnostics.count('transmitAndReceive(') != 1:
    raise SystemExit('R5_RF_FAIL diagnostics TX surface is not singular')
if 'if (config_.passive_capture)' not in diagnostics or 'capturePassive();' not in diagnostics:
    raise SystemExit('R5_RF_FAIL passive diagnostics RX missing')
if 'CONFIG_ESP_MAIN_TASK_STACK_SIZE=16384' not in stack_defaults:
    raise SystemExit('R5_STACK_FAIL RF main task stack no longer 16 KiB')
if 'recordPhysicalObservation' not in state_store or 'clearPhysicalObservation' not in state_store:
    raise SystemExit('R5_STATE_FAIL independent physical-observation API missing')
if 'SafetyConstraint::ForceOff' not in resolver or 'SafetyConstraint::ForceOn' not in resolver:
    raise SystemExit('R5_SAFETY_FAIL explicit hard-safety resolution missing')

# Record the final read-only architecture audit as a docs-only commit.
if AUDIT.exists():
    raise SystemExit('R5_SCOPE_FAIL audit document already exists')
AUDIT.write_text(f'''# Output Execution Architecture R5 Audit

Status: PASS
Updated: 2026-09-09
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Audited production source HEAD: `{BASE}`

## Purpose

This is the final architecture re-audit after A1-A11. It verifies the implemented
output-execution architecture before A12 stabilization and the single final full
software gate. The audit does not change production C++ and does not use hardware,
serial, flashing, or RF transmission.

## Final production invariant

`OutputSupervisor` is the only normal production owner allowed to execute configured
physical outputs. The explicit `MaintenanceLocked` raw-RF path is a separate,
guarded maintenance capability and is not a normal production output owner.

## Evidence verified

- `scripts/check_output_rf_ownership.py` passes on the audited source SHA.
- The focused supervisor, lifecycle, runtime-lifecycle, automation, manual,
  maintenance, state-store, telemetry, persistence and climate-supervisor host tests pass.
- `runClimateV6RealInputRuntime()` composes a static `RuntimeOutputOwner`; climate,
  schedule and hard-safety data enter the supervisor rather than writing RF directly.
- Boot, recovery and fault containment are supervisor lifecycle operations.
- Normal manual commands are intents; raw RF is reachable only through the
  maintenance adapter and `MaintenanceLocked` control path.
- The low-level RMT transmitter remains singular; diagnostics keeps passive RX and
  its explicit manual TX entry is isolated behind the maintenance adapter.
- Retired `Stage28dRfOutputEndpoint` and `Stage28dBinaryRoleArbiter` compatibility
  sources are not part of production firmware CMake composition.
- `OutputStateStore` keeps command truth separate from independent physical
  observation; RF TX completion does not fabricate physical acknowledgement.
- Execution reports keep physical state `Unknown` without independent feedback.
- Honest output telemetry v2 reports requested/resolved/attempted/transport/last-command
  truth separately from physical observation.
- The initial implementation remains synchronous in the existing main task; no new
  supervisor FreeRTOS task or queue ownership was introduced.
- RF-enabled main-task stack remains `16384` bytes. A11.5 measured the runtime entry
  frame at 32 bytes before and after composition cleanup; long-lived output objects
  moved to static storage, adding 2472 bytes of `.bss` rather than permanent main-stack use.

## Normative amendment closure

R-A1 through R-A13 from `OUTPUT_EXECUTION_IMPLEMENTATION_PLAN_REAUDIT.md` are satisfied:
endpoint identity is unified; one RMT owner remains; RF success is local TX completion;
climate injection and previous-state migration were split; legacy safety copies are
inactive in production; propose/commit semantics are preserved; state store and binary
policy remain distinct; main-loop serialization is retained; NVS ownership is bounded;
maintenance shares the radio only under its lifecycle lock; and the final ownership
guard uses a narrow explicit allowlist.

## Result

No architecture blocker was found. A11 exit criteria are satisfied and the codebase is
ready for A12.1 focused stabilization. Hardware remains deferred until A13.3 explicit
authorization.

**R5 FINAL ARCHITECTURE RE-AUDIT: PASS.**
''')

run(['git', 'add', '-N', str(AUDIT)])
changed = out(['git', 'diff', '--name-only']).splitlines()
if changed != [str(AUDIT)]:
    raise SystemExit(f'R5_SCOPE_FAIL changed={changed!r}')
run(['git', 'diff', '--check'])
run(['git', 'add', str(AUDIT)])
run(['git', 'commit', '-m', 'Record final output architecture re-audit'])
commit = out(['git', 'rev-parse', 'HEAD'])
if out(['git', 'rev-parse', 'HEAD^']) != BASE:
    raise SystemExit('R5_PARENT_FAIL')
run(['git', 'push', 'origin', f'HEAD:{BRANCH}'])
run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'FETCH_HEAD']) != commit:
    raise SystemExit('R5_PUSH_VERIFY_FAIL')
print(f'R5_PASS commit={commit}')
