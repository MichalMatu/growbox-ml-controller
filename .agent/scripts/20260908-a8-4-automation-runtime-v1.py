from pathlib import Path

ROOT = Path('.')


def replace_once(path: str, old: str, new: str) -> None:
    p = ROOT / path
    text = p.read_text()
    if text.count(old) != 1:
        raise SystemExit(f'{path}: expected one replacement, found {text.count(old)}')
    p.write_text(text.replace(old, new, 1))


def write(path: str, content: str) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)

write('src/climate/output/OutputAutomationControl.h', r'''#pragma once

#include "climate/output/OutputLifecycleExecutor.h"

#include <cstdint>

namespace growbox::app::output {

enum class OutputAutomationControlStatus : std::uint8_t {
  Ready = 0U,
  TransitionPending,
  SafetyDeferred,
  FaultLocked,
  Invalid,
};

struct OutputAutomationControlReport {
  OutputAutomationControlStatus status = OutputAutomationControlStatus::Ready;
  SupervisorMode mode = SupervisorMode::BootLocked;
  bool requested_enabled = false;
  bool request_pending = false;
  bool safety_deferred = false;
  bool lifecycle_active = false;
  OutputLifecycleExecutionReport lifecycle{};
};

class OutputAutomationControl final {
public:
  OutputAutomationControl(OutputSupervisorLifecycle& lifecycle,
                          OutputLifecycleExecutor& lifecycle_executor) noexcept;

  bool valid() const noexcept { return valid_; }
  bool requestEnabled(bool enabled) noexcept;
  bool requestedEnabled() const noexcept { return requested_enabled_; }
  bool requestPending() const noexcept { return request_pending_; }
  SupervisorMode mode() const noexcept { return lifecycle_.mode(); }
  bool transitionActive() const noexcept {
    return lifecycle_executor_.active() || arming_completion_pending_ || request_pending_;
  }

  OutputAutomationControlReport tick(std::uint64_t monotonic_ms,
                                     const ScheduleIntent& schedule,
                                     const SafetyEnvelope& safety) noexcept;

private:
  static bool hardSafetyActive(const SafetyEnvelope& safety) noexcept;
  bool completeArming() noexcept;
  bool applyPendingRequest(std::uint64_t monotonic_ms,
                           const ScheduleIntent& schedule) noexcept;
  OutputAutomationControlReport makeReport(bool safety_deferred) const noexcept;

  OutputSupervisorLifecycle& lifecycle_;
  OutputLifecycleExecutor& lifecycle_executor_;
  bool valid_{false};
  bool requested_enabled_{false};
  bool request_pending_{false};
  bool pending_enabled_{false};
  bool arming_completion_pending_{false};
};

} // namespace growbox::app::output
''')

write('src/climate/output/OutputAutomationControl.cpp', r'''#include "climate/output/OutputAutomationControl.h"

namespace growbox::app::output {

OutputAutomationControl::OutputAutomationControl(
    OutputSupervisorLifecycle& lifecycle,
    OutputLifecycleExecutor& lifecycle_executor) noexcept
    : lifecycle_(lifecycle), lifecycle_executor_(lifecycle_executor),
      valid_(lifecycle_.valid() && lifecycle_executor_.valid()),
      requested_enabled_(lifecycle_.mode() == SupervisorMode::Automatic) {}

bool OutputAutomationControl::requestEnabled(bool enabled) noexcept {
  if (!valid_) {
    return false;
  }
  const SupervisorMode current = lifecycle_.mode();
  if (current == SupervisorMode::FaultLocked || current == SupervisorMode::MaintenanceLocked ||
      current == SupervisorMode::Recovering || current == SupervisorMode::BootLocked) {
    return false;
  }
  requested_enabled_ = enabled;
  pending_enabled_ = enabled;
  request_pending_ = true;
  return true;
}

bool OutputAutomationControl::hardSafetyActive(const SafetyEnvelope& safety) noexcept {
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

bool OutputAutomationControl::completeArming() noexcept {
  if (!arming_completion_pending_) {
    return true;
  }
  if (lifecycle_executor_.active()) {
    return true;
  }
  if (lifecycle_.mode() != SupervisorMode::Arming) {
    arming_completion_pending_ = false;
    return lifecycle_.mode() == SupervisorMode::Automatic;
  }
  const auto transition = lifecycle_.apply(OutputLifecycleCommand::ArmingSucceeded);
  if (transition.status != OutputLifecycleTransitionStatus::Applied &&
      transition.status != OutputLifecycleTransitionStatus::NoChange) {
    return false;
  }
  arming_completion_pending_ = false;
  return lifecycle_.mode() == SupervisorMode::Automatic;
}

bool OutputAutomationControl::applyPendingRequest(std::uint64_t monotonic_ms,
                                                  const ScheduleIntent& schedule) noexcept {
  if (!request_pending_ || lifecycle_executor_.active()) {
    return true;
  }

  if (pending_enabled_) {
    if (lifecycle_.mode() == SupervisorMode::Automatic) {
      request_pending_ = false;
      return true;
    }
    if (lifecycle_.mode() == SupervisorMode::Arming) {
      arming_completion_pending_ = true;
      request_pending_ = false;
      return true;
    }
    if (lifecycle_.mode() != SupervisorMode::Disabled) {
      return false;
    }
    const auto transition = lifecycle_.apply(OutputLifecycleCommand::EnableAutomation);
    if (transition.status != OutputLifecycleTransitionStatus::Applied &&
        transition.status != OutputLifecycleTransitionStatus::NoChange) {
      return false;
    }
    arming_completion_pending_ = lifecycle_.mode() == SupervisorMode::Arming;
    request_pending_ = false;
    return arming_completion_pending_ || lifecycle_.mode() == SupervisorMode::Automatic;
  }

  if (lifecycle_.mode() == SupervisorMode::Disabled) {
    request_pending_ = false;
    return true;
  }
  if (lifecycle_.mode() != SupervisorMode::Automatic) {
    return false;
  }

  const auto transition = lifecycle_.apply(OutputLifecycleCommand::DisableAutomation);
  if (transition.status != OutputLifecycleTransitionStatus::Applied ||
      !transition.has_policy_event ||
      transition.policy_event != OutputLifecycleEvent::AutomationOff) {
    return false;
  }
  request_pending_ = false;
  return lifecycle_executor_.start(transition, monotonic_ms, schedule);
}

OutputAutomationControlReport
OutputAutomationControl::makeReport(bool safety_deferred) const noexcept {
  OutputAutomationControlReport report{};
  report.mode = lifecycle_.mode();
  report.requested_enabled = requested_enabled_;
  report.request_pending = request_pending_;
  report.safety_deferred = safety_deferred;
  report.lifecycle = lifecycle_executor_.report();
  report.lifecycle_active = lifecycle_executor_.active();

  if (!valid_) {
    report.status = OutputAutomationControlStatus::Invalid;
  } else if (report.mode == SupervisorMode::FaultLocked) {
    report.status = OutputAutomationControlStatus::FaultLocked;
  } else if (safety_deferred) {
    report.status = OutputAutomationControlStatus::SafetyDeferred;
  } else if (transitionActive()) {
    report.status = OutputAutomationControlStatus::TransitionPending;
  } else {
    report.status = OutputAutomationControlStatus::Ready;
  }
  return report;
}

OutputAutomationControlReport OutputAutomationControl::tick(
    std::uint64_t monotonic_ms, const ScheduleIntent& schedule,
    const SafetyEnvelope& safety) noexcept {
  if (!valid_) {
    return makeReport(false);
  }

  // Re-enable deliberately spends one complete main-loop cycle in Arming.
  // A request received while Arming may replace the desired state before this
  // completion point without creating an illegal lifecycle transition.
  if (arming_completion_pending_) {
    if (!completeArming()) {
      if (lifecycle_.mode() != SupervisorMode::FaultLocked) {
        (void)lifecycle_.apply(OutputLifecycleCommand::EnterFault);
      }
      return makeReport(false);
    }
  }

  if (!applyPendingRequest(monotonic_ms, schedule)) {
    if (lifecycle_.mode() != SupervisorMode::FaultLocked) {
      (void)lifecycle_.apply(OutputLifecycleCommand::EnterFault);
    }
    return makeReport(false);
  }

  const bool safety_deferred = lifecycle_executor_.active() && hardSafetyActive(safety);
  if (lifecycle_executor_.active() && !safety_deferred) {
    (void)lifecycle_executor_.tick(monotonic_ms);
  }
  return makeReport(safety_deferred);
}

} // namespace growbox::app::output
''')

write('test/test_output_automation_control/test_main.cpp', r'''#include "climate/output/OutputAutomationControl.h"
#include "climate/output/BinaryActuatorPolicy.h"
#include "climate/output/OutputSupervisorResolver.h"

#include <array>
#include <cassert>
#include <cstddef>
#include <cstdint>

namespace {
namespace output = growbox::app::output;
constexpr output::OutputEndpointId kFan = 1U;
constexpr output::OutputEndpointId kLamp = 2U;
constexpr output::OutputEndpointId kHumidifier = 3U;

class FakeTransport final : public output::OutputTransport {
public:
  output::TxResult send(const output::OutputCommand& command) noexcept override {
    assert(sent_count < sent.size());
    sent[sent_count++] = command;
    return next_result;
  }

  std::array<output::OutputCommand, 32U> sent{};
  std::size_t sent_count{0U};
  output::TxResult next_result{output::TransportStatus::Completed,
                               output::TransportError::None};
};

output::OutputPolicyConfig basePolicy() {
  return output::makeSafeDefaultOutputPolicyConfig(kFan, kLamp, kHumidifier);
}

void makeAutomationOffNoCommand(output::OutputPolicyConfig& policy) {
  const auto event = output::outputLifecycleEventIndex(output::OutputLifecycleEvent::AutomationOff);
  for (std::size_t index = 0U; index < policy.count; ++index) {
    auto& action = policy.endpoints[index].lifecycle[event];
    action.action = output::OutputPolicyAction::NoCommand;
    action.delay_ms = 0U;
    action.retransmit = false;
    action.max_retries = 0U;
  }
  assert(output::validateOutputPolicyConfig(policy) == output::OutputPolicyConfigStatus::Ok);
}

output::OutputStateStore makeStore() {
  output::OutputStateStore store;
  const std::array<output::OutputEndpointId, output::kOutputEndpointCapacity> endpoints{
      kFan, kLamp, kHumidifier};
  assert(store.configure(endpoints, endpoints.size()));
  return store;
}

output::OutputSupervisorResolverConfig makeResolverConfig(output::BinaryActuatorPolicy& fan,
                                                          output::BinaryActuatorPolicy& humidifier) {
  output::OutputSupervisorResolverConfig config{};
  config.endpoints[0] = {kLamp, nullptr};
  config.endpoints[1] = {kFan, &fan};
  config.endpoints[2] = {kHumidifier, &humidifier};
  config.count = 3U;
  return config;
}

void arm(output::OutputSupervisorLifecycle& lifecycle) {
  assert(lifecycle.apply(output::OutputLifecycleCommand::BeginArming).status ==
         output::OutputLifecycleTransitionStatus::Applied);
  assert(lifecycle.apply(output::OutputLifecycleCommand::ArmingSucceeded).status ==
         output::OutputLifecycleTransitionStatus::Applied);
  assert(lifecycle.mode() == output::SupervisorMode::Automatic);
}

output::ScheduleIntent lampSchedule(bool on) {
  output::ScheduleIntent schedule{};
  schedule.metadata.sequence = 10U;
  schedule.metadata.source = output::OutputSource::Schedule;
  schedule.metadata.reason = output::OutputReason::ScheduleRequest;
  assert(output::setEndpointIntent(schedule.endpoints[0], kLamp, on ? 1.0F : 0.0F));
  return schedule;
}

output::SafetyEnvelope fanSafety(output::SafetyConstraint constraint) {
  output::SafetyEnvelope safety{};
  safety.metadata.sequence = 20U;
  safety.metadata.source = output::OutputSource::Safety;
  safety.metadata.reason = output::OutputReason::ThermalSafety;
  assert(output::setSafetyConstraint(safety.endpoints[0], kFan, constraint,
                                     output::OutputReason::ThermalSafety));
  return safety;
}

void runUntilIdle(output::OutputAutomationControl& control, std::uint64_t& now,
                  const output::ScheduleIntent& schedule) {
  for (unsigned index = 0U; index < 8U && control.transitionActive(); ++index) {
    ++now;
    (void)control.tick(now, schedule, {});
  }
  assert(!control.transitionActive());
}

void testAllAutomationOffActionsExecuteThroughHighLevelRequest() {
  const std::array<output::OutputPolicyAction, 5U> actions{
      output::OutputPolicyAction::NoCommand, output::OutputPolicyAction::ForceOff,
      output::OutputPolicyAction::ForceOn, output::OutputPolicyAction::ApplySchedule,
      output::OutputPolicyAction::RestoreLastCommand};

  for (const auto action_kind : actions) {
    auto policy = basePolicy();
    makeAutomationOffNoCommand(policy);
    const auto event = output::outputLifecycleEventIndex(output::OutputLifecycleEvent::AutomationOff);
    output::OutputEndpointPolicy* target = nullptr;
    for (std::size_t index = 0U; index < policy.count; ++index) {
      if ((action_kind == output::OutputPolicyAction::ApplySchedule &&
           policy.endpoints[index].role == output::OutputEndpointRole::ScheduledLight) ||
          (action_kind != output::OutputPolicyAction::ApplySchedule &&
           policy.endpoints[index].role == output::OutputEndpointRole::ExhaustFan)) {
        target = &policy.endpoints[index];
        break;
      }
    }
    assert(target != nullptr);
    auto& action = target->lifecycle[event];
    action.action = action_kind;
    if (action_kind != output::OutputPolicyAction::NoCommand) {
      action.retransmit = true;
      action.max_retries = 0U;
    }
    assert(output::validateOutputPolicyConfig(policy) == output::OutputPolicyConfigStatus::Ok);

    auto store = makeStore();
    if (action_kind == output::OutputPolicyAction::RestoreLastCommand) {
      output::OutputCommand previous{};
      previous.endpoint = kFan;
      previous.state = output::BinaryOutputState::On;
      assert(store.recordAttempt(previous, 50U,
                                 {output::TransportStatus::Completed,
                                  output::TransportError::None}));
    }
    output::BinaryActuatorPolicy fan;
    output::BinaryActuatorPolicy humidifier;
    const auto resolver_config = makeResolverConfig(fan, humidifier);
    output::OutputSupervisorLifecycle lifecycle(policy);
    FakeTransport transport;
    output::OutputLifecycleExecutor executor(policy, lifecycle, transport, store, resolver_config);
    arm(lifecycle);
    output::OutputAutomationControl control(lifecycle, executor);
    assert(control.valid());
    assert(control.requestEnabled(false));

    std::uint64_t now = 1'000U;
    (void)control.tick(now, lampSchedule(true), {});
    runUntilIdle(control, now, lampSchedule(true));
    assert(control.mode() == output::SupervisorMode::Disabled);
    assert(!control.requestedEnabled());

    if (action_kind == output::OutputPolicyAction::NoCommand) {
      assert(transport.sent_count == 0U);
      continue;
    }
    assert(transport.sent_count == 1U);
    if (action_kind == output::OutputPolicyAction::ApplySchedule) {
      assert(transport.sent[0].endpoint == kLamp);
      assert(transport.sent[0].state == output::BinaryOutputState::On);
    } else {
      assert(transport.sent[0].endpoint == kFan);
      const auto expected = action_kind == output::OutputPolicyAction::ForceOff
                                ? output::BinaryOutputState::Off
                                : output::BinaryOutputState::On;
      assert(transport.sent[0].state == expected);
    }
  }
}

void testHardSafetyDefersLifecycleAndResolverStillExecutesSafety() {
  auto policy = basePolicy();
  makeAutomationOffNoCommand(policy);
  const auto event = output::outputLifecycleEventIndex(output::OutputLifecycleEvent::AutomationOff);
  auto* fan_policy = const_cast<output::OutputEndpointPolicy*>(
      output::findOutputPolicyRole(policy, output::OutputEndpointRole::ExhaustFan));
  assert(fan_policy != nullptr);
  fan_policy->lifecycle[event].action = output::OutputPolicyAction::ForceOff;
  fan_policy->lifecycle[event].retransmit = true;
  fan_policy->lifecycle[event].max_retries = 0U;
  assert(output::validateOutputPolicyConfig(policy) == output::OutputPolicyConfigStatus::Ok);

  auto store = makeStore();
  output::BinaryActuatorPolicy fan;
  output::BinaryActuatorPolicy humidifier;
  const auto resolver_config = makeResolverConfig(fan, humidifier);
  output::OutputSupervisorLifecycle lifecycle(policy);
  FakeTransport transport;
  output::OutputLifecycleExecutor executor(policy, lifecycle, transport, store, resolver_config);
  arm(lifecycle);
  output::OutputAutomationControl control(lifecycle, executor);
  assert(control.requestEnabled(false));

  const auto safety = fanSafety(output::SafetyConstraint::ForceOn);
  const auto report = control.tick(2'000U, lampSchedule(false), safety);
  assert(report.mode == output::SupervisorMode::Disabled);
  assert(report.safety_deferred);
  assert(executor.active());
  assert(transport.sent_count == 0U);

  output::OutputSupervisorResolver resolver(resolver_config);
  output::OutputSupervisorCycleInput input{};
  input.mode = control.mode();
  input.monotonic_ms = 2'000U;
  input.safety = safety;
  assert(output::setEndpointIntent(input.control.endpoints[0], kFan, 0.0F));
  input.control.metadata.sequence = 30U;
  output::OutputSupervisorResolution resolution{};
  assert(resolver.resolve(input, store, resolution));
  assert(resolution.plan.size == 1U);
  assert(resolution.plan.steps[0].endpoint == kFan);
  assert(resolution.plan.steps[0].state == output::BinaryOutputState::On);
  assert(resolution.plan.steps[0].source == output::OutputSource::Safety);

  (void)control.tick(2'001U, lampSchedule(false), {});
  assert(transport.sent_count == 1U);
  assert(transport.sent[0].state == output::BinaryOutputState::Off);
}

void testDisabledKeepsControlIntentObservableButSuppressesNormalExecution() {
  auto policy = basePolicy();
  makeAutomationOffNoCommand(policy);
  auto store = makeStore();
  output::BinaryActuatorPolicy fan;
  output::BinaryActuatorPolicy humidifier;
  const auto resolver_config = makeResolverConfig(fan, humidifier);
  output::OutputSupervisorLifecycle lifecycle(policy);
  FakeTransport transport;
  output::OutputLifecycleExecutor executor(policy, lifecycle, transport, store, resolver_config);
  arm(lifecycle);
  output::OutputAutomationControl control(lifecycle, executor);
  assert(control.requestEnabled(false));
  (void)control.tick(3'000U, lampSchedule(false), {});
  assert(control.mode() == output::SupervisorMode::Disabled);

  output::ControlIntent calculated{};
  calculated.metadata.sequence = 77U;
  calculated.metadata.source = output::OutputSource::Climate;
  calculated.metadata.reason = output::OutputReason::ClimateDecision;
  assert(output::setEndpointIntent(calculated.endpoints[0], kFan, 1.0F));

  output::OutputSupervisorResolver resolver(resolver_config);
  output::OutputSupervisorCycleInput input{};
  input.mode = control.mode();
  input.monotonic_ms = 3'001U;
  input.control = calculated;
  output::OutputSupervisorResolution resolution{};
  assert(resolver.resolve(input, store, resolution));
  assert(resolution.plan.size == 0U);
  assert(output::endpointIntentActive(calculated.endpoints[0]));
  assert(calculated.endpoints[0].level == 1.0F);
  assert(calculated.metadata.sequence == 77U);
}

void testReenableSpendsOneCycleInArmingBeforeAutomatic() {
  auto policy = basePolicy();
  makeAutomationOffNoCommand(policy);
  auto store = makeStore();
  output::BinaryActuatorPolicy fan;
  output::BinaryActuatorPolicy humidifier;
  const auto resolver_config = makeResolverConfig(fan, humidifier);
  output::OutputSupervisorLifecycle lifecycle(policy);
  FakeTransport transport;
  output::OutputLifecycleExecutor executor(policy, lifecycle, transport, store, resolver_config);
  arm(lifecycle);
  output::OutputAutomationControl control(lifecycle, executor);

  assert(control.requestEnabled(false));
  (void)control.tick(4'000U, lampSchedule(false), {});
  assert(control.mode() == output::SupervisorMode::Disabled);
  assert(control.requestEnabled(true));
  const auto arming = control.tick(4'001U, lampSchedule(false), {});
  assert(arming.mode == output::SupervisorMode::Arming);
  assert(arming.requested_enabled);
  assert(control.transitionActive());
  const auto automatic = control.tick(4'002U, lampSchedule(false), {});
  assert(automatic.mode == output::SupervisorMode::Automatic);
  assert(!control.transitionActive());
}

} // namespace

int main() {
  testAllAutomationOffActionsExecuteThroughHighLevelRequest();
  testHardSafetyDefersLifecycleAndResolverStillExecutesSafety();
  testDisabledKeepsControlIntentObservableButSuppressesNormalExecution();
  testReenableSpendsOneCycleInArmingBeforeAutomatic();
  return 0;
}
''')

replace_once('src/CMakeLists.txt',
'''    "climate/output/OutputSupervisorLifecycle.cpp"\n    "climate/output/OutputExecutionProjection.cpp"''',
'''    "climate/output/OutputSupervisorLifecycle.cpp"\n    "climate/output/OutputAutomationControl.cpp"\n    "climate/output/OutputExecutionProjection.cpp"''')

replace_once('test/host/CMakeLists.txt',
'''target_compile_options(output_supervisor_lifecycle_tests PRIVATE -Wall -Wextra -Wpedantic)\n\nadd_executable(\n  climate_semantic_output_tests''',
'''target_compile_options(output_supervisor_lifecycle_tests PRIVATE -Wall -Wextra -Wpedantic)\n\nadd_executable(\n  output_automation_control_tests\n  "${PROJECT_ROOT}/test/test_output_automation_control/test_main.cpp"\n  "${PROJECT_ROOT}/src/climate/output/OutputAutomationControl.cpp"\n  "${PROJECT_ROOT}/src/climate/output/OutputLifecycleExecutor.cpp"\n  "${PROJECT_ROOT}/src/climate/output/OutputSupervisorLifecycle.cpp"\n  "${PROJECT_ROOT}/src/climate/output/OutputSupervisorResolver.cpp"\n  "${PROJECT_ROOT}/src/climate/output/OutputPolicyConfig.cpp"\n  "${PROJECT_ROOT}/src/climate/output/OutputStateStore.cpp"\n  "${PROJECT_ROOT}/src/climate/output/BinaryActuatorPolicy.cpp"\n)\ntarget_include_directories(output_automation_control_tests PRIVATE "${PROJECT_ROOT}/src")\ntarget_compile_features(output_automation_control_tests PRIVATE cxx_std_17)\ntarget_compile_options(output_automation_control_tests PRIVATE -Wall -Wextra -Wpedantic)\n\nadd_executable(\n  climate_semantic_output_tests''')

replace_once('test/host/CMakeLists.txt',
'''add_test(NAME output_supervisor_lifecycle_tests COMMAND output_supervisor_lifecycle_tests)\nadd_test(NAME climate_semantic_output_tests COMMAND climate_semantic_output_tests)''',
'''add_test(NAME output_supervisor_lifecycle_tests COMMAND output_supervisor_lifecycle_tests)\nadd_test(NAME output_automation_control_tests COMMAND output_automation_control_tests)\nadd_test(NAME climate_semantic_output_tests COMMAND climate_semantic_output_tests)''')

replace_once('src/climate/runtime/Stage28ServiceConsoleCommand.h',
'''  RfReceive,\n  RtcSetUnix,''',
'''  RfReceive,\n  AutomationStatus,\n  AutomationEnable,\n  AutomationDisable,\n  RtcSetUnix,''')

replace_once('src/climate/runtime/Stage28ServiceConsoleCommand.cpp',
'''  if (count==3U && equalsIgnoreCase(tokens[0],"rtc") && equalsIgnoreCase(tokens[1],"set-unix")) {''',
'''  if (equalsIgnoreCase(tokens[0],"automation")) {\n    if (count==1U || (count==2U && equalsIgnoreCase(tokens[1],"status"))) { command.kind=ServiceConsoleCommandKind::AutomationStatus; return command; }\n    if (count==2U && equalsIgnoreCase(tokens[1],"on")) { command.kind=ServiceConsoleCommandKind::AutomationEnable; return command; }\n    if (count==2U && equalsIgnoreCase(tokens[1],"off")) { command.kind=ServiceConsoleCommandKind::AutomationDisable; return command; }\n    return invalidCommand();\n  }\n  if (count==3U && equalsIgnoreCase(tokens[0],"rtc") && equalsIgnoreCase(tokens[1],"set-unix")) {''')

replace_once('src/climate/runtime/Stage28ServiceConsole.h',
'''namespace growbox::app::climate_io::storage { class Stage27TelemetryLogger; }\n\nnamespace growbox::app::climate_io::runtime {''',
'''namespace growbox::app::climate_io::storage { class Stage27TelemetryLogger; }\nnamespace growbox::app::output { class OutputAutomationControl; }\n\nnamespace growbox::app::climate_io::runtime {''')

replace_once('src/climate/runtime/Stage28ServiceConsole.h',
'''    const RuntimeTimingMetrics* timing_metrics{nullptr};\n  };''',
'''    const RuntimeTimingMetrics* timing_metrics{nullptr};\n    ::growbox::app::output::OutputAutomationControl* automation_control{nullptr};\n  };''')

replace_once('src/climate/runtime/Stage28ServiceConsole.h',
'''  void handleRfReceive(const ServiceConsoleCommand& command) noexcept;\n  void handleRtcSetUnix''',
'''  void handleRfReceive(const ServiceConsoleCommand& command) noexcept;\n  void printAutomationStatus() noexcept;\n  void handleAutomationRequest(bool enabled) noexcept;\n  void handleRtcSetUnix''')

replace_once('src/climate/runtime/Stage28ServiceConsole.cpp',
'''#include "climate/runtime/Stage28ePlatformDiagnostics.h"''',
'''#include "climate/runtime/Stage28ePlatformDiagnostics.h"\n#include "climate/output/OutputAutomationControl.h"''')

replace_once('src/climate/runtime/Stage28ServiceConsole.cpp',
'''const char* stackMarginSeverityName(StackMarginSeverity severity) noexcept {''',
'''const char* supervisorModeName(::growbox::app::output::SupervisorMode mode) noexcept {\n  using ::growbox::app::output::SupervisorMode;\n  switch (mode) {\n  case SupervisorMode::BootLocked: return "boot-locked";\n  case SupervisorMode::Arming: return "arming";\n  case SupervisorMode::Automatic: return "automatic";\n  case SupervisorMode::Recovering: return "recovering";\n  case SupervisorMode::Disabled: return "disabled";\n  case SupervisorMode::FaultLocked: return "fault-locked";\n  case SupervisorMode::MaintenanceLocked: return "maintenance-locked";\n  }\n  return "unknown";\n}\n\nconst char* stackMarginSeverityName(StackMarginSeverity severity) noexcept {''')

replace_once('src/climate/runtime/Stage28ServiceConsole.cpp',
'''  case ServiceConsoleCommandKind::RfReceive:\n    handleRfReceive(command);\n    return;\n  case ServiceConsoleCommandKind::RtcSetUnix:''',
'''  case ServiceConsoleCommandKind::RfReceive:\n    handleRfReceive(command);\n    return;\n  case ServiceConsoleCommandKind::AutomationStatus:\n    printAutomationStatus();\n    return;\n  case ServiceConsoleCommandKind::AutomationEnable:\n    handleAutomationRequest(true);\n    return;\n  case ServiceConsoleCommandKind::AutomationDisable:\n    handleAutomationRequest(false);\n    return;\n  case ServiceConsoleCommandKind::RtcSetUnix:''')

replace_once('src/climate/runtime/Stage28ServiceConsole.cpp',
'''  writeText("  rtc set-unix <epoch>             set DS3231 from UTC Unix seconds\\r\\n");''',
'''  writeText("  automation [status]              show automation lifecycle state\\r\\n");\n  writeText("  automation on|off                request high-level automation mode\\r\\n");\n  writeText("  rtc set-unix <epoch>             set DS3231 from UTC Unix seconds\\r\\n");''')

replace_once('src/climate/runtime/Stage28ServiceConsole.cpp',
'''  writeText("Manual TX is not physical load-state acknowledgement.\\r\\n");\n}\n\nvoid Stage28ServiceConsole::printStatus''',
'''  writeText("Manual TX is not physical load-state acknowledgement.\\r\\n");\n}\n\nvoid Stage28ServiceConsole::printAutomationStatus() noexcept {\n  if (config_.automation_control == nullptr) {\n    writeText("automation unavailable\\r\\n");\n    return;\n  }\n  const auto& control = *config_.automation_control;\n  writeFormatted("automation mode=%s requested=%s transition_active=%d request_pending=%d\\r\\n",\n                 supervisorModeName(control.mode()), control.requestedEnabled() ? "on" : "off",\n                 control.transitionActive(), control.requestPending());\n}\n\nvoid Stage28ServiceConsole::handleAutomationRequest(bool enabled) noexcept {\n  if (config_.automation_control == nullptr) {\n    writeText("error: automation control unavailable\\r\\n");\n    return;\n  }\n  const bool accepted = config_.automation_control->requestEnabled(enabled);\n  writeFormatted("automation request=%s accepted=%d mode=%s\\r\\n", enabled ? "on" : "off",\n                 accepted, supervisorModeName(config_.automation_control->mode()));\n}\n\nvoid Stage28ServiceConsole::printStatus''')

replace_once('src/climate/runtime/Stage28ServiceConsole.cpp',
'''  if (config_.timing_metrics != nullptr) {''',
'''  if (config_.automation_control != nullptr) {\n    printAutomationStatus();\n  }\n\n  if (config_.timing_metrics != nullptr) {''')

replace_once('test/test_stage28_service_console/test_main.cpp',
'''void testNamedRfTransmitCommands(){''',
'''void testAutomationCommands(){auto c=parseServiceConsoleCommand("automation");assert(c.kind==ServiceConsoleCommandKind::AutomationStatus);c=parseServiceConsoleCommand("automation status");assert(c.kind==ServiceConsoleCommandKind::AutomationStatus);c=parseServiceConsoleCommand("AUTOMATION ON");assert(c.kind==ServiceConsoleCommandKind::AutomationEnable);c=parseServiceConsoleCommand("automation off");assert(c.kind==ServiceConsoleCommandKind::AutomationDisable);assert(parseServiceConsoleCommand("automation maybe").kind==ServiceConsoleCommandKind::Invalid);}\nvoid testNamedRfTransmitCommands(){''')

replace_once('test/test_stage28_service_console/test_main.cpp',
'''int main(){testReadOnlyMenuCommands();testNamedRfTransmitCommands();''',
'''int main(){testReadOnlyMenuCommands();testAutomationCommands();testNamedRfTransmitCommands();''')

replace_once('src/climate/ClimateV6RealInputRuntime.cpp',
'''#include "climate/output/BinaryActuatorPolicy.h"\n#include "climate/output/ClimateOutputSupervisorSink.h"''',
'''#include "climate/output/BinaryActuatorPolicy.h"\n#include "climate/output/ClimateOutputSupervisorSink.h"\n#include "climate/output/OutputAutomationControl.h"\n#include "climate/output/OutputLifecycleExecutor.h"\n#include "climate/output/OutputSupervisorLifecycle.h"''')

old_console = '''  runtime::RuntimeTimingMetrics runtime_timing{};\n  runtime_timing.loop_active.budget_us = kTickIntervalMs * 1000U;\n  runtime::Stage28ServiceConsole service_console(\n      {GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED != 0, GROWBOX_FIRMWARE_GIT_SHA,\n       &real_output_ready, &storage_logger, &runtime_timing},\n      ble, scd41, clock, rf_diagnostics);\n  const bool service_console_ready = service_console.begin();\n\n'''
replace_once('src/climate/ClimateV6RealInputRuntime.cpp', old_console,
'''  runtime::RuntimeTimingMetrics runtime_timing{};\n  runtime_timing.loop_active.budget_us = kTickIntervalMs * 1000U;\n\n''')

replace_once('src/climate/ClimateV6RealInputRuntime.cpp',
'''  RuntimeOutputTransport supervisor_transport(rf_output_transport, real_output_ready);\n  output::OutputSupervisorResolver supervisor_resolver(supervisor_config);''',
'''  RuntimeOutputTransport supervisor_transport(rf_output_transport, real_output_ready);\n  const output::OutputPolicyConfig output_policy = stage28d::makeOutputPolicyConfig();\n  output::OutputSupervisorLifecycle output_lifecycle(output_policy);\n  output::OutputLifecycleExecutor lifecycle_executor(output_policy, output_lifecycle,\n                                                     supervisor_transport, output_state_store,\n                                                     supervisor_config);\n  bool lifecycle_ready = output_lifecycle.valid() && lifecycle_executor.valid();\n  if (lifecycle_ready) {\n    const auto begin_arming = output_lifecycle.apply(output::OutputLifecycleCommand::BeginArming);\n    const auto armed = output_lifecycle.apply(output::OutputLifecycleCommand::ArmingSucceeded);\n    lifecycle_ready = begin_arming.status == output::OutputLifecycleTransitionStatus::Applied &&\n                      armed.status == output::OutputLifecycleTransitionStatus::Applied &&\n                      output_lifecycle.mode() == output::SupervisorMode::Automatic;\n  }\n  output::OutputAutomationControl automation_control(output_lifecycle, lifecycle_executor);\n  lifecycle_ready = lifecycle_ready && automation_control.valid();\n\n  output::OutputSupervisorResolver supervisor_resolver(supervisor_config);''')

replace_once('src/climate/ClimateV6RealInputRuntime.cpp',
'''  if (!supervisor_sink.valid()) {\n    ESP_LOGE(kTag, "Output supervisor composition invalid; real outputs remain locked");''',
'''  if (!supervisor_sink.valid() || !lifecycle_ready) {\n    ESP_LOGE(kTag, "Output supervisor/lifecycle composition invalid; real outputs remain locked");''')

replace_once('src/climate/ClimateV6RealInputRuntime.cpp',
'''  static RuntimeControlOwner runtime_control_owner;''',
'''  runtime::Stage28ServiceConsole service_console(\n      {GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED != 0, GROWBOX_FIRMWARE_GIT_SHA,\n       &real_output_ready, &storage_logger, &runtime_timing, &automation_control},\n      ble, scd41, clock, rf_diagnostics);\n  const bool service_console_ready = service_console.begin();\n\n  static RuntimeControlOwner runtime_control_owner;''')

replace_once('src/climate/ClimateV6RealInputRuntime.cpp',
'''      ClimateOutputSupervisorCycleContext supervisor_context{};\n      supervisor_context.mode = output::SupervisorMode::Automatic;\n      supervisor_context.schedule = schedule_intent;\n      supervisor_context.safety = safety_snapshot.envelope;\n      supervisor_sink.setCycleContext(supervisor_context);\n\n      loop_result = application.tick(now_ms, decision);''',
'''      const auto automation_report =\n          automation_control.tick(now_ms, schedule_intent, safety_snapshot.envelope);\n\n      ClimateOutputSupervisorCycleContext supervisor_context{};\n      supervisor_context.mode = automation_report.mode;\n      supervisor_context.schedule = schedule_intent;\n      supervisor_context.safety = safety_snapshot.envelope;\n      supervisor_sink.setCycleContext(supervisor_context);\n\n      loop_result = application.tick(now_ms, decision);''')

replace_once('src/climate/ClimateV6RealInputRuntime.cpp',
'''               "humidifier_known=%d humidifier_on=%d safety_latched=%d force_fan=%d "\n               "safety_reason=%u requested_fan=%.3f requested_humidifier=%.3f "''',
'''               "humidifier_known=%d humidifier_on=%d safety_latched=%d force_fan=%d "\n               "safety_reason=%u supervisor_mode=%u automation_requested=%d lifecycle_active=%d "\n               "requested_fan=%.3f requested_humidifier=%.3f "''')

replace_once('src/climate/ClimateV6RealInputRuntime.cpp',
'''               lamp_decision.thermal_latched, lamp_decision.force_exhaust_on,\n               static_cast<unsigned>(lamp_decision.reason),\n               static_cast<double>(decision.rule.safe.exhaust_fan),''',
'''               lamp_decision.thermal_latched, lamp_decision.force_exhaust_on,\n               static_cast<unsigned>(lamp_decision.reason),\n               static_cast<unsigned>(output_lifecycle.mode()), automation_control.requestedEnabled(),\n               automation_control.transitionActive(),\n               static_cast<double>(decision.rule.safe.exhaust_fan),''')

print('A8_4_EDIT_PASS')
