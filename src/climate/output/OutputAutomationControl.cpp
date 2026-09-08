#include "climate/output/OutputAutomationControl.h"

namespace growbox::app::output {

OutputAutomationControl::OutputAutomationControl(
    OutputSupervisorLifecycle& lifecycle, OutputLifecycleExecutor& lifecycle_executor) noexcept
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

OutputAutomationControlReport OutputAutomationControl::tick(std::uint64_t monotonic_ms,
                                                            const ScheduleIntent& schedule,
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
