#include "climate/output/BinaryActuatorPolicy.h"
#include "climate/output/OutputAutomationControl.h"
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
  output::TxResult next_result{output::TransportStatus::Completed, output::TransportError::None};
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

output::OutputSupervisorResolverConfig
makeResolverConfig(output::BinaryActuatorPolicy& fan, output::BinaryActuatorPolicy& humidifier) {
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
    const auto event =
        output::outputLifecycleEventIndex(output::OutputLifecycleEvent::AutomationOff);
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
      assert(store.recordAttempt(
          previous, 50U, {output::TransportStatus::Completed, output::TransportError::None}));
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
