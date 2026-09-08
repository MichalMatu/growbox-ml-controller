import os
import subprocess
from pathlib import Path

BASE = '0a9298374235729b54225a82e86e28997f3acca5'
BRANCH = 'mvp/environment-controller'
EXPECTED = sorted([
    'src/CMakeLists.txt',
    'src/climate/ClimateV6RealInputRuntime.cpp',
    'src/climate/output/OutputLifecycleExecutor.cpp',
    'src/climate/output/OutputLifecycleExecutor.h',
    'src/climate/output/OutputRuntimeLifecycleControl.cpp',
    'src/climate/output/OutputRuntimeLifecycleControl.h',
    'test/host/CMakeLists.txt',
    'test/test_output_runtime_lifecycle_control/test_main.cpp',
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
        raise SystemExit(f'{path}: expected one replacement, found {count}')
    p.write_text(text.replace(old, new, 1))


run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'HEAD']) != BASE:
    raise SystemExit('A11_1_IDENTITY_FAIL local HEAD mismatch')
if out(['git', 'rev-parse', 'FETCH_HEAD']) != BASE:
    raise SystemExit('A11_1_IDENTITY_FAIL remote branch mismatch')
if out(['git', 'status', '--porcelain']):
    raise SystemExit('A11_1_IDENTITY_FAIL worktree not clean')
print('A11_1_IDENTITY_PASS')

Path('src/climate/output/OutputRuntimeLifecycleControl.h').write_text(r'''#pragma once

#include "climate/output/OutputLifecycleExecutor.h"

#include <cstdint>

namespace growbox::app::output {

enum class OutputRuntimeLifecycleOperation : std::uint8_t {
  None = 0U,
  Boot,
  Recovery,
  Fault,
};

enum class OutputRuntimeLifecycleStatus : std::uint8_t {
  Ready = 0U,
  TransitionPending,
  SafetyDeferred,
  FaultLocked,
  Invalid,
};

struct OutputRuntimeLifecycleReport {
  OutputRuntimeLifecycleStatus status = OutputRuntimeLifecycleStatus::Ready;
  SupervisorMode mode = SupervisorMode::BootLocked;
  OutputRuntimeLifecycleOperation operation = OutputRuntimeLifecycleOperation::None;
  bool active = false;
  bool safety_deferred = false;
  bool boot_completed = false;
  OutputLifecycleExecutionReport lifecycle{};
};

class OutputRuntimeLifecycleControl final {
public:
  OutputRuntimeLifecycleControl(OutputSupervisorLifecycle& lifecycle,
                                OutputLifecycleExecutor& executor) noexcept;

  bool valid() const noexcept { return valid_; }
  bool transitionActive() const noexcept {
    return operation_ != OutputRuntimeLifecycleOperation::None;
  }
  bool bootCompleted() const noexcept { return boot_completed_; }
  OutputRuntimeLifecycleOperation operation() const noexcept { return operation_; }

  bool beginBoot(std::uint64_t monotonic_ms, const ScheduleIntent& schedule) noexcept;
  bool requestRecovery(std::uint64_t monotonic_ms, const ScheduleIntent& schedule) noexcept;
  bool requestFault(std::uint64_t monotonic_ms, const ScheduleIntent& schedule) noexcept;

  OutputRuntimeLifecycleReport tick(std::uint64_t monotonic_ms,
                                    const SafetyEnvelope& safety) noexcept;
  OutputRuntimeLifecycleReport report() const noexcept;

private:
  static bool hardSafetyActive(const SafetyEnvelope& safety) noexcept;
  bool start(OutputLifecycleCommand command, OutputRuntimeLifecycleOperation operation,
             std::uint64_t monotonic_ms, const ScheduleIntent& schedule) noexcept;
  void finalizeCompletedOperation() noexcept;
  OutputRuntimeLifecycleReport makeReport(bool safety_deferred) const noexcept;

  OutputSupervisorLifecycle& lifecycle_;
  OutputLifecycleExecutor& executor_;
  OutputRuntimeLifecycleOperation operation_{OutputRuntimeLifecycleOperation::None};
  bool boot_completed_{false};
  bool valid_{false};
};

} // namespace growbox::app::output
''')

Path('src/climate/output/OutputRuntimeLifecycleControl.cpp').write_text(r'''#include "climate/output/OutputRuntimeLifecycleControl.h"

namespace growbox::app::output {

OutputRuntimeLifecycleControl::OutputRuntimeLifecycleControl(
    OutputSupervisorLifecycle& lifecycle, OutputLifecycleExecutor& executor) noexcept
    : lifecycle_(lifecycle), executor_(executor), valid_(lifecycle_.valid() && executor_.valid()) {}

bool OutputRuntimeLifecycleControl::hardSafetyActive(const SafetyEnvelope& safety) noexcept {
  for (const auto& constraint : safety.endpoints) {
    if (!safetyConstraintActive(constraint)) {
      continue;
    }
    if (constraint.constraint == SafetyConstraint::ForceOff ||
        constraint.constraint == SafetyConstraint::ForceOn ||
        constraint.constraint == SafetyConstraint::Inhibit) {
      return true;
    }
  }
  return false;
}

bool OutputRuntimeLifecycleControl::start(OutputLifecycleCommand command,
                                          OutputRuntimeLifecycleOperation operation,
                                          std::uint64_t monotonic_ms,
                                          const ScheduleIntent& schedule) noexcept {
  if (!valid_ || transitionActive() || executor_.active()) {
    return false;
  }
  const auto transition = lifecycle_.apply(command);
  if (transition.status != OutputLifecycleTransitionStatus::Applied ||
      !transition.has_policy_event || !executor_.start(transition, monotonic_ms, schedule)) {
    if (operation == OutputRuntimeLifecycleOperation::Boot &&
        lifecycle_.mode() == SupervisorMode::Arming) {
      (void)lifecycle_.apply(OutputLifecycleCommand::ArmingFailed);
    } else if (operation == OutputRuntimeLifecycleOperation::Recovery &&
               lifecycle_.mode() == SupervisorMode::Recovering) {
      (void)lifecycle_.apply(OutputLifecycleCommand::RecoveryFailed);
    }
    return false;
  }
  operation_ = operation;
  return true;
}

bool OutputRuntimeLifecycleControl::beginBoot(std::uint64_t monotonic_ms,
                                              const ScheduleIntent& schedule) noexcept {
  if (lifecycle_.mode() != SupervisorMode::BootLocked) {
    return false;
  }
  return start(OutputLifecycleCommand::BeginArming, OutputRuntimeLifecycleOperation::Boot,
               monotonic_ms, schedule);
}

bool OutputRuntimeLifecycleControl::requestRecovery(std::uint64_t monotonic_ms,
                                                    const ScheduleIntent& schedule) noexcept {
  if (lifecycle_.mode() != SupervisorMode::FaultLocked &&
      lifecycle_.mode() != SupervisorMode::Automatic) {
    return false;
  }
  return start(OutputLifecycleCommand::BeginRecovery, OutputRuntimeLifecycleOperation::Recovery,
               monotonic_ms, schedule);
}

bool OutputRuntimeLifecycleControl::requestFault(std::uint64_t monotonic_ms,
                                                 const ScheduleIntent& schedule) noexcept {
  if (!valid_) {
    return false;
  }
  if (operation_ == OutputRuntimeLifecycleOperation::Fault) {
    return true;
  }
  if (lifecycle_.mode() == SupervisorMode::FaultLocked) {
    return true;
  }
  if (!executor_.cancelPending()) {
    return false;
  }
  operation_ = OutputRuntimeLifecycleOperation::None;
  return start(OutputLifecycleCommand::EnterFault, OutputRuntimeLifecycleOperation::Fault,
               monotonic_ms, schedule);
}

void OutputRuntimeLifecycleControl::finalizeCompletedOperation() noexcept {
  const auto completed = operation_;
  operation_ = OutputRuntimeLifecycleOperation::None;

  if (completed == OutputRuntimeLifecycleOperation::Boot) {
    if (executor_.status() == OutputLifecycleExecutionStatus::Completed &&
        lifecycle_.mode() == SupervisorMode::Arming) {
      const auto transition = lifecycle_.apply(OutputLifecycleCommand::ArmingSucceeded);
      boot_completed_ = transition.status == OutputLifecycleTransitionStatus::Applied ||
                        transition.status == OutputLifecycleTransitionStatus::NoChange;
    } else if (lifecycle_.mode() == SupervisorMode::Arming) {
      (void)lifecycle_.apply(OutputLifecycleCommand::ArmingFailed);
    }
    return;
  }

  if (completed == OutputRuntimeLifecycleOperation::Recovery) {
    if (executor_.status() == OutputLifecycleExecutionStatus::Completed &&
        lifecycle_.mode() == SupervisorMode::Recovering) {
      const auto transition = lifecycle_.apply(OutputLifecycleCommand::RecoverySucceeded);
      if (transition.status == OutputLifecycleTransitionStatus::Applied ||
          transition.status == OutputLifecycleTransitionStatus::NoChange) {
        boot_completed_ = true;
      }
    } else if (lifecycle_.mode() == SupervisorMode::Recovering) {
      (void)lifecycle_.apply(OutputLifecycleCommand::RecoveryFailed);
    }
  }
  // Fault execution intentionally leaves the lifecycle in FaultLocked.
}

OutputRuntimeLifecycleReport
OutputRuntimeLifecycleControl::makeReport(bool safety_deferred) const noexcept {
  OutputRuntimeLifecycleReport value{};
  value.mode = lifecycle_.mode();
  value.operation = operation_;
  value.active = transitionActive();
  value.safety_deferred = safety_deferred;
  value.boot_completed = boot_completed_;
  value.lifecycle = executor_.report();
  if (!valid_) {
    value.status = OutputRuntimeLifecycleStatus::Invalid;
  } else if (safety_deferred) {
    value.status = OutputRuntimeLifecycleStatus::SafetyDeferred;
  } else if (transitionActive()) {
    value.status = OutputRuntimeLifecycleStatus::TransitionPending;
  } else if (value.mode == SupervisorMode::FaultLocked) {
    value.status = OutputRuntimeLifecycleStatus::FaultLocked;
  } else {
    value.status = OutputRuntimeLifecycleStatus::Ready;
  }
  return value;
}

OutputRuntimeLifecycleReport OutputRuntimeLifecycleControl::tick(
    std::uint64_t monotonic_ms, const SafetyEnvelope& safety) noexcept {
  if (!valid_ || !transitionActive()) {
    return makeReport(false);
  }
  if (hardSafetyActive(safety)) {
    return makeReport(true);
  }
  if (executor_.active()) {
    (void)executor_.tick(monotonic_ms);
  }
  if (!executor_.active()) {
    finalizeCompletedOperation();
  }
  return makeReport(false);
}

OutputRuntimeLifecycleReport OutputRuntimeLifecycleControl::report() const noexcept {
  return makeReport(false);
}

} // namespace growbox::app::output
''')

replace_once(
    'src/climate/output/OutputLifecycleExecutor.h',
    '''  OutputLifecycleExecutionReport tick(std::uint64_t monotonic_ms) noexcept;\n  OutputLifecycleExecutionReport report() const noexcept;\n''',
    '''  OutputLifecycleExecutionReport tick(std::uint64_t monotonic_ms) noexcept;\n  // Abort a pending lifecycle plan without fabricating a transport result. This is\n  // used only when a higher-priority fault transition supersedes the old plan.\n  bool cancelPending() noexcept;\n  OutputLifecycleExecutionReport report() const noexcept;\n''',
)
replace_once(
    'src/climate/output/OutputLifecycleExecutor.cpp',
    '''OutputLifecycleExecutionReport OutputLifecycleExecutor::report() const noexcept {\n''',
    '''bool OutputLifecycleExecutor::cancelPending() noexcept {\n  if (!valid_) {\n    return false;\n  }\n  if (!active_) {\n    return true;\n  }\n  clearPlan();\n  active_ = false;\n  containment_active_ = false;\n  status_ = OutputLifecycleExecutionStatus::Idle;\n  event_ = OutputLifecycleEvent::Boot;\n  return true;\n}\n\nOutputLifecycleExecutionReport OutputLifecycleExecutor::report() const noexcept {\n''',
)

replace_once(
    'src/CMakeLists.txt',
    '''    "climate/output/OutputMaintenanceControl.cpp"\n    "climate/output/OutputExecutionProjection.cpp"\n''',
    '''    "climate/output/OutputMaintenanceControl.cpp"\n    "climate/output/OutputRuntimeLifecycleControl.cpp"\n    "climate/output/OutputExecutionProjection.cpp"\n''',
)

replace_once(
    'src/climate/ClimateV6RealInputRuntime.cpp',
    '''#include "climate/output/OutputMaintenanceControl.h"\n#include "climate/output/OutputNvsBackend.h"\n''',
    '''#include "climate/output/OutputMaintenanceControl.h"\n#include "climate/output/OutputRuntimeLifecycleControl.h"\n#include "climate/output/OutputNvsBackend.h"\n''',
)

replace_once(
    'src/climate/ClimateV6RealInputRuntime.cpp',
    '''  stage28d::Stage28dRfOutputEndpoint physical_endpoint(\n      {GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED != 0 && rf_ready && output_bindings_valid, 0.5F},\n      rf_output_transport, output_state_store_ready ? &output_state_store : nullptr);\n\n  bool real_output_ready = false;\n  if (GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED != 0) {\n    real_output_ready = rf_ready && output_bindings_valid;\n    if (real_output_ready) {\n      real_output_ready = forceSafeStateWithRetries(physical_endpoint, monotonicMilliseconds());\n    }\n    if (!real_output_ready) {\n      ESP_LOGE(kTag, "Real-output initialization failed; automatic outputs remain fake-locked");\n    }\n  }\n''',
    '''  bool real_transport_available =\n      GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED != 0 && rf_ready && output_bindings_valid;\n  stage28d::Stage28dRfOutputEndpoint physical_endpoint(\n      {real_transport_available, 0.5F}, rf_output_transport,\n      output_state_store_ready ? &output_state_store : nullptr);\n\n  // Normal production startup is supervisor-owned below. The legacy thermal\n  // qualification path remains explicit migration debt until A11.2.\n  bool real_output_ready =\n      real_transport_available && GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED != 0;\n  if (GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED != 0 && !real_transport_available) {\n    ESP_LOGE(kTag, "Real-output transport unavailable; automatic outputs remain fake-locked");\n  }\n''',
)

replace_once(
    'src/climate/ClimateV6RealInputRuntime.cpp',
    '''  output::BinaryActuatorPolicy exhaust_policy(kExhaustPolicyConfig);\n  output::BinaryActuatorPolicy humidifier_policy(kHumidifierPolicyConfig);\n  if (real_output_ready) {\n    synchronizeSupervisorPoliciesSafeOff(exhaust_policy, humidifier_policy,\n                                         monotonicMilliseconds());\n  }\n''',
    '''  output::BinaryActuatorPolicy exhaust_policy(kExhaustPolicyConfig);\n  output::BinaryActuatorPolicy humidifier_policy(kHumidifierPolicyConfig);\n''',
)

replace_once(
    'src/climate/ClimateV6RealInputRuntime.cpp',
    '''  RuntimeOutputTransport supervisor_transport(rf_output_transport, real_output_ready);\n  output::OutputSupervisorLifecycle output_lifecycle(output_policy);\n  output::OutputLifecycleExecutor lifecycle_executor(output_policy, output_lifecycle,\n                                                     supervisor_transport, output_state_store,\n                                                     supervisor_config);\n  bool lifecycle_ready = output_lifecycle.valid() && lifecycle_executor.valid();\n  if (lifecycle_ready) {\n    const auto begin_arming = output_lifecycle.apply(output::OutputLifecycleCommand::BeginArming);\n    const auto armed = output_lifecycle.apply(output::OutputLifecycleCommand::ArmingSucceeded);\n    lifecycle_ready = begin_arming.status == output::OutputLifecycleTransitionStatus::Applied &&\n                      armed.status == output::OutputLifecycleTransitionStatus::Applied &&\n                      output_lifecycle.mode() == output::SupervisorMode::Automatic;\n  }\n  output::OutputAutomationControl automation_control(output_lifecycle, lifecycle_executor);\n''',
    '''  RuntimeOutputTransport supervisor_transport(rf_output_transport, real_transport_available);\n  output::OutputSupervisorLifecycle output_lifecycle(output_policy);\n  output::OutputLifecycleExecutor lifecycle_executor(output_policy, output_lifecycle,\n                                                     supervisor_transport, output_state_store,\n                                                     supervisor_config);\n  output::OutputRuntimeLifecycleControl runtime_lifecycle(output_lifecycle, lifecycle_executor);\n  bool lifecycle_ready = output_lifecycle.valid() && lifecycle_executor.valid() &&\n                         runtime_lifecycle.valid();\n  output::OutputAutomationControl automation_control(output_lifecycle, lifecycle_executor);\n''',
)

replace_once(
    'src/climate/ClimateV6RealInputRuntime.cpp',
    '''  if (!supervisor_sink.valid() || !lifecycle_ready) {\n    ESP_LOGE(kTag, "Output supervisor/lifecycle composition invalid; real outputs remain locked");\n    if (real_output_ready) {\n      const std::uint64_t safe_ms = monotonicMilliseconds();\n      const bool safe_off = forceSafeStateWithRetries(physical_endpoint, safe_ms);\n      if (safe_off) {\n        synchronizeSupervisorPoliciesSafeOff(exhaust_policy, humidifier_policy, safe_ms);\n      }\n      fail_safe_output_driver.disableReal();\n      real_output_ready = false;\n      ESP_LOGE(kTag, "Output supervisor composition fault safe_off=%d outputs=fake-locked",\n               safe_off);\n    }\n  }\n''',
    '''  if (!supervisor_sink.valid() || !lifecycle_ready) {\n    ESP_LOGE(kTag, "Output supervisor/lifecycle composition invalid; physical execution locked");\n    // There is no direct emergency writer here anymore. If the supervisor cannot\n    // be composed, fail closed by disabling transport ownership for this boot.\n    real_transport_available = false;\n    fail_safe_output_driver.disableReal();\n    real_output_ready = false;\n  }\n''',
)

replace_once(
    'src/climate/ClimateV6RealInputRuntime.cpp',
    '''    const bool real_transport_active_this_cycle = real_output_ready;\n''',
    '''    const bool real_transport_active_this_cycle = real_transport_available;\n''',
)

replace_once(
    'src/climate/ClimateV6RealInputRuntime.cpp',
    '''      if (!safety_envelope_ready && fail_safe_output_driver.realEnabled()) {\n        ESP_LOGE(kTag, "Lamp safety envelope build failed; forcing safe state and locking outputs");\n        const bool safe_off = forceSafeStateWithRetries(physical_endpoint, now_ms);\n        if (safe_off) {\n          synchronizeSupervisorPoliciesSafeOff(exhaust_policy, humidifier_policy, now_ms);\n        }\n        fail_safe_output_driver.disableReal();\n        real_output_ready = false;\n        ESP_LOGE(kTag, "Lamp safety envelope fault safe_off=%d outputs=fake-locked", safe_off);\n      }\n\n      const auto automation_report =\n          automation_control.tick(now_ms, schedule_intent, safety_snapshot.envelope);\n      const auto maintenance_report =\n          maintenance_control.tick(now_ms, safety_snapshot.envelope);\n\n      output::ManualIntent manual_intent{};\n      (void)manual_control.consume(manual_intent);\n\n      ClimateOutputSupervisorCycleContext supervisor_context{};\n      supervisor_context.mode = maintenance_report.mode;\n''',
    '''      if (!safety_envelope_ready && real_transport_available &&\n          output_lifecycle.mode() != output::SupervisorMode::FaultLocked) {\n        ESP_LOGE(kTag, "Lamp safety envelope build failed; requesting supervisor fault containment");\n        if (!runtime_lifecycle.requestFault(now_ms, schedule_intent)) {\n          ESP_LOGE(kTag, "Supervisor fault request failed; disabling physical transport");\n          real_transport_available = false;\n        }\n        real_output_ready = false;\n      } else if (safety_envelope_ready &&\n                 output_lifecycle.mode() == output::SupervisorMode::BootLocked &&\n                 !runtime_lifecycle.transitionActive()) {\n        if (!runtime_lifecycle.beginBoot(now_ms, schedule_intent)) {\n          ESP_LOGE(kTag, "Supervisor boot plan failed to start; disabling physical transport");\n          real_transport_available = false;\n          real_output_ready = false;\n        }\n      }\n\n      // Runtime boot/recovery/fault owns the lifecycle executor only while its\n      // own transition is active. Automation/maintenance retain their existing\n      // executor ownership outside those windows. Hard safety defers lifecycle\n      // TX and remains executable by the supervisor resolver below.\n      (void)runtime_lifecycle.tick(now_ms, safety_snapshot.envelope);\n      if (!runtime_lifecycle.transitionActive()) {\n        (void)automation_control.tick(now_ms, schedule_intent, safety_snapshot.envelope);\n        (void)maintenance_control.tick(now_ms, safety_snapshot.envelope);\n      }\n\n      real_output_ready = real_transport_available && runtime_lifecycle.bootCompleted() &&\n                          output_lifecycle.mode() != output::SupervisorMode::FaultLocked;\n\n      output::ManualIntent manual_intent{};\n      (void)manual_control.consume(manual_intent);\n\n      ClimateOutputSupervisorCycleContext supervisor_context{};\n      supervisor_context.mode = output_lifecycle.mode();\n''',
)

replace_once(
    'src/climate/ClimateV6RealInputRuntime.cpp',
    '''      loop_result = application.tick(now_ms, decision);\n      if (fail_safe_output_driver.realEnabled() && !loop_result.command_applied) {\n        ESP_LOGE(kTag, "Supervisor output apply failed; forcing safe state and locking real outputs");\n        const bool safe_off = forceSafeStateWithRetries(physical_endpoint, now_ms);\n        if (safe_off) {\n          synchronizeSupervisorPoliciesSafeOff(exhaust_policy, humidifier_policy, now_ms);\n        }\n        fail_safe_output_driver.disableReal();\n        real_output_ready = false;\n        ESP_LOGE(kTag, "Supervisor output fault safe_off=%d outputs=fake-locked", safe_off);\n      }\n''',
    '''      loop_result = application.tick(now_ms, decision);\n      if (real_transport_available && !loop_result.command_applied &&\n          output_lifecycle.mode() != output::SupervisorMode::FaultLocked) {\n        ESP_LOGE(kTag, "Supervisor output apply failed; requesting lifecycle fault containment");\n        if (!runtime_lifecycle.requestFault(now_ms, schedule_intent)) {\n          ESP_LOGE(kTag, "Lifecycle fault containment failed to start; disabling physical transport");\n          real_transport_available = false;\n        }\n        real_output_ready = false;\n      }\n''',
)

# Register focused host target immediately after the existing lifecycle executor target.
host = Path('test/host/CMakeLists.txt')
text = host.read_text()
anchor = '''target_compile_options(output_lifecycle_executor_tests PRIVATE -Wall -Wextra -Wpedantic)\n\nadd_executable(\n  output_automation_control_tests\n'''
insert = '''target_compile_options(output_lifecycle_executor_tests PRIVATE -Wall -Wextra -Wpedantic)\n\nadd_executable(\n  output_runtime_lifecycle_control_tests\n  "${PROJECT_ROOT}/test/test_output_runtime_lifecycle_control/test_main.cpp"\n  "${PROJECT_ROOT}/src/climate/output/OutputRuntimeLifecycleControl.cpp"\n  "${PROJECT_ROOT}/src/climate/output/OutputLifecycleExecutor.cpp"\n  "${PROJECT_ROOT}/src/climate/output/OutputSupervisorLifecycle.cpp"\n  "${PROJECT_ROOT}/src/climate/output/OutputSupervisorResolver.cpp"\n  "${PROJECT_ROOT}/src/climate/output/OutputPolicyConfig.cpp"\n  "${PROJECT_ROOT}/src/climate/output/OutputStateStore.cpp"\n  "${PROJECT_ROOT}/src/climate/output/BinaryActuatorPolicy.cpp"\n)\ntarget_include_directories(output_runtime_lifecycle_control_tests PRIVATE "${PROJECT_ROOT}/src")\ntarget_compile_features(output_runtime_lifecycle_control_tests PRIVATE cxx_std_17)\ntarget_compile_options(output_runtime_lifecycle_control_tests PRIVATE -Wall -Wextra -Wpedantic)\n\nadd_executable(\n  output_automation_control_tests\n'''
if text.count(anchor) != 1:
    raise SystemExit(f'test/host/CMakeLists.txt: runtime target anchor count={text.count(anchor)}')
text = text.replace(anchor, insert, 1)
add_anchor = 'add_test(NAME output_lifecycle_executor_tests COMMAND output_lifecycle_executor_tests)\n'
if text.count(add_anchor) != 1:
    raise SystemExit('test/host/CMakeLists.txt: add_test anchor mismatch')
text = text.replace(add_anchor, add_anchor +
                    'add_test(NAME output_runtime_lifecycle_control_tests COMMAND output_runtime_lifecycle_control_tests)\n', 1)
host.write_text(text)

Path('test/test_output_runtime_lifecycle_control').mkdir(parents=True, exist_ok=True)
Path('test/test_output_runtime_lifecycle_control/test_main.cpp').write_text(r'''#include "climate/output/OutputRuntimeLifecycleControl.h"
#include "climate/output/OutputSupervisorResolver.h"

#include <array>
#include <cassert>
#include <cstddef>
#include <cstdint>

namespace output = growbox::app::output;

namespace {

constexpr output::OutputEndpointId kFan = 1U;
constexpr output::OutputEndpointId kLamp = 2U;
constexpr output::OutputEndpointId kHumidifier = 3U;

struct FakeTransport final : output::OutputTransport {
  std::array<output::OutputCommand, 32U> commands{};
  std::size_t count{0U};
  output::OutputEndpointId fail_endpoint{output::kInvalidOutputEndpoint};
  bool fail_always{false};

  output::TxResult send(const output::OutputCommand& command) noexcept override {
    assert(count < commands.size());
    commands[count++] = command;
    if (fail_always && command.endpoint == fail_endpoint) {
      return {output::TransportStatus::Failed, output::TransportError::IoFailure};
    }
    return {output::TransportStatus::Completed, output::TransportError::None};
  }

  void reset() noexcept {
    count = 0U;
    fail_endpoint = output::kInvalidOutputEndpoint;
    fail_always = false;
  }
};

struct Fixture {
  output::OutputPolicyConfig policy{output::makeSafeDefaultOutputPolicyConfig(kFan, kLamp,
                                                                              kHumidifier)};
  output::OutputStateStore store{};
  output::OutputSupervisorResolverConfig resolver_config{};
  FakeTransport transport{};
  output::OutputSupervisorLifecycle lifecycle;
  output::OutputLifecycleExecutor executor;
  output::OutputRuntimeLifecycleControl control;

  explicit Fixture(output::OutputPolicyConfig custom =
                       output::makeSafeDefaultOutputPolicyConfig(kFan, kLamp, kHumidifier))
      : policy(custom), lifecycle(policy),
        executor(policy, lifecycle, transport, store, makeResolverConfig()),
        control(lifecycle, executor) {
    const std::array<output::OutputEndpointId, output::kOutputEndpointCapacity> endpoints{
        kFan, kLamp, kHumidifier};
    assert(store.configure(endpoints, endpoints.size()));
    resolver_config = makeResolverConfig();
    // executor was constructed before store.configure; composition validation
    // therefore must be rebuilt in tests through the alternate fixture helper.
  }

  static output::OutputSupervisorResolverConfig makeResolverConfig() noexcept {
    output::OutputSupervisorResolverConfig config{};
    config.endpoints[0] = {kLamp, nullptr};
    config.endpoints[1] = {kFan, nullptr};
    config.endpoints[2] = {kHumidifier, nullptr};
    config.count = 3U;
    return config;
  }
};

// Construct objects in the same order as production: state store first, then executor.
struct ReadyFixture {
  output::OutputPolicyConfig policy{};
  output::OutputStateStore store{};
  output::OutputSupervisorResolverConfig resolver_config{};
  FakeTransport transport{};
  output::OutputSupervisorLifecycle lifecycle;
  output::OutputLifecycleExecutor executor;
  output::OutputRuntimeLifecycleControl control;

  explicit ReadyFixture(output::OutputPolicyConfig custom =
                            output::makeSafeDefaultOutputPolicyConfig(kFan, kLamp, kHumidifier))
      : policy(custom), resolver_config(makeResolverConfig()), lifecycle(policy),
        executor(policy, lifecycle, transport, store, resolver_config), control(lifecycle, executor) {
    // This constructor cannot configure store before executor construction. Use create().
  }

  static output::OutputSupervisorResolverConfig makeResolverConfig() noexcept {
    output::OutputSupervisorResolverConfig config{};
    config.endpoints[0] = {kLamp, nullptr};
    config.endpoints[1] = {kFan, nullptr};
    config.endpoints[2] = {kHumidifier, nullptr};
    config.count = 3U;
    return config;
  }
};

struct Harness {
  output::OutputPolicyConfig policy{};
  output::OutputStateStore store{};
  output::OutputSupervisorResolverConfig config{};
  FakeTransport transport{};
  output::OutputSupervisorLifecycle* lifecycle{nullptr};
  output::OutputLifecycleExecutor* executor{nullptr};
  output::OutputRuntimeLifecycleControl* control{nullptr};

  explicit Harness(output::OutputPolicyConfig custom =
                       output::makeSafeDefaultOutputPolicyConfig(kFan, kLamp, kHumidifier))
      : policy(custom) {
    const std::array<output::OutputEndpointId, output::kOutputEndpointCapacity> endpoints{
        kFan, kLamp, kHumidifier};
    assert(store.configure(endpoints, endpoints.size()));
    config.endpoints[0] = {kLamp, nullptr};
    config.endpoints[1] = {kFan, nullptr};
    config.endpoints[2] = {kHumidifier, nullptr};
    config.count = 3U;
    lifecycle = new output::OutputSupervisorLifecycle(policy);
    executor = new output::OutputLifecycleExecutor(policy, *lifecycle, transport, store, config);
    control = new output::OutputRuntimeLifecycleControl(*lifecycle, *executor);
    assert(control->valid());
  }

  ~Harness() {
    delete control;
    delete executor;
    delete lifecycle;
  }

  void tickUntilDone(std::uint64_t now = 100U) {
    output::SafetyEnvelope safety{};
    for (unsigned i = 0U; i < 32U && control->transitionActive(); ++i) {
      (void)control->tick(now + i, safety);
    }
    assert(!control->transitionActive());
  }
};

void testBootPlanOwnsSafeInitialization() {
  Harness h;
  output::ScheduleIntent schedule{};
  assert(h.control->beginBoot(100U, schedule));
  assert(h.lifecycle->mode() == output::SupervisorMode::Arming);
  h.tickUntilDone();
  assert(h.control->bootCompleted());
  assert(h.lifecycle->mode() == output::SupervisorMode::Automatic);
  assert(h.transport.count == 3U);
  assert(h.transport.commands[0].endpoint == kLamp);
  assert(h.transport.commands[1].endpoint == kFan);
  assert(h.transport.commands[2].endpoint == kHumidifier);
  for (std::size_t i = 0U; i < h.transport.count; ++i) {
    assert(h.transport.commands[i].state == output::BinaryOutputState::Off);
    assert(h.transport.commands[i].source == output::OutputSource::Lifecycle);
    assert(h.transport.commands[i].reason == output::OutputReason::LifecyclePolicy);
  }
}

void testFailedBootFaultLocks() {
  Harness h;
  h.transport.fail_endpoint = kLamp;
  h.transport.fail_always = true;
  assert(h.control->beginBoot(200U, {}));
  h.tickUntilDone(200U);
  assert(!h.control->bootCompleted());
  assert(h.lifecycle->mode() == output::SupervisorMode::FaultLocked);
  assert(h.transport.count >= 2U);
}

void testRecoveryPartialFailureFailsClosed() {
  auto policy = output::makeSafeDefaultOutputPolicyConfig(kFan, kLamp, kHumidifier);
  policy.max_transition_failures = 2U;
  for (std::size_t i = 0U; i < policy.count; ++i) {
    auto& recovery = policy.endpoints[i].lifecycle[output::outputLifecycleEventIndex(
        output::OutputLifecycleEvent::Recovery)];
    recovery.max_retries = 0U;
  }
  assert(output::validateOutputPolicyConfig(policy) == output::OutputPolicyConfigStatus::Ok);
  Harness h(policy);
  (void)h.lifecycle->apply(output::OutputLifecycleCommand::EnterFault);
  assert(h.lifecycle->mode() == output::SupervisorMode::FaultLocked);
  h.transport.fail_endpoint = kLamp;
  h.transport.fail_always = true;
  assert(h.control->requestRecovery(300U, {}));
  h.tickUntilDone(300U);
  assert(h.lifecycle->mode() == output::SupervisorMode::FaultLocked);
  assert(h.executor->status() == output::OutputLifecycleExecutionStatus::CompletedWithFailures);
}

void testFaultSupersedesPendingBootPlan() {
  Harness h;
  assert(h.control->beginBoot(400U, {}));
  assert(h.executor->active());
  assert(h.control->requestFault(401U, {}));
  assert(h.lifecycle->mode() == output::SupervisorMode::FaultLocked);
  h.tickUntilDone(401U);
  assert(h.transport.count == 3U);
  for (std::size_t i = 0U; i < h.transport.count; ++i) {
    assert(h.transport.commands[i].reason == output::OutputReason::FaultContainment);
  }
}

void testHardSafetyDefersLifecycleButRemainsResolvable() {
  Harness h;
  assert(h.control->beginBoot(500U, {}));

  output::SafetyEnvelope safety{};
  safety.metadata.sequence = 77U;
  safety.metadata.monotonic_ms = 500U;
  safety.metadata.source = output::OutputSource::Safety;
  safety.metadata.reason = output::OutputReason::ThermalSafety;
  assert(output::setSafetyConstraint(safety.endpoints[0], kFan,
                                     output::SafetyConstraint::ForceOn,
                                     output::OutputReason::ThermalSafety));

  const auto report = h.control->tick(500U, safety);
  assert(report.status == output::OutputRuntimeLifecycleStatus::SafetyDeferred);
  assert(report.safety_deferred);
  assert(h.transport.count == 0U);
  assert(h.lifecycle->mode() == output::SupervisorMode::Arming);

  output::OutputSupervisorResolver resolver(h.config);
  output::OutputSupervisorCycleInput input{};
  input.mode = h.lifecycle->mode();
  input.monotonic_ms = 500U;
  input.safety = safety;
  output::OutputSupervisorResolution resolution{};
  assert(resolver.resolve(input, h.store, resolution));
  assert(resolution.plan.size == 1U);
  assert(resolution.plan.steps[0].endpoint == kFan);
  assert(resolution.plan.steps[0].state == output::BinaryOutputState::On);
  assert(resolution.plan.steps[0].source == output::OutputSource::Safety);
}

} // namespace

int main() {
  testBootPlanOwnsSafeInitialization();
  testFailedBootFaultLocks();
  testRecoveryPartialFailureFailsClosed();
  testFaultSupersedesPendingBootPlan();
  testHardSafetyDefersLifecycleButRemainsResolvable();
  return 0;
}
''')

# The test intentionally uses bounded dynamic construction only in the host fixture,
# never in production. Keep production hot path allocation-free.
run(['git', 'add', '-N', 'src/climate/output/OutputRuntimeLifecycleControl.cpp',
     'src/climate/output/OutputRuntimeLifecycleControl.h',
     'test/test_output_runtime_lifecycle_control/test_main.cpp'])
run(['git', 'diff', '--check'])
changed = sorted(filter(None, out(['git', 'diff', '--name-only']).splitlines()))
if changed != EXPECTED:
    raise SystemExit(f'A11_1_ALLOWLIST_FAIL changed={changed!r}')

runtime = Path('src/climate/ClimateV6RealInputRuntime.cpp').read_text()
if runtime.count('forceSafeStateWithRetries(') != 3:
    raise SystemExit(f'A11_1_STATIC_FAIL forceSafeStateWithRetries count={runtime.count("forceSafeStateWithRetries(")}')
if runtime.count('synchronizeSupervisorPoliciesSafeOff(') != 3:
    raise SystemExit('A11_1_STATIC_FAIL legacy safe-off synchronization escaped thermal-only debt')
for token in [
    'runtime_lifecycle.beginBoot(',
    'runtime_lifecycle.requestFault(',
    'runtime_lifecycle.tick(',
    'RuntimeOutputTransport supervisor_transport(rf_output_transport, real_transport_available)',
    'const bool real_transport_active_this_cycle = real_transport_available;',
    'supervisor_context.mode = output_lifecycle.mode();',
]:
    if token not in runtime:
        raise SystemExit(f'A11_1_STATIC_FAIL missing runtime token {token!r}')
if 'const auto begin_arming = output_lifecycle.apply' in runtime:
    raise SystemExit('A11_1_STATIC_FAIL direct arming bypass remains')
print('A11_1_STATIC_PASS')

build = 'build/host-tests-a11-1-v1'
run(['cmake', '-S', 'test/host', '-B', build])
targets = [
    'output_runtime_lifecycle_control_tests',
    'output_lifecycle_executor_tests',
    'output_supervisor_lifecycle_tests',
    'output_automation_control_tests',
    'output_maintenance_control_tests',
    'output_supervisor_resolver_tests',
    'climate_output_supervisor_sink_tests',
]
run(['cmake', '--build', build, '--parallel', '--target', *targets])
regex = '^(' + '|'.join(targets) + ')$'
run(['ctest', '--test-dir', build, '-R', regex, '--output-on-failure'])
print('A11_1_FOCUSED_PASS')

fw_build = 'build/stage27c-a11-1-v1'
Path(fw_build).mkdir(parents=True, exist_ok=True)
env = os.environ.copy()
env.update({
    'STAGE27C_BUILD_DIR': fw_build,
    'STAGE27C_SDKCONFIG': f'{fw_build}/sdkconfig',
    'GROWBOX_RF433_LOOPBACK_ENABLED': '1',
    'GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED': '1',
    'GROWBOX_RF433_LOOPBACK_AUTO_SMOKE': '0',
    'GROWBOX_RF433_REMOTE_CAPTURE_ENABLED': '0',
})
run(['bash', 'scripts/stage27c_crowpanel.sh', 'build'], env=env)
print('A11_1_CANONICAL_BUILD_PASS')

run(['git', 'diff', '--check'])
changed = sorted(filter(None, out(['git', 'diff', '--name-only']).splitlines()))
if changed != EXPECTED:
    raise SystemExit(f'A11_1_FINAL_ALLOWLIST_FAIL changed={changed!r}')
run(['git', 'add', '--', *EXPECTED])
staged = sorted(filter(None, out(['git', 'diff', '--cached', '--name-only']).splitlines()))
if staged != EXPECTED:
    raise SystemExit(f'A11_1_STAGED_ALLOWLIST_FAIL staged={staged!r}')
run(['git', 'commit', '-m', 'Move startup and recovery outputs to supervisor'])
commit = out(['git', 'rev-parse', 'HEAD'])
run(['git', 'push', 'origin', f'HEAD:{BRANCH}'])
run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'FETCH_HEAD']) != commit:
    raise SystemExit('A11_1_PUSH_VERIFY_FAIL')
if out(['git', 'status', '--porcelain']):
    raise SystemExit('A11_1_CLEAN_VERIFY_FAIL')
print(f'A11_1_PASS commit={commit}')
