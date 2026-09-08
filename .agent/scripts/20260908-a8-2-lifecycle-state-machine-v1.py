from pathlib import Path

src_cmake = Path('src/CMakeLists.txt')
host_cmake = Path('test/host/CMakeLists.txt')
header = Path('src/climate/output/OutputSupervisorLifecycle.h')
source = Path('src/climate/output/OutputSupervisorLifecycle.cpp')
test = Path('test/test_output_supervisor_lifecycle/test_main.cpp')

header.parent.mkdir(parents=True, exist_ok=True)
test.parent.mkdir(parents=True, exist_ok=True)

header.write_text(r'''#pragma once

#include "climate/output/OutputPolicyConfig.h"

#include <cstdint>

namespace growbox::app::output {

enum class OutputLifecycleCommand : std::uint8_t {
  BeginArming = 0U,
  ArmingSucceeded,
  ArmingFailed,
  DisableAutomation,
  EnableAutomation,
  BeginRecovery,
  RecoverySucceeded,
  RecoveryFailed,
  EnterFault,
  EnterMaintenance,
  ExitMaintenance,
};

enum class OutputLifecycleTransitionStatus : std::uint8_t {
  Applied = 0U,
  NoChange,
  InvalidPolicy,
  IllegalTransition,
};

enum class OutputLifecycleFaultReason : std::uint8_t {
  None = 0U,
  InvalidPolicy,
  IllegalTransition,
  ArmingFailed,
  RecoveryFailed,
  ExplicitFault,
};

struct OutputLifecycleTransitionReport {
  OutputLifecycleTransitionStatus status = OutputLifecycleTransitionStatus::NoChange;
  SupervisorMode before = SupervisorMode::BootLocked;
  SupervisorMode after = SupervisorMode::BootLocked;
  OutputLifecycleFaultReason fault = OutputLifecycleFaultReason::None;
  bool has_policy_event = false;
  OutputLifecycleEvent policy_event = OutputLifecycleEvent::Boot;
  std::uint64_t generation = 0U;
};

class OutputSupervisorLifecycle final {
public:
  explicit OutputSupervisorLifecycle(const OutputPolicyConfig& policy) noexcept;

  bool valid() const noexcept { return valid_; }
  SupervisorMode mode() const noexcept { return mode_; }
  OutputLifecycleFaultReason fault() const noexcept { return fault_; }
  std::uint64_t generation() const noexcept { return generation_; }
  bool normalExecutionEnabled() const noexcept { return mode_ == SupervisorMode::Automatic; }
  bool safetyEvaluationEnabled() const noexcept { return true; }

  OutputLifecycleTransitionReport apply(OutputLifecycleCommand command) noexcept;

private:
  OutputLifecycleTransitionReport transition(SupervisorMode next,
                                             OutputLifecycleFaultReason fault,
                                             bool has_policy_event,
                                             OutputLifecycleEvent policy_event) noexcept;
  OutputLifecycleTransitionReport noChange() const noexcept;
  OutputLifecycleTransitionReport failClosed(OutputLifecycleFaultReason fault) noexcept;

  bool valid_{false};
  SupervisorMode mode_{SupervisorMode::BootLocked};
  OutputLifecycleFaultReason fault_{OutputLifecycleFaultReason::None};
  std::uint64_t generation_{0U};
};

} // namespace growbox::app::output
''')

source.write_text(r'''#include "climate/output/OutputSupervisorLifecycle.h"

namespace growbox::app::output {

OutputSupervisorLifecycle::OutputSupervisorLifecycle(const OutputPolicyConfig& policy) noexcept
    : valid_(validateOutputPolicyConfig(policy) == OutputPolicyConfigStatus::Ok) {
  if (!valid_) {
    mode_ = SupervisorMode::FaultLocked;
    fault_ = OutputLifecycleFaultReason::InvalidPolicy;
  }
}

OutputLifecycleTransitionReport OutputSupervisorLifecycle::transition(
    SupervisorMode next, OutputLifecycleFaultReason fault, bool has_policy_event,
    OutputLifecycleEvent policy_event) noexcept {
  const SupervisorMode before = mode_;
  mode_ = next;
  fault_ = fault;
  ++generation_;
  if (generation_ == 0U) {
    ++generation_;
  }
  return {OutputLifecycleTransitionStatus::Applied, before, mode_, fault_, has_policy_event,
          policy_event, generation_};
}

OutputLifecycleTransitionReport OutputSupervisorLifecycle::noChange() const noexcept {
  return {OutputLifecycleTransitionStatus::NoChange, mode_, mode_, fault_, false,
          OutputLifecycleEvent::Boot, generation_};
}

OutputLifecycleTransitionReport
OutputSupervisorLifecycle::failClosed(OutputLifecycleFaultReason fault) noexcept {
  const SupervisorMode before = mode_;
  mode_ = SupervisorMode::FaultLocked;
  fault_ = fault;
  ++generation_;
  if (generation_ == 0U) {
    ++generation_;
  }
  return {OutputLifecycleTransitionStatus::IllegalTransition, before, mode_, fault_, true,
          OutputLifecycleEvent::Fault, generation_};
}

OutputLifecycleTransitionReport
OutputSupervisorLifecycle::apply(OutputLifecycleCommand command) noexcept {
  if (!valid_) {
    return {OutputLifecycleTransitionStatus::InvalidPolicy, mode_, mode_, fault_, false,
            OutputLifecycleEvent::Boot, generation_};
  }

  switch (command) {
  case OutputLifecycleCommand::BeginArming:
    if (mode_ == SupervisorMode::BootLocked) {
      return transition(SupervisorMode::Arming, OutputLifecycleFaultReason::None, true,
                        OutputLifecycleEvent::Boot);
    }
    if (mode_ == SupervisorMode::Arming) {
      return noChange();
    }
    break;

  case OutputLifecycleCommand::ArmingSucceeded:
    if (mode_ == SupervisorMode::Arming) {
      return transition(SupervisorMode::Automatic, OutputLifecycleFaultReason::None, false,
                        OutputLifecycleEvent::Boot);
    }
    if (mode_ == SupervisorMode::Automatic) {
      return noChange();
    }
    break;

  case OutputLifecycleCommand::ArmingFailed:
    if (mode_ == SupervisorMode::Arming) {
      return transition(SupervisorMode::FaultLocked, OutputLifecycleFaultReason::ArmingFailed,
                        true, OutputLifecycleEvent::Fault);
    }
    break;

  case OutputLifecycleCommand::DisableAutomation:
    if (mode_ == SupervisorMode::Automatic) {
      return transition(SupervisorMode::Disabled, OutputLifecycleFaultReason::None, true,
                        OutputLifecycleEvent::AutomationOff);
    }
    if (mode_ == SupervisorMode::Disabled) {
      return noChange();
    }
    break;

  case OutputLifecycleCommand::EnableAutomation:
    if (mode_ == SupervisorMode::Disabled) {
      return transition(SupervisorMode::Arming, OutputLifecycleFaultReason::None, false,
                        OutputLifecycleEvent::Boot);
    }
    if (mode_ == SupervisorMode::Automatic || mode_ == SupervisorMode::Arming) {
      return noChange();
    }
    break;

  case OutputLifecycleCommand::BeginRecovery:
    if (mode_ == SupervisorMode::Automatic || mode_ == SupervisorMode::FaultLocked) {
      return transition(SupervisorMode::Recovering, OutputLifecycleFaultReason::None, true,
                        OutputLifecycleEvent::Recovery);
    }
    if (mode_ == SupervisorMode::Recovering) {
      return noChange();
    }
    break;

  case OutputLifecycleCommand::RecoverySucceeded:
    if (mode_ == SupervisorMode::Recovering) {
      return transition(SupervisorMode::Automatic, OutputLifecycleFaultReason::None, false,
                        OutputLifecycleEvent::Recovery);
    }
    break;

  case OutputLifecycleCommand::RecoveryFailed:
    if (mode_ == SupervisorMode::Recovering) {
      return transition(SupervisorMode::FaultLocked, OutputLifecycleFaultReason::RecoveryFailed,
                        true, OutputLifecycleEvent::Fault);
    }
    break;

  case OutputLifecycleCommand::EnterFault:
    if (mode_ == SupervisorMode::FaultLocked) {
      return noChange();
    }
    return transition(SupervisorMode::FaultLocked, OutputLifecycleFaultReason::ExplicitFault, true,
                      OutputLifecycleEvent::Fault);

  case OutputLifecycleCommand::EnterMaintenance:
    if (mode_ == SupervisorMode::Disabled) {
      return transition(SupervisorMode::MaintenanceLocked, OutputLifecycleFaultReason::None, false,
                        OutputLifecycleEvent::AutomationOff);
    }
    if (mode_ == SupervisorMode::MaintenanceLocked) {
      return noChange();
    }
    break;

  case OutputLifecycleCommand::ExitMaintenance:
    if (mode_ == SupervisorMode::MaintenanceLocked) {
      return transition(SupervisorMode::Disabled, OutputLifecycleFaultReason::None, false,
                        OutputLifecycleEvent::AutomationOff);
    }
    if (mode_ == SupervisorMode::Disabled) {
      return noChange();
    }
    break;
  }

  return failClosed(OutputLifecycleFaultReason::IllegalTransition);
}

} // namespace growbox::app::output
''')

test.write_text(r'''#include "climate/output/OutputSupervisorLifecycle.h"

#include <cassert>

namespace output = growbox::app::output;

namespace {

output::OutputPolicyConfig validPolicy() {
  return output::makeSafeDefaultOutputPolicyConfig(1U, 2U, 3U);
}

output::OutputSupervisorLifecycle automaticLifecycle() {
  output::OutputSupervisorLifecycle lifecycle(validPolicy());
  auto report = lifecycle.apply(output::OutputLifecycleCommand::BeginArming);
  assert(report.status == output::OutputLifecycleTransitionStatus::Applied);
  assert(report.has_policy_event && report.policy_event == output::OutputLifecycleEvent::Boot);
  report = lifecycle.apply(output::OutputLifecycleCommand::ArmingSucceeded);
  assert(report.status == output::OutputLifecycleTransitionStatus::Applied);
  assert(lifecycle.mode() == output::SupervisorMode::Automatic);
  return lifecycle;
}

void testBootArmingAutomaticSequence() {
  output::OutputSupervisorLifecycle lifecycle(validPolicy());
  assert(lifecycle.valid());
  assert(lifecycle.mode() == output::SupervisorMode::BootLocked);
  assert(!lifecycle.normalExecutionEnabled());
  assert(lifecycle.safetyEvaluationEnabled());

  const auto arming = lifecycle.apply(output::OutputLifecycleCommand::BeginArming);
  assert(arming.before == output::SupervisorMode::BootLocked);
  assert(arming.after == output::SupervisorMode::Arming);
  assert(arming.has_policy_event && arming.policy_event == output::OutputLifecycleEvent::Boot);
  assert(arming.generation == 1U);

  const auto automatic = lifecycle.apply(output::OutputLifecycleCommand::ArmingSucceeded);
  assert(automatic.after == output::SupervisorMode::Automatic);
  assert(!automatic.has_policy_event);
  assert(automatic.generation == 2U);
  assert(lifecycle.normalExecutionEnabled());
}

void testDisableAndReenableAreExplicit() {
  auto lifecycle = automaticLifecycle();
  const auto disabled = lifecycle.apply(output::OutputLifecycleCommand::DisableAutomation);
  assert(disabled.after == output::SupervisorMode::Disabled);
  assert(disabled.has_policy_event);
  assert(disabled.policy_event == output::OutputLifecycleEvent::AutomationOff);
  assert(!lifecycle.normalExecutionEnabled());
  assert(lifecycle.safetyEvaluationEnabled());

  const auto duplicate_disable = lifecycle.apply(output::OutputLifecycleCommand::DisableAutomation);
  assert(duplicate_disable.status == output::OutputLifecycleTransitionStatus::NoChange);

  const auto rearming = lifecycle.apply(output::OutputLifecycleCommand::EnableAutomation);
  assert(rearming.after == output::SupervisorMode::Arming);
  assert(!rearming.has_policy_event);
  assert(!lifecycle.normalExecutionEnabled());
  const auto automatic = lifecycle.apply(output::OutputLifecycleCommand::ArmingSucceeded);
  assert(automatic.after == output::SupervisorMode::Automatic);
  assert(lifecycle.normalExecutionEnabled());
}

void testArmingFailureAndRecovery() {
  output::OutputSupervisorLifecycle lifecycle(validPolicy());
  lifecycle.apply(output::OutputLifecycleCommand::BeginArming);
  const auto failed = lifecycle.apply(output::OutputLifecycleCommand::ArmingFailed);
  assert(failed.after == output::SupervisorMode::FaultLocked);
  assert(failed.fault == output::OutputLifecycleFaultReason::ArmingFailed);
  assert(failed.has_policy_event && failed.policy_event == output::OutputLifecycleEvent::Fault);

  const auto recovering = lifecycle.apply(output::OutputLifecycleCommand::BeginRecovery);
  assert(recovering.after == output::SupervisorMode::Recovering);
  assert(recovering.has_policy_event);
  assert(recovering.policy_event == output::OutputLifecycleEvent::Recovery);
  const auto recovered = lifecycle.apply(output::OutputLifecycleCommand::RecoverySucceeded);
  assert(recovered.after == output::SupervisorMode::Automatic);
  assert(recovered.fault == output::OutputLifecycleFaultReason::None);
}

void testRecoveryFailureReturnsToFaultLocked() {
  auto lifecycle = automaticLifecycle();
  lifecycle.apply(output::OutputLifecycleCommand::BeginRecovery);
  const auto failed = lifecycle.apply(output::OutputLifecycleCommand::RecoveryFailed);
  assert(failed.after == output::SupervisorMode::FaultLocked);
  assert(failed.fault == output::OutputLifecycleFaultReason::RecoveryFailed);
  assert(failed.has_policy_event && failed.policy_event == output::OutputLifecycleEvent::Fault);
  assert(!lifecycle.normalExecutionEnabled());
  assert(lifecycle.safetyEvaluationEnabled());
}

void testIllegalTransitionFailsClosed() {
  output::OutputSupervisorLifecycle lifecycle(validPolicy());
  const auto illegal = lifecycle.apply(output::OutputLifecycleCommand::ArmingSucceeded);
  assert(illegal.status == output::OutputLifecycleTransitionStatus::IllegalTransition);
  assert(illegal.before == output::SupervisorMode::BootLocked);
  assert(illegal.after == output::SupervisorMode::FaultLocked);
  assert(illegal.fault == output::OutputLifecycleFaultReason::IllegalTransition);
  assert(illegal.has_policy_event && illegal.policy_event == output::OutputLifecycleEvent::Fault);
  assert(!lifecycle.normalExecutionEnabled());
}

void testInvalidPolicyStartsFaultLockedAndCannotTransition() {
  auto invalid = validPolicy();
  invalid.endpoints[1].endpoint = invalid.endpoints[0].endpoint;
  output::OutputSupervisorLifecycle lifecycle(invalid);
  assert(!lifecycle.valid());
  assert(lifecycle.mode() == output::SupervisorMode::FaultLocked);
  assert(lifecycle.fault() == output::OutputLifecycleFaultReason::InvalidPolicy);
  const auto report = lifecycle.apply(output::OutputLifecycleCommand::BeginRecovery);
  assert(report.status == output::OutputLifecycleTransitionStatus::InvalidPolicy);
  assert(report.after == output::SupervisorMode::FaultLocked);
}

void testMaintenanceRequiresDisabledQuiescence() {
  auto lifecycle = automaticLifecycle();
  lifecycle.apply(output::OutputLifecycleCommand::DisableAutomation);
  const auto entered = lifecycle.apply(output::OutputLifecycleCommand::EnterMaintenance);
  assert(entered.after == output::SupervisorMode::MaintenanceLocked);
  assert(!lifecycle.normalExecutionEnabled());
  const auto exited = lifecycle.apply(output::OutputLifecycleCommand::ExitMaintenance);
  assert(exited.after == output::SupervisorMode::Disabled);

  auto unsafe = automaticLifecycle();
  const auto rejected = unsafe.apply(output::OutputLifecycleCommand::EnterMaintenance);
  assert(rejected.status == output::OutputLifecycleTransitionStatus::IllegalTransition);
  assert(rejected.after == output::SupervisorMode::FaultLocked);
}

void testExplicitFaultIsAvailableFromNormalStates() {
  auto lifecycle = automaticLifecycle();
  const auto fault = lifecycle.apply(output::OutputLifecycleCommand::EnterFault);
  assert(fault.after == output::SupervisorMode::FaultLocked);
  assert(fault.fault == output::OutputLifecycleFaultReason::ExplicitFault);
  assert(fault.has_policy_event && fault.policy_event == output::OutputLifecycleEvent::Fault);
  const auto duplicate = lifecycle.apply(output::OutputLifecycleCommand::EnterFault);
  assert(duplicate.status == output::OutputLifecycleTransitionStatus::NoChange);
}

} // namespace

int main() {
  testBootArmingAutomaticSequence();
  testDisableAndReenableAreExplicit();
  testArmingFailureAndRecovery();
  testRecoveryFailureReturnsToFaultLocked();
  testIllegalTransitionFailsClosed();
  testInvalidPolicyStartsFaultLockedAndCannotTransition();
  testMaintenanceRequiresDisabledQuiescence();
  testExplicitFaultIsAvailableFromNormalStates();
  return 0;
}
''')

src = src_cmake.read_text()
needle = '    "climate/output/OutputPolicyConfig.cpp"\n'
assert needle in src
assert 'climate/output/OutputSupervisorLifecycle.cpp' not in src
src = src.replace(needle, needle + '    "climate/output/OutputSupervisorLifecycle.cpp"\n', 1)
src_cmake.write_text(src)

host = host_cmake.read_text()
marker = 'add_executable(\n  climate_semantic_output_tests\n'
assert marker in host
assert 'output_supervisor_lifecycle_tests' not in host
block = r'''add_executable(
  output_supervisor_lifecycle_tests
  "${PROJECT_ROOT}/test/test_output_supervisor_lifecycle/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/output/OutputSupervisorLifecycle.cpp"
  "${PROJECT_ROOT}/src/climate/output/OutputPolicyConfig.cpp"
)
target_include_directories(output_supervisor_lifecycle_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(output_supervisor_lifecycle_tests PRIVATE cxx_std_17)
target_compile_options(output_supervisor_lifecycle_tests PRIVATE -Wall -Wextra -Wpedantic)

'''
host = host.replace(marker, block + marker, 1)
add_test_marker = 'add_test(NAME climate_semantic_output_tests COMMAND climate_semantic_output_tests)\n'
assert add_test_marker in host
host = host.replace(add_test_marker,
                    'add_test(NAME output_supervisor_lifecycle_tests COMMAND output_supervisor_lifecycle_tests)\n' + add_test_marker,
                    1)
host_cmake.write_text(host)

print('A8_2_EDIT_PASS')
