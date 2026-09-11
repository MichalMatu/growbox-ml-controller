#include "climate/output/lifecycle/OutputLifecycleExecutor.h"

#include <cmath>
#include <cstddef>

namespace growbox::app::output {

OutputLifecycleExecutor::OutputLifecycleExecutor(
    const OutputPolicyConfig& policy, OutputSupervisorLifecycle& lifecycle,
    OutputTransport& transport, OutputStateStore& state_store,
    OutputSupervisorResolverConfig resolver_config) noexcept
    : policy_(policy), lifecycle_(lifecycle), transport_(transport), state_store_(state_store),
      resolver_config_(resolver_config), valid_(validateComposition()) {
  if (!valid_) {
    status_ = OutputLifecycleExecutionStatus::InvalidConfiguration;
  }
}

bool OutputLifecycleExecutor::validateComposition() const noexcept {
  if (validateOutputPolicyConfig(policy_) != OutputPolicyConfigStatus::Ok || !lifecycle_.valid() ||
      !state_store_.valid() || resolver_config_.count != policy_.count ||
      resolver_config_.count == 0U || resolver_config_.count > kOutputEndpointCapacity) {
    return false;
  }

  for (std::size_t index = 0U; index < policy_.count; ++index) {
    const OutputEndpointId endpoint = policy_.endpoints[index].endpoint;
    if (state_store_.find(endpoint) == nullptr || findBinding(endpoint) == nullptr) {
      return false;
    }
  }
  for (std::size_t index = 0U; index < resolver_config_.count; ++index) {
    if (!isValidOutputEndpoint(resolver_config_.endpoints[index].endpoint)) {
      return false;
    }
    for (std::size_t previous = 0U; previous < index; ++previous) {
      if (resolver_config_.endpoints[previous].endpoint ==
          resolver_config_.endpoints[index].endpoint) {
        return false;
      }
    }
  }
  return true;
}

const OutputSupervisorEndpointBinding*
OutputLifecycleExecutor::findBinding(OutputEndpointId endpoint) const noexcept {
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

bool OutputLifecycleExecutor::timeReached(std::uint64_t now, std::uint64_t due) noexcept {
  constexpr std::uint64_t kHalfRange = std::uint64_t{1U} << 63U;
  return now == due || (now - due) < kHalfRange;
}

bool OutputLifecycleExecutor::scheduleState(const ScheduleIntent& schedule,
                                            OutputEndpointId endpoint,
                                            BinaryOutputState& state) noexcept {
  for (const auto& intent : schedule.endpoints) {
    if (!endpointIntentActive(intent) || intent.endpoint != endpoint) {
      continue;
    }
    if (!std::isfinite(intent.level)) {
      return false;
    }
    state = intent.level >= 0.5F ? BinaryOutputState::On : BinaryOutputState::Off;
    return true;
  }
  return false;
}

std::uint64_t OutputLifecycleExecutor::nextSequence() noexcept {
  ++sequence_;
  if (sequence_ == 0U) {
    ++sequence_;
  }
  return sequence_;
}

void OutputLifecycleExecutor::clearPlan() noexcept {
  steps_ = {};
  cursor_ = 0U;
  terminal_failures_ = 0U;
  has_last_result_ = false;
  last_result_ = {};
}

bool OutputLifecycleExecutor::buildStep(const OutputEndpointPolicy& endpoint,
                                        OutputLifecycleEvent event, std::uint64_t monotonic_ms,
                                        const ScheduleIntent& schedule,
                                        PendingStep& step) noexcept {
  const std::size_t event_index = outputLifecycleEventIndex(event);
  if (event_index >= endpoint.lifecycle.size()) {
    return false;
  }
  const auto& action = endpoint.lifecycle[event_index];
  step = {};
  step.policy = action;
  if (action.action == OutputPolicyAction::NoCommand) {
    return true;
  }

  step.present = true;
  step.command.endpoint = endpoint.endpoint;
  step.command.source = OutputSource::Lifecycle;
  step.command.reason = event == OutputLifecycleEvent::Fault ? OutputReason::FaultContainment
                                                             : OutputReason::LifecyclePolicy;
  step.command.sequence = nextSequence();
  step.command.due_ms = monotonic_ms + static_cast<std::uint64_t>(action.delay_ms);

  switch (action.action) {
  case OutputPolicyAction::ForceOff:
    step.command.state = BinaryOutputState::Off;
    return true;
  case OutputPolicyAction::ForceOn:
    step.command.state = BinaryOutputState::On;
    return true;
  case OutputPolicyAction::ApplySchedule:
    return scheduleState(schedule, endpoint.endpoint, step.command.state);
  case OutputPolicyAction::RestoreLastCommand: {
    const OutputStateEntry* state = state_store_.find(endpoint.endpoint);
    if (state == nullptr || !state->has_successful_command) {
      return false;
    }
    step.command.state = state->last_successful_command.state;
    return true;
  }
  case OutputPolicyAction::NoCommand:
    return true;
  }
  return false;
}

bool OutputLifecycleExecutor::buildPlan(OutputLifecycleEvent event, std::uint64_t monotonic_ms,
                                        const ScheduleIntent& schedule) noexcept {
  clearPlan();
  if (validateOutputPolicyConfig(policy_) != OutputPolicyConfigStatus::Ok) {
    return false;
  }
  for (std::size_t index = 0U; index < policy_.count; ++index) {
    const auto& endpoint = policy_.endpoints[index];
    const auto& action = endpoint.lifecycle[outputLifecycleEventIndex(event)];
    if (action.order >= steps_.size()) {
      return false;
    }
    PendingStep built{};
    if (!buildStep(endpoint, event, monotonic_ms, schedule, built)) {
      return false;
    }
    steps_[action.order] = built;
  }
  return true;
}

bool OutputLifecycleExecutor::commandAlreadyCompleted(const OutputCommand& command) const noexcept {
  const OutputStateEntry* state = state_store_.find(command.endpoint);
  return state != nullptr && state->has_successful_command &&
         state->last_successful_command.state == command.state;
}

void OutputLifecycleExecutor::synchronizeBinary(const OutputCommand& command,
                                                std::uint64_t monotonic_ms) noexcept {
  const auto* binding = findBinding(command.endpoint);
  if (binding != nullptr && binding->binary_policy != nullptr) {
    binding->binary_policy->synchronize(command.state, monotonic_ms);
  }
}

void OutputLifecycleExecutor::finishPlan() noexcept {
  active_ = false;
  if (containment_active_ ||
      (event_ == OutputLifecycleEvent::Fault && lifecycle_.mode() == SupervisorMode::FaultLocked)) {
    status_ = OutputLifecycleExecutionStatus::FaultLocked;
  } else if (terminal_failures_ != 0U) {
    status_ = OutputLifecycleExecutionStatus::CompletedWithFailures;
  } else {
    status_ = OutputLifecycleExecutionStatus::Completed;
  }
}

void OutputLifecycleExecutor::failClosed(OutputLifecycleExecutionStatus status) noexcept {
  active_ = false;
  status_ = status;
  if (lifecycle_.valid() && lifecycle_.mode() != SupervisorMode::FaultLocked) {
    lifecycle_.apply(OutputLifecycleCommand::EnterFault);
  }
}

bool OutputLifecycleExecutor::beginFaultContainment(std::uint64_t monotonic_ms) noexcept {
  if (containment_active_) {
    active_ = false;
    status_ = OutputLifecycleExecutionStatus::FaultLocked;
    return false;
  }

  const auto transition = lifecycle_.apply(OutputLifecycleCommand::EnterFault);
  if (lifecycle_.mode() != SupervisorMode::FaultLocked) {
    active_ = false;
    status_ = OutputLifecycleExecutionStatus::FaultLocked;
    return false;
  }

  event_ = OutputLifecycleEvent::Fault;
  containment_active_ = true;
  if (!buildPlan(event_, monotonic_ms, schedule_snapshot_)) {
    active_ = false;
    status_ = OutputLifecycleExecutionStatus::FaultLocked;
    return false;
  }
  active_ = true;
  status_ = OutputLifecycleExecutionStatus::Pending;
  (void)transition;
  return true;
}

bool OutputLifecycleExecutor::start(const OutputLifecycleTransitionReport& transition,
                                    std::uint64_t monotonic_ms,
                                    const ScheduleIntent& schedule) noexcept {
  if (!valid_) {
    status_ = OutputLifecycleExecutionStatus::InvalidConfiguration;
    return false;
  }
  if (active_) {
    status_ = OutputLifecycleExecutionStatus::Busy;
    return false;
  }
  if (transition.status != OutputLifecycleTransitionStatus::Applied ||
      !transition.has_policy_event || transition.generation != lifecycle_.generation() ||
      transition.after != lifecycle_.mode()) {
    status_ = OutputLifecycleExecutionStatus::InvalidTransition;
    return false;
  }

  schedule_snapshot_ = schedule;
  event_ = transition.policy_event;
  containment_active_ =
      event_ == OutputLifecycleEvent::Fault && lifecycle_.mode() == SupervisorMode::FaultLocked;
  if (!buildPlan(event_, monotonic_ms, schedule_snapshot_)) {
    failClosed(OutputLifecycleExecutionStatus::InvalidPlan);
    return false;
  }
  active_ = true;
  status_ = OutputLifecycleExecutionStatus::Pending;
  return true;
}

OutputLifecycleExecutionReport OutputLifecycleExecutor::tick(std::uint64_t monotonic_ms) noexcept {
  if (!active_) {
    return report();
  }

  while (cursor_ < policy_.count && !steps_[cursor_].present) {
    ++cursor_;
  }
  if (cursor_ >= policy_.count) {
    finishPlan();
    return report();
  }

  PendingStep& step = steps_[cursor_];
  if (!timeReached(monotonic_ms, step.command.due_ms)) {
    return report();
  }

  if (!step.policy.retransmit && commandAlreadyCompleted(step.command)) {
    const OutputStateEntry* state = state_store_.find(step.command.endpoint);
    const std::uint64_t truth_ms = state == nullptr ? monotonic_ms : state->last_successful_ms;
    synchronizeBinary(step.command, truth_ms);
    ++cursor_;
    while (cursor_ < policy_.count && !steps_[cursor_].present) {
      ++cursor_;
    }
    if (cursor_ >= policy_.count) {
      finishPlan();
    }
    return report();
  }

  if (!state_store_.recordDesired(step.command) || !state_store_.recordResolved(step.command)) {
    failClosed(OutputLifecycleExecutionStatus::InvalidPlan);
    return report();
  }

  const TxResult tx = transport_.send(step.command);
  if (!state_store_.recordAttempt(step.command, monotonic_ms, tx)) {
    failClosed(OutputLifecycleExecutionStatus::InvalidPlan);
    return report();
  }

  ++step.attempts;
  has_last_result_ = true;
  last_result_ = {step.command, tx, PhysicalOutputState::Unknown};

  if (tx.status == TransportStatus::Completed) {
    synchronizeBinary(step.command, monotonic_ms);
    ++cursor_;
    while (cursor_ < policy_.count && !steps_[cursor_].present) {
      ++cursor_;
    }
    if (cursor_ >= policy_.count) {
      finishPlan();
    }
    return report();
  }

  if (step.attempts <= step.policy.max_retries) {
    return report();
  }

  ++terminal_failures_;
  ++cursor_;
  if (containment_active_) {
    active_ = false;
    status_ = OutputLifecycleExecutionStatus::FaultLocked;
    return report();
  }
  if (terminal_failures_ >= policy_.max_transition_failures) {
    beginFaultContainment(monotonic_ms);
    return report();
  }

  while (cursor_ < policy_.count && !steps_[cursor_].present) {
    ++cursor_;
  }
  if (cursor_ >= policy_.count) {
    finishPlan();
  }
  return report();
}

bool OutputLifecycleExecutor::cancelPending() noexcept {
  if (!valid_) {
    return false;
  }
  if (!active_) {
    return true;
  }
  clearPlan();
  active_ = false;
  containment_active_ = false;
  status_ = OutputLifecycleExecutionStatus::Idle;
  event_ = OutputLifecycleEvent::Boot;
  return true;
}

OutputLifecycleExecutionReport OutputLifecycleExecutor::report() const noexcept {
  OutputLifecycleExecutionReport value{};
  value.status = status_;
  value.active = active_;
  value.containment_active = containment_active_;
  value.event = event_;
  value.next_order = cursor_;
  value.terminal_failures = terminal_failures_;
  if (active_ && cursor_ < steps_.size()) {
    value.current_attempts = steps_[cursor_].attempts;
  }
  value.has_last_result = has_last_result_;
  value.last_result = last_result_;
  return value;
}

} // namespace growbox::app::output
