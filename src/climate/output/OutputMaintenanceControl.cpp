#include "climate/output/OutputMaintenanceControl.h"

#include <cstddef>

namespace growbox::app::output {

OutputMaintenanceControl::OutputMaintenanceControl(
    const OutputPolicyConfig& policy, OutputSupervisorLifecycle& lifecycle,
    OutputAutomationControl& automation_control, OutputLifecycleExecutor& lifecycle_executor,
    OutputStateStore& state_store, OutputSupervisorResolverConfig resolver_config,
    OutputTransport& raw_transport) noexcept
    : policy_(policy), lifecycle_(lifecycle), automation_control_(automation_control),
      lifecycle_executor_(lifecycle_executor), state_store_(state_store),
      resolver_config_(resolver_config), raw_transport_(raw_transport) {
  valid_ = validateOutputPolicyConfig(policy_) == OutputPolicyConfigStatus::Ok &&
           lifecycle_.valid() && automation_control_.valid() && lifecycle_executor_.valid() &&
           state_store_.valid() && resolver_config_.count == policy_.count &&
           resolver_config_.count > 0U && resolver_config_.count <= kOutputEndpointCapacity;
  if (!valid_) {
    last_terminal_status_ = OutputMaintenanceStatus::Invalid;
    return;
  }
  for (std::size_t index = 0U; index < policy_.count; ++index) {
    const auto endpoint = policy_.endpoints[index].endpoint;
    if (state_store_.find(endpoint) == nullptr || findBinding(endpoint) == nullptr) {
      valid_ = false;
      last_terminal_status_ = OutputMaintenanceStatus::Invalid;
      return;
    }
  }
}

const OutputSupervisorEndpointBinding*
OutputMaintenanceControl::findBinding(OutputEndpointId endpoint) const noexcept {
  const OutputSupervisorEndpointBinding* found = nullptr;
  for (std::size_t index = 0U; index < resolver_config_.count; ++index) {
    const auto& candidate = resolver_config_.endpoints[index];
    if (candidate.endpoint != endpoint) {
      continue;
    }
    if (found != nullptr) {
      return nullptr;
    }
    found = &candidate;
  }
  return found;
}

const SafetyEndpointConstraint*
OutputMaintenanceControl::findSafety(const SafetyEnvelope& safety,
                                     OutputEndpointId endpoint) noexcept {
  for (const auto& candidate : safety.endpoints) {
    if (safetyConstraintActive(candidate) && candidate.endpoint == endpoint) {
      return &candidate;
    }
  }
  return nullptr;
}

bool OutputMaintenanceControl::safetyVetoes(const SafetyEndpointConstraint* safety,
                                            BinaryOutputState state) noexcept {
  if (safety == nullptr || safety->constraint == SafetyConstraint::Allow) {
    return false;
  }
  if (safety->constraint == SafetyConstraint::Inhibit) {
    return true;
  }
  if (safety->constraint == SafetyConstraint::ForceOff) {
    return state == BinaryOutputState::On;
  }
  if (safety->constraint == SafetyConstraint::ForceOn) {
    return state == BinaryOutputState::Off;
  }
  return true;
}

bool OutputMaintenanceControl::binaryStateValid(BinaryOutputState state) noexcept {
  return state == BinaryOutputState::Off || state == BinaryOutputState::On;
}

std::uint64_t OutputMaintenanceControl::nextSequence() noexcept {
  ++sequence_;
  if (sequence_ == 0U) {
    ++sequence_;
  }
  return sequence_;
}

bool OutputMaintenanceControl::clearPhysicalUncertainty(OutputEndpointId endpoint) noexcept {
  return state_store_.clearPhysicalObservation(endpoint);
}

bool OutputMaintenanceControl::clearPhysicalUncertainty() noexcept {
  for (std::size_t index = 0U; index < policy_.count; ++index) {
    if (!clearPhysicalUncertainty(policy_.endpoints[index].endpoint)) {
      return false;
    }
  }
  return true;
}

void OutputMaintenanceControl::synchronizeBinary(const OutputCommand& command,
                                                 std::uint64_t monotonic_ms) noexcept {
  const auto* binding = findBinding(command.endpoint);
  if (binding != nullptr && binding->binary_policy != nullptr) {
    binding->binary_policy->synchronize(command.state, monotonic_ms);
  }
}

void OutputMaintenanceControl::failClosed() noexcept {
  enter_pending_ = false;
  exit_pending_ = false;
  rearm_pending_ = false;
  raw_pending_ = false;
  last_terminal_status_ = OutputMaintenanceStatus::FaultLocked;
  if (lifecycle_.valid() && lifecycle_.mode() != SupervisorMode::FaultLocked) {
    (void)lifecycle_.apply(OutputLifecycleCommand::EnterFault);
  }
}

bool OutputMaintenanceControl::requestEnter() noexcept {
  if (!valid_ || exit_pending_ || rearm_pending_ || raw_pending_ || enter_pending_) {
    return false;
  }
  if (lifecycle_.mode() == SupervisorMode::MaintenanceLocked) {
    return true;
  }
  if (lifecycle_.mode() == SupervisorMode::Automatic) {
    if (automation_control_.transitionActive() || !automation_control_.requestEnabled(false)) {
      last_terminal_status_ = OutputMaintenanceStatus::Busy;
      return false;
    }
    enter_pending_ = true;
    last_terminal_status_ = OutputMaintenanceStatus::EnterPending;
    return true;
  }
  if (lifecycle_.mode() == SupervisorMode::Disabled &&
      !automation_control_.transitionActive() && !lifecycle_executor_.active()) {
    enter_pending_ = true;
    last_terminal_status_ = OutputMaintenanceStatus::EnterPending;
    return true;
  }
  last_terminal_status_ = OutputMaintenanceStatus::ModeDenied;
  return false;
}

bool OutputMaintenanceControl::requestExit() noexcept {
  if (!valid_ || enter_pending_ || exit_pending_ || rearm_pending_ || raw_pending_) {
    return false;
  }
  if (lifecycle_.mode() != SupervisorMode::MaintenanceLocked ||
      automation_control_.transitionActive() || lifecycle_executor_.active()) {
    last_terminal_status_ = OutputMaintenanceStatus::ModeDenied;
    return false;
  }
  exit_pending_ = true;
  last_terminal_status_ = OutputMaintenanceStatus::ExitPending;
  return true;
}

bool OutputMaintenanceControl::requestRaw(OutputEndpointRole role, BinaryOutputState state,
                                          std::uint64_t monotonic_ms) noexcept {
  if (!valid_ || enter_pending_ || exit_pending_ || rearm_pending_ || raw_pending_) {
    last_terminal_status_ = OutputMaintenanceStatus::Busy;
    return false;
  }
  if (lifecycle_.mode() != SupervisorMode::MaintenanceLocked ||
      automation_control_.transitionActive() || lifecycle_executor_.active()) {
    last_terminal_status_ = OutputMaintenanceStatus::ModeDenied;
    return false;
  }
  if (!binaryStateValid(state)) {
    last_terminal_status_ = OutputMaintenanceStatus::Invalid;
    return false;
  }
  const auto* endpoint = findOutputPolicyRole(policy_, role);
  if (endpoint == nullptr || !isValidOutputEndpoint(endpoint->endpoint)) {
    last_terminal_status_ = OutputMaintenanceStatus::Invalid;
    return false;
  }
  raw_command_ = {};
  raw_command_.endpoint = endpoint->endpoint;
  raw_command_.state = state;
  raw_command_.source = OutputSource::Maintenance;
  raw_command_.reason = OutputReason::MaintenanceRequest;
  raw_command_.sequence = nextSequence();
  raw_command_.due_ms = monotonic_ms;
  raw_pending_ = true;
  has_raw_result_ = false;
  last_raw_transport_ = {};
  last_terminal_status_ = OutputMaintenanceStatus::RawPending;
  return true;
}

OutputMaintenanceReport OutputMaintenanceControl::tick(std::uint64_t monotonic_ms,
                                                        const SafetyEnvelope& safety) noexcept {
  if (!valid_) {
    last_terminal_status_ = OutputMaintenanceStatus::Invalid;
    return makeReport();
  }
  if (lifecycle_.mode() == SupervisorMode::FaultLocked) {
    enter_pending_ = false;
    exit_pending_ = false;
    rearm_pending_ = false;
    raw_pending_ = false;
    last_terminal_status_ = OutputMaintenanceStatus::FaultLocked;
    return makeReport();
  }

  if (rearm_pending_) {
    if (lifecycle_.mode() == SupervisorMode::Automatic &&
        !automation_control_.transitionActive()) {
      rearm_pending_ = false;
      last_terminal_status_ = OutputMaintenanceStatus::Ready;
    }
    return makeReport();
  }

  if (enter_pending_) {
    if (automation_control_.transitionActive() || lifecycle_executor_.active()) {
      return makeReport();
    }
    if (lifecycle_.mode() == SupervisorMode::MaintenanceLocked) {
      enter_pending_ = false;
      last_terminal_status_ = OutputMaintenanceStatus::Ready;
      return makeReport();
    }
    if (lifecycle_.mode() != SupervisorMode::Disabled) {
      failClosed();
      return makeReport();
    }
    const auto transition = lifecycle_.apply(OutputLifecycleCommand::EnterMaintenance);
    if (transition.status != OutputLifecycleTransitionStatus::Applied ||
        lifecycle_.mode() != SupervisorMode::MaintenanceLocked ||
        !clearPhysicalUncertainty()) {
      failClosed();
      return makeReport();
    }
    enter_pending_ = false;
    last_terminal_status_ = OutputMaintenanceStatus::Ready;
    return makeReport();
  }

  if (exit_pending_) {
    if (lifecycle_.mode() != SupervisorMode::MaintenanceLocked ||
        automation_control_.transitionActive() || lifecycle_executor_.active()) {
      failClosed();
      return makeReport();
    }
    const auto transition = lifecycle_.apply(OutputLifecycleCommand::ExitMaintenance);
    if (transition.status != OutputLifecycleTransitionStatus::Applied ||
        lifecycle_.mode() != SupervisorMode::Disabled ||
        !automation_control_.requestEnabled(true)) {
      failClosed();
      return makeReport();
    }
    exit_pending_ = false;
    rearm_pending_ = true;
    last_terminal_status_ = OutputMaintenanceStatus::ExitPending;
    return makeReport();
  }

  if (raw_pending_) {
    if (lifecycle_.mode() != SupervisorMode::MaintenanceLocked ||
        automation_control_.transitionActive() || lifecycle_executor_.active()) {
      raw_pending_ = false;
      last_terminal_status_ = OutputMaintenanceStatus::ModeDenied;
      return makeReport();
    }
    if (safetyVetoes(findSafety(safety, raw_command_.endpoint), raw_command_.state)) {
      raw_pending_ = false;
      has_raw_result_ = false;
      last_raw_transport_ = {};
      last_terminal_status_ = OutputMaintenanceStatus::SafetyVeto;
      return makeReport();
    }
    raw_command_.due_ms = monotonic_ms;
    if (!state_store_.recordDesired(raw_command_) || !state_store_.recordResolved(raw_command_) ||
        !clearPhysicalUncertainty(raw_command_.endpoint)) {
      failClosed();
      return makeReport();
    }
    const TxResult tx = raw_transport_.send(raw_command_);
    if (!state_store_.recordAttempt(raw_command_, monotonic_ms, tx)) {
      failClosed();
      return makeReport();
    }
    has_raw_result_ = true;
    last_raw_transport_ = tx;
    raw_pending_ = false;
    if (tx.status == TransportStatus::Completed) {
      synchronizeBinary(raw_command_, monotonic_ms);
      last_terminal_status_ = OutputMaintenanceStatus::Ready;
    } else {
      last_terminal_status_ = OutputMaintenanceStatus::TxFailed;
    }
  }
  return makeReport();
}

OutputMaintenanceReport OutputMaintenanceControl::makeReport() const noexcept {
  OutputMaintenanceReport value{};
  value.status = last_terminal_status_;
  value.mode = lifecycle_.mode();
  value.enter_pending = enter_pending_;
  value.exit_pending = exit_pending_;
  value.rearm_pending = rearm_pending_;
  value.raw_pending = raw_pending_;
  value.has_raw_result = has_raw_result_;
  value.raw_command = raw_command_;
  value.raw_transport = last_raw_transport_;
  value.physical = PhysicalOutputState::Unknown;
  if (!valid_) {
    value.status = OutputMaintenanceStatus::Invalid;
  } else if (value.mode == SupervisorMode::FaultLocked) {
    value.status = OutputMaintenanceStatus::FaultLocked;
  } else if (enter_pending_) {
    value.status = OutputMaintenanceStatus::EnterPending;
  } else if (exit_pending_ || rearm_pending_) {
    value.status = OutputMaintenanceStatus::ExitPending;
  } else if (raw_pending_) {
    value.status = OutputMaintenanceStatus::RawPending;
  }
  return value;
}

OutputMaintenanceReport OutputMaintenanceControl::report() const noexcept { return makeReport(); }

} // namespace growbox::app::output
