import os
import re
import subprocess
from pathlib import Path

BASE = 'a207ab0c09196eeae42036cc391ed0aab0dae1db'
BRANCH = 'mvp/environment-controller'
EXPECTED = sorted([
    'src/CMakeLists.txt',
    'src/climate/ClimateV6RealInputRuntime.cpp',
    'src/climate/output/ClimateOutputSupervisorSink.cpp',
    'src/climate/output/ClimateOutputSupervisorSink.h',
    'test/test_climate_output_supervisor_sink/test_main.cpp',
])


def run(cmd, env=None):
    print('+', ' '.join(cmd), flush=True)
    subprocess.run(cmd, check=True, env=env)


def out(cmd):
    return subprocess.check_output(cmd, text=True).strip()


def replace_once(path, old, new):
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{path}: expected one replacement, found {count}: {old[:120]!r}')
    p.write_text(text.replace(old, new, 1))


def sub_once(path, pattern, repl, flags=0):
    p = Path(path)
    text = p.read_text()
    new, count = re.subn(pattern, repl, text, count=1, flags=flags)
    if count != 1:
        raise SystemExit(f'{path}: expected one regex replacement, found {count}: {pattern[:120]!r}')
    p.write_text(new)


run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'HEAD']) != BASE:
    raise SystemExit('A11_2_IDENTITY_FAIL local HEAD mismatch')
if out(['git', 'rev-parse', 'FETCH_HEAD']) != BASE:
    raise SystemExit('A11_2_IDENTITY_FAIL remote branch mismatch')
if out(['git', 'status', '--porcelain']):
    raise SystemExit('A11_2_IDENTITY_FAIL worktree not clean')
print('A11_2_IDENTITY_PASS')

# Firmware no longer compiles legacy execution-owner implementations. Host tests
# still compile them directly as migration compatibility evidence.
cmake = Path('src/CMakeLists.txt')
text = cmake.read_text()
for line in [
    '    "climate/Stage28dBinaryRoleArbiter.cpp"\n',
    '    "climate/Stage28dRfOutputEndpoint.cpp"\n',
]:
    if text.count(line) != 1:
        raise SystemExit(f'src/CMakeLists.txt: expected one legacy owner source, found {text.count(line)}: {line!r}')
    text = text.replace(line, '', 1)
cmake.write_text(text)

runtime_path = 'src/climate/ClimateV6RealInputRuntime.cpp'
runtime = Path(runtime_path)
text = runtime.read_text()
for line in [
    '#include "climate/Stage28dRfOutputEndpoint.h"\n',
    '#include "climate/Stage28dThermalTestSequence.h"\n',
    "constexpr unsigned kSafeStateAttempts = 3U;\n",
]:
    if text.count(line) != 1:
        raise SystemExit(f'{runtime_path}: expected one removable line, found {text.count(line)}: {line!r}')
    text = text.replace(line, '', 1)
runtime.write_text(text)

sub_once(
    runtime_path,
    r'class SwitchableRoleDriver final : public ClimateRoleDriver \{.*?\n\};\n\n(?=class RuntimeOutputTransport)',
    '',
    flags=re.S,
)
sub_once(
    runtime_path,
    r'void synchronizeSupervisorPoliciesSafeOff\(.*?\n\}\n\nbool forceSafeStateWithRetries\(.*?\n\}\n\n(?=runtime::Stage27PhysicalOutputSnapshot)',
    '',
    flags=re.S,
)
replace_once(
    runtime_path,
    '''  stage28d::ThermalTestSequence& thermalTestSequence() noexcept {\n    return thermal_test_sequence_;\n  }\n\n''',
    '',
)
replace_once(runtime_path, '  stage28d::ThermalTestSequence thermal_test_sequence_;\n', '')

sub_once(
    runtime_path,
    r'''  bool real_transport_available =\n      GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED != 0 && rf_ready && output_bindings_valid;\n  stage28d::Stage28dRfOutputEndpoint physical_endpoint\(.*?\n\n  if \(GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED != 0 && !real_output_ready\) \{\n    ESP_LOGE\(kTag, "Gate6 thermal sequence requested but real outputs are not safely armed"\);\n  \}\n\n''',
    '''  bool real_transport_available =\n      GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED != 0 && rf_ready && output_bindings_valid;\n\n  // The pre-supervisor Gate6 qualification path was a direct configured-output\n  // writer. Keep the build knob fail-closed until A13 defines the replacement\n  // supervisor-owned hardware qualification contract.\n  if (GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED != 0) {\n    ESP_LOGW(kTag,\n             "Legacy Gate6 thermal qualification is retired; locking real transport until A13");\n    real_transport_available = false;\n  }\n\n  bool real_output_ready = false;\n  if (GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED != 0 && !real_transport_available) {\n    ESP_LOGE(kTag, "Real-output transport unavailable; automatic outputs remain fake-locked");\n  }\n\n''',
    flags=re.S,
)

sub_once(
    runtime_path,
    r'''  // Legacy role transport remains only as an exceptional fail-safe path until A11\.\n  // Normal climate and schedule execution below is supervisor-owned\.\n  runtime::LockedFakeRoleDriver fake_output_driver;\n  MappedClimateRoleDriver mapped_output_driver\(semantic_output_config, physical_endpoint\);\n  SwitchableRoleDriver fail_safe_output_driver\(fake_output_driver, mapped_output_driver,\n                                                real_output_ready\);\n  ClimateActuatorAdapter fail_safe_actuator_adapter\(fail_safe_output_driver\);\n\n''',
    '',
)
replace_once(
    runtime_path,
    '''  ClimateOutputSupervisorSink supervisor_sink(semantic_output_config, supervisor_resolver,\n                                              supervisor_executor, output_state_store,\n                                              &fail_safe_actuator_adapter);\n''',
    '''  ClimateOutputSupervisorSink supervisor_sink(semantic_output_config, supervisor_resolver,\n                                              supervisor_executor, output_state_store);\n''',
)
replace_once(runtime_path, '    fail_safe_output_driver.disableReal();\n', '')
replace_once(
    runtime_path,
    '''  auto& thermal_test_sequence = runtime_control_owner.thermalTestSequence();\n  const std::uint64_t thermal_test_started_ms = monotonicMilliseconds();\n  stage28d::ThermalTestPhase last_test_phase = stage28d::ThermalTestPhase::Complete;\n  bool thermal_test_finished_safe = false;\n''',
    '',
)

# Remove the remaining pre-supervisor thermal qualification writer branch. The
# normal supervisor path that followed its else-if becomes the only loop path.
sub_once(
    runtime_path,
    r'''    if \(GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED != 0 && real_output_ready &&\n        !thermal_test_finished_safe\) \{.*?    \} else if \(GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED == 0\) \{\n''',
    '',
    flags=re.S,
)
replace_once(
    runtime_path,
    '''      }\n    }\n    if (output_persistence.valid()) {\n''',
    '''      }\n    if (output_persistence.valid()) {\n''',
)

sub_once(
    runtime_path,
    r'''static_cast<unsigned long>\(physical_endpoint\.transmitCount\(\) \+\n\s+supervisor_transport\.transmitCount\(\)\)''',
    'static_cast<unsigned long>(supervisor_transport.transmitCount())',
)
sub_once(
    runtime_path,
    r'''static_cast<unsigned long>\(physical_endpoint\.transmitErrorCount\(\) \+\n\s+supervisor_transport\.transmitErrorCount\(\)\)''',
    'static_cast<unsigned long>(supervisor_transport.transmitErrorCount())',
)

# Remove the legacy fallback sink API. Fail-safe output resolution now remains
# inside the supervisor boundary.
replace_once(
    'src/climate/output/ClimateOutputSupervisorSink.h',
    '''      ::growbox::app::output::OutputSupervisorExecutor& executor,\n      ::growbox::app::output::OutputStateStore& state_store,\n      ::growbox::climate::ClimateActuatorSink* fail_safe_fallback = nullptr) noexcept;\n''',
    '''      ::growbox::app::output::OutputSupervisorExecutor& executor,\n      ::growbox::app::output::OutputStateStore& state_store) noexcept;\n''',
)
replace_once(
    'src/climate/output/ClimateOutputSupervisorSink.h',
    '  ::growbox::climate::ClimateActuatorSink* fail_safe_fallback_{nullptr};\n',
    '',
)
replace_once(
    'src/climate/output/ClimateOutputSupervisorSink.cpp',
    '''    ::growbox::app::output::OutputSupervisorExecutor& executor,\n    ::growbox::app::output::OutputStateStore& state_store,\n    ::growbox::climate::ClimateActuatorSink* fail_safe_fallback) noexcept\n    : climate_config_(climate_config),\n      config_status_(validateClimateSemanticOutputConfig(climate_config_)), resolver_(resolver),\n      executor_(executor), state_store_(state_store), fail_safe_fallback_(fail_safe_fallback) {}\n''',
    '''    ::growbox::app::output::OutputSupervisorExecutor& executor,\n    ::growbox::app::output::OutputStateStore& state_store) noexcept\n    : climate_config_(climate_config),\n      config_status_(validateClimateSemanticOutputConfig(climate_config_)), resolver_(resolver),\n      executor_(executor), state_store_(state_store) {}\n''',
)
replace_once(
    'src/climate/output/ClimateOutputSupervisorSink.cpp',
    '''bool ClimateOutputSupervisorSink::applyFailSafeOff(std::uint64_t monotonic_ms) noexcept {\n  last_resolution_ = {};\n  last_report_ = {};\n  if (fail_safe_fallback_ == nullptr) {\n    return false;\n  }\n  return fail_safe_fallback_->applyFailSafeOff(monotonic_ms);\n}\n''',
    '''bool ClimateOutputSupervisorSink::applyFailSafeOff(std::uint64_t monotonic_ms) noexcept {\n  using ::growbox::app::output::OutputReason;\n  using ::growbox::app::output::OutputSource;\n  using ::growbox::app::output::SafetyConstraint;\n\n  last_resolution_ = {};\n  last_report_ = {};\n  if (!valid()) {\n    return false;\n  }\n\n  ::growbox::app::output::SafetyEnvelope fail_safe{};\n  fail_safe.metadata.sequence = nextSequence();\n  fail_safe.metadata.monotonic_ms = monotonic_ms;\n  fail_safe.metadata.source = OutputSource::Safety;\n  fail_safe.metadata.reason = OutputReason::FaultContainment;\n\n  std::size_t constraint_count = 0U;\n  for (const auto role : kClimateRoles) {\n    const std::size_t role_index = climateRoleIndex(role);\n    if (role_index >= climate_config_.roles.size()) {\n      return false;\n    }\n    const auto& mapping = climate_config_.roles[role_index];\n    if (!mapping.enabled) {\n      continue;\n    }\n    if (constraint_count >= fail_safe.endpoints.size() ||\n        !::growbox::app::output::setSafetyConstraint(\n            fail_safe.endpoints[constraint_count], mapping.endpoint, SafetyConstraint::ForceOff,\n            OutputReason::FaultContainment)) {\n      return false;\n    }\n    ++constraint_count;\n  }\n\n  // Existing hard-safety constraints override the generic climate fail-safe.\n  // This preserves the non-bypassable thermal fan ForceOn / lamp ForceOff rules.\n  for (const auto& hard : context_.safety.endpoints) {\n    if (!::growbox::app::output::safetyConstraintActive(hard)) {\n      continue;\n    }\n    bool replaced = false;\n    for (std::size_t index = 0U; index < constraint_count; ++index) {\n      if (fail_safe.endpoints[index].endpoint == hard.endpoint) {\n        fail_safe.endpoints[index] = hard;\n        replaced = true;\n        break;\n      }\n    }\n    if (!replaced) {\n      if (constraint_count >= fail_safe.endpoints.size()) {\n        return false;\n      }\n      fail_safe.endpoints[constraint_count++] = hard;\n    }\n  }\n\n  ::growbox::app::output::OutputSupervisorCycleInput cycle{};\n  cycle.mode = context_.mode;\n  cycle.monotonic_ms = monotonic_ms;\n  cycle.safety = fail_safe;\n  if (!resolver_.resolve(cycle, state_store_, last_resolution_)) {\n    last_resolution_ = {};\n    return false;\n  }\n  if (!executor_.execute(last_resolution_, monotonic_ms, last_report_)) {\n    last_report_ = {};\n    return false;\n  }\n  return reportTransportCompleted(last_report_);\n}\n''',
)

# Update focused sink tests: remove the legacy fallback test double and prove
# fail-safe execution plus hard-safety precedence through the supervisor.
test_path = 'test/test_climate_output_supervisor_sink/test_main.cpp'
sub_once(
    test_path,
    r'class RecordingFailSafeSink final : public climate::ClimateActuatorSink \{.*?\n\};\n\n',
    '',
    flags=re.S,
)
replace_once(
    test_path,
    '''  RecordingFailSafeSink fallback;\n  climate_io::ClimateOutputSupervisorSink sink(makeClimateConfig(), resolver, executor, store,\n                                                &fallback);\n''',
    '''  climate_io::ClimateOutputSupervisorSink sink(makeClimateConfig(), resolver, executor, store);\n''',
)
sub_once(
    test_path,
    r'''void testExceptionalFailSafeRemainsExplicitLegacyFallbackDebt\(\) \{.*?\n\}\n\n(?=\} // namespace)''',
    r'''void testFailSafeOffExecutesThroughSupervisorOnly() {
  auto fan = makePolicy();
  auto humidifier = makePolicy();
  auto store = makeStore();
  const auto supervisor_config = makeSupervisorConfig(fan, humidifier);
  output::OutputSupervisorResolver resolver(supervisor_config);
  FakeTransport transport;
  output::OutputSupervisorExecutor executor(transport, store, supervisor_config);
  climate_io::ClimateOutputSupervisorSink sink(makeClimateConfig(), resolver, executor, store);
  sink.setCycleContext(scheduleContext(true));

  climate::ClimatePolicyRequest projection{};
  assert(sink.applyAndReport(request(1.0F, 1.0F), 50'000U, projection));
  assert(transport.sent_count == 3U);
  assert(store.find(kLamp)->last_successful_command.state == output::BinaryOutputState::On);

  sink.setCycleContext(scheduleContext(true));
  assert(sink.applyFailSafeOff(50'001U));
  assert(transport.sent_count == 5U);
  assert(sink.lastReport().size == 2U);
  assert(transport.sent[3].endpoint == kFan);
  assert(transport.sent[3].state == output::BinaryOutputState::Off);
  assert(transport.sent[3].source == output::OutputSource::Safety);
  assert(transport.sent[3].reason == output::OutputReason::FaultContainment);
  assert(transport.sent[4].endpoint == kHumidifier);
  assert(transport.sent[4].state == output::BinaryOutputState::Off);
  assert(transport.sent[4].source == output::OutputSource::Safety);
  assert(transport.sent[4].reason == output::OutputReason::FaultContainment);
  assert(store.find(kLamp)->last_successful_command.state == output::BinaryOutputState::On);
  assertPhysicalUnknown(store, kFan);
  assertPhysicalUnknown(store, kHumidifier);
}

void testHardSafetyOverridesSupervisorFailSafeOff() {
  auto fan = makePolicy();
  auto humidifier = makePolicy();
  auto store = makeStore();
  const auto supervisor_config = makeSupervisorConfig(fan, humidifier);
  output::OutputSupervisorResolver resolver(supervisor_config);
  FakeTransport transport;
  output::OutputSupervisorExecutor executor(transport, store, supervisor_config);
  climate_io::ClimateOutputSupervisorSink sink(makeClimateConfig(), resolver, executor, store);
  sink.setCycleContext(scheduleContext(false));

  climate::ClimatePolicyRequest projection{};
  assert(sink.applyAndReport(request(0.0F, 0.0F), 60'000U, projection));
  assert(transport.sent_count == 3U);

  auto context = scheduleContext(false);
  context.safety.metadata.sequence = 91U;
  context.safety.metadata.source = output::OutputSource::Safety;
  context.safety.metadata.reason = output::OutputReason::ThermalSafety;
  assert(output::setSafetyConstraint(context.safety.endpoints[0], kFan,
                                     output::SafetyConstraint::ForceOn,
                                     output::OutputReason::ThermalSafety));
  sink.setCycleContext(context);

  assert(sink.applyFailSafeOff(60'001U));
  assert(transport.sent_count == 4U);
  assert(sink.lastReport().size == 1U);
  assert(transport.sent[3].endpoint == kFan);
  assert(transport.sent[3].state == output::BinaryOutputState::On);
  assert(transport.sent[3].source == output::OutputSource::Safety);
  assert(transport.sent[3].reason == output::OutputReason::ThermalSafety);
  assert(store.find(kHumidifier)->last_successful_command.state == output::BinaryOutputState::Off);
}

''',
    flags=re.S,
)
replace_once(
    test_path,
    '  testExceptionalFailSafeRemainsExplicitLegacyFallbackDebt();\n',
    '  testFailSafeOffExecutesThroughSupervisorOnly();\n  testHardSafetyOverridesSupervisorFailSafeOff();\n',
)

run(['git', 'diff', '--check'])
changed = sorted(filter(None, out(['git', 'diff', '--name-only']).splitlines()))
if changed != EXPECTED:
    raise SystemExit(f'A11_2_ALLOWLIST_FAIL changed={changed!r}')

# Narrow ownership/static checks before compilation.
runtime_text = Path(runtime_path).read_text()
for token in (
    'Stage28dRfOutputEndpoint',
    'MappedClimateRoleDriver',
    'SwitchableRoleDriver',
    'ClimateActuatorAdapter',
    'forceSafeStateWithRetries',
    'physical_endpoint',
    'writeScheduledLight(',
    'setSafetyForceExhaust(',
):
    if token in runtime_text:
        raise SystemExit(f'A11_2_RUNTIME_OWNER_FAIL token={token!r}')
cmake_text = Path('src/CMakeLists.txt').read_text()
for token in ('climate/Stage28dRfOutputEndpoint.cpp', 'climate/Stage28dBinaryRoleArbiter.cpp'):
    if token in cmake_text:
        raise SystemExit(f'A11_2_FIRMWARE_SOURCE_OWNER_FAIL token={token!r}')
sink_h = Path('src/climate/output/ClimateOutputSupervisorSink.h').read_text()
sink_cpp = Path('src/climate/output/ClimateOutputSupervisorSink.cpp').read_text()
if 'fail_safe_fallback' in sink_h + sink_cpp:
    raise SystemExit('A11_2_FALLBACK_FAIL legacy fail-safe fallback remains')
if 'OutputReason::FaultContainment' not in sink_cpp or 'resolver_.resolve' not in sink_cpp:
    raise SystemExit('A11_2_FAILSAFE_SUPERVISOR_FAIL')
if 'Legacy Gate6 thermal qualification is retired' not in runtime_text:
    raise SystemExit('A11_2_THERMAL_FAIL_CLOSED_FAIL')
# Compatibility evidence remains available to host tests only.
for rel in (
    'src/climate/Stage28dRfOutputEndpoint.cpp',
    'src/climate/Stage28dBinaryRoleArbiter.cpp',
):
    if not Path(rel).is_file():
        raise SystemExit(f'A11_2_COMPATIBILITY_SHIM_MISSING {rel}')
print('A11_2_STATIC_PASS')

build = 'build/host-tests-a11-2-v1'
run(['cmake', '-S', 'test/host', '-B', build])
targets = [
    'climate_output_supervisor_sink_tests',
    'output_supervisor_resolver_tests',
    'output_supervisor_executor_tests',
    'output_runtime_lifecycle_control_tests',
    'climate_application_composition_tests',
    'climate_control_loop_tests',
    'binary_actuator_policy_tests',
    'stage28d_lamp_safety_tests',
    'stage28d_rf_output_endpoint_tests',
    'stage28d_binary_role_arbiter_tests',
]
run(['cmake', '--build', build, '--parallel', '--target', *targets])
regex = '^(' + '|'.join(targets) + ')$'
run(['ctest', '--test-dir', build, '-R', regex, '--output-on-failure'])
print('A11_2_FOCUSED_PASS')

fw_build = 'build/stage27c-a11-2-v1'
Path(fw_build).mkdir(parents=True, exist_ok=True)
env = os.environ.copy()
env.update({
    'STAGE27C_BUILD_DIR': fw_build,
    'STAGE27C_SDKCONFIG': f'{fw_build}/sdkconfig',
    'GROWBOX_RF433_LOOPBACK_ENABLED': '1',
    'GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED': '1',
    'GROWBOX_RF433_REMOTE_CAPTURE_ENABLED': '0',
    'GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED': '0',
})
run(['bash', 'scripts/stage27c_crowpanel.sh', 'build'], env=env)
print('A11_2_CANONICAL_BUILD_PASS')

run(['git', 'diff', '--check'])
changed = sorted(filter(None, out(['git', 'diff', '--name-only']).splitlines()))
if changed != EXPECTED:
    raise SystemExit(f'A11_2_FINAL_ALLOWLIST_FAIL changed={changed!r}')
run(['git', 'add', '--', *EXPECTED])
staged = sorted(filter(None, out(['git', 'diff', '--cached', '--name-only']).splitlines()))
if staged != EXPECTED:
    raise SystemExit(f'A11_2_STAGED_ALLOWLIST_FAIL staged={staged!r}')
run(['git', 'commit', '-m', 'Remove legacy output execution owners'])
commit = out(['git', 'rev-parse', 'HEAD'])
run(['git', 'push', 'origin', f'HEAD:{BRANCH}'])
run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'FETCH_HEAD']) != commit:
    raise SystemExit('A11_2_PUSH_VERIFY_FAIL')
if out(['git', 'status', '--porcelain']):
    raise SystemExit('A11_2_CLEAN_FAIL')
print(f'A11_2_PASS commit={commit}')
