from pathlib import Path

HEADER = r'''#pragma once

#include "climate/output/OutputSupervisorLifecycle.h"
#include "climate/output/OutputSupervisorResolver.h"
#include "climate/output/OutputTransport.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace growbox::app::output {

enum class OutputLifecycleExecutionStatus : std::uint8_t {
  Idle = 0U,
  Pending,
  Completed,
  CompletedWithFailures,
  FaultLocked,
  InvalidConfiguration,
  InvalidTransition,
  InvalidPlan,
  Busy,
};

struct OutputLifecycleExecutionReport {
  OutputLifecycleExecutionStatus status = OutputLifecycleExecutionStatus::Idle;
  bool active = false;
  bool containment_active = false;
  OutputLifecycleEvent event = OutputLifecycleEvent::Boot;
  std::uint8_t next_order = 0U;
  std::uint8_t terminal_failures = 0U;
  std::uint8_t current_attempts = 0U;
  bool has_last_result = false;
  ExecutionStepResult last_result{};
};

class OutputLifecycleExecutor final {
public:
  OutputLifecycleExecutor(const OutputPolicyConfig& policy,
                          OutputSupervisorLifecycle& lifecycle,
                          OutputTransport& transport,
                          OutputStateStore& state_store,
                          OutputSupervisorResolverConfig resolver_config) noexcept;

  bool valid() const noexcept { return valid_; }
  bool active() const noexcept { return active_; }
  OutputLifecycleExecutionStatus status() const noexcept { return status_; }

  bool start(const OutputLifecycleTransitionReport& transition, std::uint64_t monotonic_ms,
             const ScheduleIntent& schedule) noexcept;
  bool start(const OutputLifecycleTransitionReport& transition,
             std::uint64_t monotonic_ms) noexcept {
    return start(transition, monotonic_ms, ScheduleIntent{});
  }

  OutputLifecycleExecutionReport tick(std::uint64_t monotonic_ms) noexcept;
  OutputLifecycleExecutionReport report() const noexcept;

private:
  struct PendingStep {
    bool present = false;
    OutputLifecycleActionPolicy policy{};
    OutputCommand command{};
    std::uint8_t attempts = 0U;
  };

  bool validateComposition() const noexcept;
  const OutputSupervisorEndpointBinding* findBinding(OutputEndpointId endpoint) const noexcept;
  static bool timeReached(std::uint64_t now, std::uint64_t due) noexcept;
  static bool scheduleState(const ScheduleIntent& schedule, OutputEndpointId endpoint,
                            BinaryOutputState& state) noexcept;
  bool buildPlan(OutputLifecycleEvent event, std::uint64_t monotonic_ms,
                 const ScheduleIntent& schedule) noexcept;
  bool buildStep(const OutputEndpointPolicy& endpoint, OutputLifecycleEvent event,
                 std::uint64_t monotonic_ms, const ScheduleIntent& schedule,
                 PendingStep& step) noexcept;
  bool commandAlreadyCompleted(const OutputCommand& command) const noexcept;
  void synchronizeBinary(const OutputCommand& command, std::uint64_t monotonic_ms) noexcept;
  std::uint64_t nextSequence() noexcept;
  void clearPlan() noexcept;
  void finishPlan() noexcept;
  bool beginFaultContainment(std::uint64_t monotonic_ms) noexcept;
  void failClosed(OutputLifecycleExecutionStatus status) noexcept;

  OutputPolicyConfig policy_{};
  OutputSupervisorLifecycle& lifecycle_;
  OutputTransport& transport_;
  OutputStateStore& state_store_;
  OutputSupervisorResolverConfig resolver_config_{};
  std::array<PendingStep, kOutputEndpointCapacity> steps_{};
  ScheduleIntent schedule_snapshot_{};
  OutputLifecycleEvent event_{OutputLifecycleEvent::Boot};
  OutputLifecycleExecutionStatus status_{OutputLifecycleExecutionStatus::Idle};
  std::uint8_t cursor_{0U};
  std::uint8_t terminal_failures_{0U};
  std::uint64_t sequence_{0U};
  bool active_{false};
  bool containment_active_{false};
  bool valid_{false};
  bool has_last_result_{false};
  ExecutionStepResult last_result_{};
};

} // namespace growbox::app::output
'''

CPP = r'''#include "climate/output/OutputLifecycleExecutor.h"

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
  if (validateOutputPolicyConfig(policy_) != OutputPolicyConfigStatus::Ok ||
      !lifecycle_.valid() || !state_store_.valid() ||
      resolver_config_.count != policy_.count || resolver_config_.count == 0U ||
      resolver_config_.count > kOutputEndpointCapacity) {
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
                                        OutputLifecycleEvent event,
                                        std::uint64_t monotonic_ms,
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
  step.command.reason = event == OutputLifecycleEvent::Fault
                            ? OutputReason::FaultContainment
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

bool OutputLifecycleExecutor::buildPlan(OutputLifecycleEvent event,
                                        std::uint64_t monotonic_ms,
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
  containment_active_ = event_ == OutputLifecycleEvent::Fault &&
                        lifecycle_.mode() == SupervisorMode::FaultLocked;
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
'''

TEST = r'''#include "climate/output/OutputLifecycleExecutor.h"

#include <array>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <limits>

namespace {

namespace output = growbox::app::output;
constexpr output::OutputEndpointId kFan = 1U;
constexpr output::OutputEndpointId kLamp = 2U;
constexpr output::OutputEndpointId kHumidifier = 3U;

class ScriptedTransport final : public output::OutputTransport {
public:
  std::array<output::TxResult, 16U> scripted{};
  std::array<output::OutputCommand, 16U> sent{};
  std::size_t scripted_count = 0U;
  std::size_t scripted_index = 0U;
  std::size_t sent_count = 0U;

  output::TxResult send(const output::OutputCommand& command) noexcept override {
    assert(sent_count < sent.size());
    sent[sent_count++] = command;
    if (scripted_index < scripted_count) {
      return scripted[scripted_index++];
    }
    return {output::TransportStatus::Completed, output::TransportError::None};
  }
};

output::OutputPolicyConfig makePolicy() {
  auto policy = output::makeSafeDefaultOutputPolicyConfig(kFan, kLamp, kHumidifier);
  assert(output::validateOutputPolicyConfig(policy) == output::OutputPolicyConfigStatus::Ok);
  return policy;
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
  config.endpoints[0] = {kFan, &fan};
  config.endpoints[1] = {kLamp, nullptr};
  config.endpoints[2] = {kHumidifier, &humidifier};
  config.count = 3U;
  return config;
}

void noCommand(output::OutputLifecycleActionPolicy& action, std::uint8_t order) {
  action.action = output::OutputPolicyAction::NoCommand;
  action.order = order;
  action.delay_ms = 0U;
  action.retransmit = false;
  action.max_retries = 0U;
}

output::OutputLifecycleTransitionReport beginBoot(output::OutputSupervisorLifecycle& lifecycle) {
  const auto transition = lifecycle.apply(output::OutputLifecycleCommand::BeginArming);
  assert(transition.status == output::OutputLifecycleTransitionStatus::Applied);
  assert(transition.has_policy_event);
  assert(transition.policy_event == output::OutputLifecycleEvent::Boot);
  return transition;
}

void reachAutomatic(output::OutputSupervisorLifecycle& lifecycle) {
  const auto arming = lifecycle.apply(output::OutputLifecycleCommand::BeginArming);
  assert(arming.status == output::OutputLifecycleTransitionStatus::Applied);
  const auto ready = lifecycle.apply(output::OutputLifecycleCommand::ArmingSucceeded);
  assert(ready.after == output::SupervisorMode::Automatic);
}

void testOrderedZeroDelayExecutesOneStepPerTick() {
  auto policy = makePolicy();
  auto store = makeStore();
  output::BinaryActuatorPolicy fan;
  output::BinaryActuatorPolicy humidifier;
  output::OutputSupervisorLifecycle lifecycle(policy);
  ScriptedTransport transport;
  output::OutputLifecycleExecutor executor(policy, lifecycle, transport, store,
                                           makeResolverConfig(fan, humidifier));
  assert(executor.valid());

  const auto transition = beginBoot(lifecycle);
  assert(executor.start(transition, 100U));
  auto report = executor.tick(100U);
  assert(report.status == output::OutputLifecycleExecutionStatus::Pending);
  assert(transport.sent_count == 1U && transport.sent[0].endpoint == kLamp);
  report = executor.tick(100U);
  assert(report.status == output::OutputLifecycleExecutionStatus::Pending);
  assert(transport.sent_count == 2U && transport.sent[1].endpoint == kFan);
  report = executor.tick(100U);
  assert(report.status == output::OutputLifecycleExecutionStatus::Completed);
  assert(transport.sent_count == 3U && transport.sent[2].endpoint == kHumidifier);
  assert(fan.known() && fan.state() == output::BinaryOutputState::Off);
  assert(humidifier.known() && humidifier.state() == output::BinaryOutputState::Off);
}

void testDelayedStepIsNotEarlyAcrossMonotonicWrap() {
  auto policy = makePolicy();
  policy.endpoints[1].lifecycle[output::outputLifecycleEventIndex(output::OutputLifecycleEvent::Boot)]
      .delay_ms = 20U;
  assert(output::validateOutputPolicyConfig(policy) == output::OutputPolicyConfigStatus::Ok);
  auto store = makeStore();
  output::BinaryActuatorPolicy fan;
  output::BinaryActuatorPolicy humidifier;
  output::OutputSupervisorLifecycle lifecycle(policy);
  ScriptedTransport transport;
  output::OutputLifecycleExecutor executor(policy, lifecycle, transport, store,
                                           makeResolverConfig(fan, humidifier));

  const std::uint64_t start = std::numeric_limits<std::uint64_t>::max() - 10U;
  assert(executor.start(beginBoot(lifecycle), start));
  assert(executor.tick(start).status == output::OutputLifecycleExecutionStatus::Pending);
  assert(transport.sent_count == 0U);
  assert(executor.tick(8U).status == output::OutputLifecycleExecutionStatus::Pending);
  assert(transport.sent_count == 0U);
  assert(executor.tick(9U).status == output::OutputLifecycleExecutionStatus::Pending);
  assert(transport.sent_count == 1U && transport.sent[0].endpoint == kLamp);
}

void testRetryDoesNotAdvanceBinaryTruthUntilSuccess() {
  auto policy = makePolicy();
  const std::size_t boot = output::outputLifecycleEventIndex(output::OutputLifecycleEvent::Boot);
  noCommand(policy.endpoints[1].lifecycle[boot], 0U);
  policy.endpoints[0].lifecycle[boot].action = output::OutputPolicyAction::ForceOn;
  policy.endpoints[0].lifecycle[boot].order = 1U;
  policy.endpoints[0].lifecycle[boot].max_retries = 1U;
  noCommand(policy.endpoints[2].lifecycle[boot], 2U);
  assert(output::validateOutputPolicyConfig(policy) == output::OutputPolicyConfigStatus::Ok);

  auto store = makeStore();
  output::BinaryActuatorPolicy fan;
  output::BinaryActuatorPolicy humidifier;
  output::OutputSupervisorLifecycle lifecycle(policy);
  ScriptedTransport transport;
  transport.scripted_count = 2U;
  transport.scripted[0] = {output::TransportStatus::Failed, output::TransportError::IoFailure};
  transport.scripted[1] = {output::TransportStatus::Completed, output::TransportError::None};
  output::OutputLifecycleExecutor executor(policy, lifecycle, transport, store,
                                           makeResolverConfig(fan, humidifier));

  assert(executor.start(beginBoot(lifecycle), 1'000U));
  auto report = executor.tick(1'000U);
  assert(report.status == output::OutputLifecycleExecutionStatus::Pending);
  assert(report.current_attempts == 1U);
  assert(!fan.known());
  assert(store.find(kFan)->has_attempt);
  assert(!store.find(kFan)->has_successful_command);

  report = executor.tick(1'001U);
  assert(report.status == output::OutputLifecycleExecutionStatus::Completed);
  assert(transport.sent_count == 2U);
  assert(fan.known() && fan.state() == output::BinaryOutputState::On);
  assert(store.find(kFan)->has_successful_command);
  assert(store.find(kFan)->last_successful_command.state == output::BinaryOutputState::On);
  assert(store.find(kFan)->physical.state == output::PhysicalOutputState::Unknown);
}

void testRetryExhaustionEntersBoundedFaultContainment() {
  auto policy = makePolicy();
  policy.max_transition_failures = 1U;
  const std::size_t boot = output::outputLifecycleEventIndex(output::OutputLifecycleEvent::Boot);
  const std::size_t fault = output::outputLifecycleEventIndex(output::OutputLifecycleEvent::Fault);
  noCommand(policy.endpoints[1].lifecycle[boot], 0U);
  policy.endpoints[0].lifecycle[boot].action = output::OutputPolicyAction::ForceOn;
  policy.endpoints[0].lifecycle[boot].order = 1U;
  policy.endpoints[0].lifecycle[boot].max_retries = 2U;
  noCommand(policy.endpoints[2].lifecycle[boot], 2U);
  noCommand(policy.endpoints[1].lifecycle[fault], 0U);
  noCommand(policy.endpoints[0].lifecycle[fault], 1U);
  noCommand(policy.endpoints[2].lifecycle[fault], 2U);
  assert(output::validateOutputPolicyConfig(policy) == output::OutputPolicyConfigStatus::Ok);

  auto store = makeStore();
  output::BinaryActuatorPolicy fan;
  output::BinaryActuatorPolicy humidifier;
  output::OutputSupervisorLifecycle lifecycle(policy);
  ScriptedTransport transport;
  transport.scripted_count = 3U;
  for (std::size_t index = 0U; index < transport.scripted_count; ++index) {
    transport.scripted[index] = {output::TransportStatus::Failed, output::TransportError::IoFailure};
  }
  output::OutputLifecycleExecutor executor(policy, lifecycle, transport, store,
                                           makeResolverConfig(fan, humidifier));

  assert(executor.start(beginBoot(lifecycle), 2'000U));
  assert(executor.tick(2'000U).status == output::OutputLifecycleExecutionStatus::Pending);
  assert(executor.tick(2'001U).status == output::OutputLifecycleExecutionStatus::Pending);
  auto report = executor.tick(2'002U);
  assert(report.status == output::OutputLifecycleExecutionStatus::Pending);
  assert(report.containment_active);
  assert(report.event == output::OutputLifecycleEvent::Fault);
  assert(lifecycle.mode() == output::SupervisorMode::FaultLocked);
  assert(transport.sent_count == 3U);
  report = executor.tick(2'003U);
  assert(report.status == output::OutputLifecycleExecutionStatus::FaultLocked);
  assert(!report.active);
  assert(transport.sent_count == 3U);
  assert(!fan.known());
}

void testAutomationOffApplyScheduleUsesLifecycleCommandTruth() {
  auto policy = makePolicy();
  const std::size_t off = output::outputLifecycleEventIndex(output::OutputLifecycleEvent::AutomationOff);
  noCommand(policy.endpoints[0].lifecycle[off], 1U);
  noCommand(policy.endpoints[2].lifecycle[off], 2U);
  assert(output::validateOutputPolicyConfig(policy) == output::OutputPolicyConfigStatus::Ok);

  auto store = makeStore();
  output::BinaryActuatorPolicy fan;
  output::BinaryActuatorPolicy humidifier;
  output::OutputSupervisorLifecycle lifecycle(policy);
  reachAutomatic(lifecycle);
  const auto transition = lifecycle.apply(output::OutputLifecycleCommand::DisableAutomation);
  assert(transition.after == output::SupervisorMode::Disabled);

  output::ScheduleIntent schedule{};
  assert(output::setEndpointIntent(schedule.endpoints[0], kLamp, 1.0F));
  ScriptedTransport transport;
  output::OutputLifecycleExecutor executor(policy, lifecycle, transport, store,
                                           makeResolverConfig(fan, humidifier));
  assert(executor.start(transition, 3'000U, schedule));
  const auto report = executor.tick(3'000U);
  assert(report.status == output::OutputLifecycleExecutionStatus::Completed);
  assert(transport.sent_count == 1U);
  assert(transport.sent[0].endpoint == kLamp);
  assert(transport.sent[0].state == output::BinaryOutputState::On);
  assert(transport.sent[0].source == output::OutputSource::Lifecycle);
  assert(store.find(kLamp)->has_successful_command);
  assert(store.find(kLamp)->physical.state == output::PhysicalOutputState::Unknown);
}

void testRecoveryRestoreLastCommandRetransmitsWithoutPhysicalAssumption() {
  auto policy = makePolicy();
  const std::size_t recovery = output::outputLifecycleEventIndex(output::OutputLifecycleEvent::Recovery);
  noCommand(policy.endpoints[1].lifecycle[recovery], 0U);
  policy.endpoints[0].lifecycle[recovery].action = output::OutputPolicyAction::RestoreLastCommand;
  policy.endpoints[0].lifecycle[recovery].order = 1U;
  policy.endpoints[0].lifecycle[recovery].retransmit = true;
  policy.endpoints[0].lifecycle[recovery].max_retries = 1U;
  noCommand(policy.endpoints[2].lifecycle[recovery], 2U);
  assert(output::validateOutputPolicyConfig(policy) == output::OutputPolicyConfigStatus::Ok);

  auto store = makeStore();
  output::OutputCommand prior{};
  prior.endpoint = kFan;
  prior.state = output::BinaryOutputState::On;
  prior.source = output::OutputSource::Climate;
  assert(store.recordAttempt(prior, 4'000U,
                             {output::TransportStatus::Completed, output::TransportError::None}));
  assert(store.find(kFan)->physical.state == output::PhysicalOutputState::Unknown);

  output::BinaryActuatorPolicy fan;
  output::BinaryActuatorPolicy humidifier;
  output::OutputSupervisorLifecycle lifecycle(policy);
  reachAutomatic(lifecycle);
  const auto transition = lifecycle.apply(output::OutputLifecycleCommand::BeginRecovery);
  assert(transition.policy_event == output::OutputLifecycleEvent::Recovery);
  ScriptedTransport transport;
  output::OutputLifecycleExecutor executor(policy, lifecycle, transport, store,
                                           makeResolverConfig(fan, humidifier));
  assert(executor.start(transition, 4'100U));
  const auto report = executor.tick(4'100U);
  assert(report.status == output::OutputLifecycleExecutionStatus::Completed);
  assert(transport.sent_count == 1U);
  assert(transport.sent[0].endpoint == kFan);
  assert(transport.sent[0].state == output::BinaryOutputState::On);
  assert(transport.sent[0].source == output::OutputSource::Lifecycle);
  assert(fan.known() && fan.state() == output::BinaryOutputState::On);
  assert(store.find(kFan)->physical.state == output::PhysicalOutputState::Unknown);
}

void testRetransmitFalseDedupesFromSuccessfulCommandTruth() {
  auto policy = makePolicy();
  const std::size_t boot = output::outputLifecycleEventIndex(output::OutputLifecycleEvent::Boot);
  noCommand(policy.endpoints[1].lifecycle[boot], 0U);
  policy.endpoints[0].lifecycle[boot].action = output::OutputPolicyAction::ForceOff;
  policy.endpoints[0].lifecycle[boot].order = 1U;
  policy.endpoints[0].lifecycle[boot].retransmit = false;
  policy.endpoints[0].lifecycle[boot].max_retries = 0U;
  noCommand(policy.endpoints[2].lifecycle[boot], 2U);
  assert(output::validateOutputPolicyConfig(policy) == output::OutputPolicyConfigStatus::Ok);

  auto store = makeStore();
  output::OutputCommand prior{};
  prior.endpoint = kFan;
  prior.state = output::BinaryOutputState::Off;
  assert(store.recordAttempt(prior, 5'000U,
                             {output::TransportStatus::Completed, output::TransportError::None}));
  output::BinaryActuatorPolicy fan;
  output::BinaryActuatorPolicy humidifier;
  output::OutputSupervisorLifecycle lifecycle(policy);
  ScriptedTransport transport;
  output::OutputLifecycleExecutor executor(policy, lifecycle, transport, store,
                                           makeResolverConfig(fan, humidifier));

  assert(executor.start(beginBoot(lifecycle), 5'100U));
  const auto report = executor.tick(5'100U);
  assert(report.status == output::OutputLifecycleExecutionStatus::Completed);
  assert(transport.sent_count == 0U);
  assert(fan.known() && fan.state() == output::BinaryOutputState::Off);
  assert(fan.lastChangeMs() == 5'000U);
}

} // namespace

int main() {
  testOrderedZeroDelayExecutesOneStepPerTick();
  testDelayedStepIsNotEarlyAcrossMonotonicWrap();
  testRetryDoesNotAdvanceBinaryTruthUntilSuccess();
  testRetryExhaustionEntersBoundedFaultContainment();
  testAutomationOffApplyScheduleUsesLifecycleCommandTruth();
  testRecoveryRestoreLastCommandRetransmitsWithoutPhysicalAssumption();
  testRetransmitFalseDedupesFromSuccessfulCommandTruth();
  return 0;
}
'''

root = Path('.')
new_files = {
    'src/climate/output/OutputLifecycleExecutor.h': HEADER,
    'src/climate/output/OutputLifecycleExecutor.cpp': CPP,
    'test/test_output_lifecycle_executor/test_main.cpp': TEST,
}
for name, content in new_files.items():
    path = root / name
    if path.exists():
        raise SystemExit(f'already exists: {name}')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')

src_cmake = root / 'src/CMakeLists.txt'
text = src_cmake.read_text(encoding='utf-8')
anchor = '    "climate/output/OutputSupervisorLifecycle.cpp"\n'
if text.count(anchor) != 1:
    raise SystemExit('src CMake lifecycle anchor mismatch')
text = text.replace(anchor, anchor + '    "climate/output/OutputLifecycleExecutor.cpp"\n')
src_cmake.write_text(text, encoding='utf-8')

test_cmake = root / 'test/host/CMakeLists.txt'
text = test_cmake.read_text(encoding='utf-8')
anchor = 'target_compile_options(output_supervisor_lifecycle_tests PRIVATE -Wall -Wextra -Wpedantic)\n'
block = r'''

add_executable(
  output_lifecycle_executor_tests
  "${PROJECT_ROOT}/test/test_output_lifecycle_executor/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/output/OutputLifecycleExecutor.cpp"
  "${PROJECT_ROOT}/src/climate/output/OutputSupervisorLifecycle.cpp"
  "${PROJECT_ROOT}/src/climate/output/OutputPolicyConfig.cpp"
  "${PROJECT_ROOT}/src/climate/output/OutputStateStore.cpp"
  "${PROJECT_ROOT}/src/climate/output/BinaryActuatorPolicy.cpp"
)
target_include_directories(output_lifecycle_executor_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(output_lifecycle_executor_tests PRIVATE cxx_std_17)
target_compile_options(output_lifecycle_executor_tests PRIVATE -Wall -Wextra -Wpedantic)
'''
if text.count(anchor) != 1:
    raise SystemExit('host CMake lifecycle target anchor mismatch')
text = text.replace(anchor, anchor + block)
add_test_anchor = 'add_test(NAME output_supervisor_lifecycle_tests COMMAND output_supervisor_lifecycle_tests)\n'
if text.count(add_test_anchor) != 1:
    raise SystemExit('host CMake add_test anchor mismatch')
text = text.replace(add_test_anchor, add_test_anchor +
                    'add_test(NAME output_lifecycle_executor_tests COMMAND output_lifecycle_executor_tests)\n')
test_cmake.write_text(text, encoding='utf-8')

print('A8_3_EDIT_PASS')
