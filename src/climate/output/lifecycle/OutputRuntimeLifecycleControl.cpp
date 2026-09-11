#include "climate/output/lifecycle/OutputRuntimeLifecycleControl.h"

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

OutputRuntimeLifecycleReport
OutputRuntimeLifecycleControl::tick(std::uint64_t monotonic_ms,
                                    const SafetyEnvelope& safety) noexcept {
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
