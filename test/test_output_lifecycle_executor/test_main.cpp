#include "climate/output/OutputLifecycleExecutor.h"

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
