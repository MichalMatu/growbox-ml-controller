#include "climate/output/supervisor/OutputSupervisorResolver.h"

#include <array>
#include <cassert>
#include <cstdint>

namespace {

namespace output = growbox::app::output;
constexpr output::OutputEndpointId kFan = 1U;
constexpr output::OutputEndpointId kLamp = 2U;
constexpr output::OutputEndpointId kHumidifier = 3U;

output::OutputStateStore makeStore() {
  output::OutputStateStore store;
  const std::array<output::OutputEndpointId, output::kOutputEndpointCapacity> endpoints{
      kFan, kLamp, kHumidifier};
  assert(store.configure(endpoints, endpoints.size()));
  return store;
}

output::OutputSupervisorResolver makeResolver(output::BinaryActuatorPolicy& fan,
                                              output::BinaryActuatorPolicy& humidifier) {
  output::OutputSupervisorResolverConfig config{};
  config.endpoints[0] = {kFan, &fan};
  config.endpoints[1] = {kLamp, nullptr};
  config.endpoints[2] = {kHumidifier, &humidifier};
  config.count = 3U;
  return output::OutputSupervisorResolver(config);
}

void setIntent(output::EndpointIntent& intent, output::OutputEndpointId endpoint, float level) {
  assert(output::setEndpointIntent(intent, endpoint, level));
}

void testRejectsInvalidConfigurationAndUnconfiguredStore() {
  output::OutputSupervisorResolver invalid({});
  assert(!invalid.valid());

  output::BinaryActuatorPolicy fan;
  output::BinaryActuatorPolicy humidifier;
  auto resolver = makeResolver(fan, humidifier);
  assert(resolver.valid());
  output::OutputStateStore empty_store;
  output::OutputSupervisorResolution resolution{};
  assert(!resolver.resolve({}, empty_store, resolution));
  assert(resolution.plan.size == 0U);
}

void testManualScheduleClimatePrecedence() {
  output::BinaryActuatorPolicy fan;
  output::BinaryActuatorPolicy humidifier;
  auto resolver = makeResolver(fan, humidifier);
  auto store = makeStore();

  output::OutputSupervisorCycleInput input{};
  input.monotonic_ms = 100U;
  setIntent(input.control.endpoints[0], kLamp, 1.0F);
  input.control.metadata.reason = output::OutputReason::ClimateDecision;
  input.control.metadata.sequence = 1U;
  setIntent(input.schedule.endpoints[0], kLamp, 0.0F);
  input.schedule.metadata.reason = output::OutputReason::ScheduleRequest;
  input.schedule.metadata.sequence = 2U;
  setIntent(input.manual.endpoints[0], kLamp, 1.0F);
  input.manual.metadata.reason = output::OutputReason::ManualRequest;
  input.manual.metadata.sequence = 3U;

  output::OutputSupervisorResolution resolution{};
  assert(resolver.resolve(input, store, resolution));
  assert(resolution.plan.size == 1U);
  assert(resolution.plan.steps[0].endpoint == kLamp);
  assert(resolution.plan.steps[0].state == output::BinaryOutputState::On);
  assert(resolution.plan.steps[0].source == output::OutputSource::Manual);
  assert(resolution.plan.steps[0].sequence == 3U);

  input.manual = {};
  assert(resolver.resolve(input, store, resolution));
  assert(resolution.plan.size == 1U);
  assert(resolution.plan.steps[0].state == output::BinaryOutputState::Off);
  assert(resolution.plan.steps[0].source == output::OutputSource::Schedule);

  input.schedule = {};
  assert(resolver.resolve(input, store, resolution));
  assert(resolution.plan.size == 1U);
  assert(resolution.plan.steps[0].state == output::BinaryOutputState::On);
  assert(resolution.plan.steps[0].source == output::OutputSource::Climate);
}

void testSafetyOverridesManualAndCanActWithoutLowerIntent() {
  output::BinaryActuatorPolicyConfig policy_config{};
  policy_config.min_on_ms = 1'000U;
  policy_config.min_off_ms = 1'000U;
  output::BinaryActuatorPolicy fan(policy_config);
  output::BinaryActuatorPolicy humidifier(policy_config);
  auto resolver = makeResolver(fan, humidifier);
  auto store = makeStore();

  output::OutputSupervisorCycleInput input{};
  input.monotonic_ms = 200U;
  setIntent(input.manual.endpoints[0], kLamp, 1.0F);
  input.manual.metadata.sequence = 5U;
  assert(output::setSafetyConstraint(input.safety.endpoints[0], kLamp,
                                     output::SafetyConstraint::ForceOff,
                                     output::OutputReason::ThermalSafety));
  input.safety.metadata.sequence = 9U;

  output::OutputSupervisorResolution resolution{};
  assert(resolver.resolve(input, store, resolution));
  assert(resolution.plan.size == 1U);
  assert(resolution.plan.steps[0].state == output::BinaryOutputState::Off);
  assert(resolution.plan.steps[0].source == output::OutputSource::Safety);
  assert(resolution.plan.steps[0].reason == output::OutputReason::ThermalSafety);
  assert(resolution.plan.steps[0].sequence == 9U);

  input = {};
  input.monotonic_ms = 300U;
  assert(output::setSafetyConstraint(input.safety.endpoints[0], kFan,
                                     output::SafetyConstraint::ForceOn,
                                     output::OutputReason::ThermalSafety));
  input.safety.metadata.sequence = 10U;
  assert(resolver.resolve(input, store, resolution));
  assert(resolution.plan.size == 1U);
  assert(resolution.plan.steps[0].endpoint == kFan);
  assert(resolution.plan.steps[0].state == output::BinaryOutputState::On);
  assert(resolution.endpoints[0].has_policy_proposal);
  assert(resolution.endpoints[0].policy_proposal.bypass_dwell);
  assert(!fan.known());
}

void testInhibitSuppressesLowerCommand() {
  output::BinaryActuatorPolicy fan;
  output::BinaryActuatorPolicy humidifier;
  auto resolver = makeResolver(fan, humidifier);
  auto store = makeStore();

  output::OutputSupervisorCycleInput input{};
  input.monotonic_ms = 400U;
  setIntent(input.schedule.endpoints[0], kLamp, 1.0F);
  assert(output::setSafetyConstraint(input.safety.endpoints[0], kLamp,
                                     output::SafetyConstraint::Inhibit,
                                     output::OutputReason::ThermalSafety));

  output::OutputSupervisorResolution resolution{};
  assert(resolver.resolve(input, store, resolution));
  assert(resolution.plan.size == 0U);
  assert(resolution.endpoints[1].inhibited);
  assert(!resolution.endpoints[1].has_resolved_state);
}

void testBinaryPolicyProposalRequiresExternalCommitAndHonorsDwell() {
  output::BinaryActuatorPolicyConfig policy_config{};
  policy_config.on_threshold = 0.10F;
  policy_config.off_threshold = 0.03F;
  policy_config.min_on_ms = 1'000U;
  policy_config.min_off_ms = 1'000U;
  output::BinaryActuatorPolicy fan(policy_config);
  output::BinaryActuatorPolicy humidifier(policy_config);
  auto resolver = makeResolver(fan, humidifier);
  auto store = makeStore();

  output::OutputSupervisorCycleInput input{};
  input.monotonic_ms = 1'000U;
  setIntent(input.control.endpoints[0], kFan, 0.20F);
  input.control.metadata.sequence = 11U;

  output::OutputSupervisorResolution resolution{};
  assert(resolver.resolve(input, store, resolution));
  assert(resolution.plan.size == 1U);
  assert(resolution.plan.steps[0].state == output::BinaryOutputState::On);
  assert(resolution.endpoints[0].has_policy_proposal);
  assert(!fan.known());
  assert(fan.commit(resolution.endpoints[0].policy_proposal, true));
  assert(fan.on());

  input.monotonic_ms = 1'500U;
  input.control.endpoints[0].level = 0.0F;
  assert(resolver.resolve(input, store, resolution));
  assert(resolution.plan.size == 0U);
  assert(resolution.endpoints[0].held_by_dwell);
  assert(fan.on());

  input.monotonic_ms = 2'000U;
  assert(resolver.resolve(input, store, resolution));
  assert(resolution.plan.size == 1U);
  assert(resolution.plan.steps[0].state == output::BinaryOutputState::Off);
  assert(fan.on());
}

void testDirectEndpointDedupeUsesSuccessfulCommandTruth() {
  output::BinaryActuatorPolicy fan;
  output::BinaryActuatorPolicy humidifier;
  auto resolver = makeResolver(fan, humidifier);
  auto store = makeStore();

  output::OutputCommand completed{};
  completed.endpoint = kLamp;
  completed.state = output::BinaryOutputState::On;
  assert(store.recordAttempt(completed, 10U,
                             {output::TransportStatus::Completed, output::TransportError::None}));

  output::OutputSupervisorCycleInput input{};
  input.monotonic_ms = 20U;
  setIntent(input.schedule.endpoints[0], kLamp, 1.0F);

  output::OutputSupervisorResolution resolution{};
  assert(resolver.resolve(input, store, resolution));
  assert(resolution.plan.size == 0U);
  assert(resolution.endpoints[1].has_resolved_state);
  assert(resolution.endpoints[1].resolved_state == output::BinaryOutputState::On);
  assert(store.find(kLamp)->physical.state == output::PhysicalOutputState::Unknown);
}

void testNonAutomaticModeSuppressesNormalIntentButNotSafety() {
  output::BinaryActuatorPolicy fan;
  output::BinaryActuatorPolicy humidifier;
  auto resolver = makeResolver(fan, humidifier);
  auto store = makeStore();

  output::OutputSupervisorCycleInput input{};
  input.mode = output::SupervisorMode::Disabled;
  input.monotonic_ms = 500U;
  setIntent(input.manual.endpoints[0], kLamp, 1.0F);

  output::OutputSupervisorResolution resolution{};
  assert(resolver.resolve(input, store, resolution));
  assert(resolution.plan.size == 0U);

  assert(output::setSafetyConstraint(input.safety.endpoints[0], kLamp,
                                     output::SafetyConstraint::ForceOff,
                                     output::OutputReason::ThermalSafety));
  assert(resolver.resolve(input, store, resolution));
  assert(resolution.plan.size == 1U);
  assert(resolution.plan.steps[0].source == output::OutputSource::Safety);
  assert(resolution.plan.steps[0].state == output::BinaryOutputState::Off);
}

} // namespace

int main() {
  testRejectsInvalidConfigurationAndUnconfiguredStore();
  testManualScheduleClimatePrecedence();
  testSafetyOverridesManualAndCanActWithoutLowerIntent();
  testInhibitSuppressesLowerCommand();
  testBinaryPolicyProposalRequiresExternalCommitAndHonorsDwell();
  testDirectEndpointDedupeUsesSuccessfulCommandTruth();
  testNonAutomaticModeSuppressesNormalIntentButNotSafety();
  return 0;
}
