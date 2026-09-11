#include "climate/output/lifecycle/OutputSupervisorLifecycle.h"

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
