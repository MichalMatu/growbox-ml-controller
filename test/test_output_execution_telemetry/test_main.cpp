#include "climate/output/OutputExecutionTelemetry.h"

#include <array>
#include <cassert>

namespace output = growbox::app::output;

namespace {
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

void testSnapshotKeepsIntentResolutionTransportAndPhysicalTruthSeparate() {
  auto store = makeStore();

  output::OutputCommand fan_attempt{};
  fan_attempt.endpoint = kFan;
  fan_attempt.state = output::BinaryOutputState::On;
  fan_attempt.source = output::OutputSource::Safety;
  fan_attempt.reason = output::OutputReason::ThermalSafety;
  assert(store.recordAttempt(fan_attempt, 500U,
                             {output::TransportStatus::Completed, output::TransportError::None}));
  assert(store.recordPhysicalObservation(kFan, output::PhysicalOutputState::Off, 490U, 7U));

  output::OutputSupervisorCycleInput cycle{};
  cycle.mode = output::SupervisorMode::Automatic;
  cycle.monotonic_ms = 500U;
  assert(output::setEndpointIntent(cycle.control.endpoints[0], kFan, 0.2F));
  assert(output::setEndpointIntent(cycle.schedule.endpoints[0], kLamp, 1.0F));
  assert(output::setEndpointIntent(cycle.manual.endpoints[0], kHumidifier, 1.0F));
  assert(output::setSafetyConstraint(cycle.safety.endpoints[0], kFan,
                                     output::SafetyConstraint::ForceOn,
                                     output::OutputReason::ThermalSafety));

  output::OutputSupervisorResolution resolution{};
  resolution.endpoint_count = 3U;
  resolution.endpoints[0].endpoint = kFan;
  resolution.endpoints[0].has_selected_input = true;
  resolution.endpoints[0].requested_level = 1.0F;
  resolution.endpoints[0].source = output::OutputSource::Safety;
  resolution.endpoints[0].reason = output::OutputReason::ThermalSafety;
  resolution.endpoints[0].has_resolved_state = true;
  resolution.endpoints[0].resolved_state = output::BinaryOutputState::On;
  resolution.endpoints[0].safety_override = true;
  resolution.endpoints[1].endpoint = kLamp;
  resolution.endpoints[1].has_selected_input = true;
  resolution.endpoints[1].requested_level = 1.0F;
  resolution.endpoints[1].source = output::OutputSource::Schedule;
  resolution.endpoints[1].reason = output::OutputReason::ScheduleRequest;
  resolution.endpoints[1].has_resolved_state = true;
  resolution.endpoints[1].resolved_state = output::BinaryOutputState::On;
  resolution.endpoints[2].endpoint = kHumidifier;
  resolution.endpoints[2].has_selected_input = true;
  resolution.endpoints[2].requested_level = 1.0F;
  resolution.endpoints[2].source = output::OutputSource::Manual;
  resolution.endpoints[2].reason = output::OutputReason::ManualRequest;
  resolution.endpoints[2].has_resolved_state = true;
  resolution.endpoints[2].resolved_state = output::BinaryOutputState::On;
  resolution.endpoints[2].held_by_dwell = true;

  output::OutputExecutionTelemetrySnapshot snapshot{};
  assert(output::buildOutputExecutionTelemetry(
      cycle, resolution, store, true, true, output::OutputLifecycleEvent::Recovery, true,
      snapshot));
  assert(snapshot.version == 2U);
  assert(snapshot.mode == output::SupervisorMode::Automatic);
  assert(snapshot.transport_active);
  assert(snapshot.lifecycle_active);
  assert(snapshot.lifecycle_event == output::OutputLifecycleEvent::Recovery);
  assert(snapshot.automation_requested);
  assert(snapshot.endpoint_count == 3U);

  const auto& fan = snapshot.endpoints[0];
  assert(fan.control.active && fan.control.level == 0.2F);
  assert(fan.safety_active);
  assert(fan.safety_constraint == output::SafetyConstraint::ForceOn);
  assert(fan.selected_source == output::OutputSource::Safety);
  assert(fan.resolved && fan.resolved_state == output::BinaryOutputState::On);
  assert(fan.attempt_known && fan.attempted_this_cycle);
  assert(fan.transport_status == output::TransportStatus::Completed);
  assert(fan.last_command_known && fan.last_command_state == output::BinaryOutputState::On);
  assert(fan.physical_state == output::PhysicalOutputState::Off);
  assert(fan.physical_independent);

  const auto& lamp = snapshot.endpoints[1];
  assert(lamp.schedule.active && lamp.schedule.level == 1.0F);
  assert(!lamp.attempt_known);
  assert(!lamp.last_command_known);
  assert(lamp.physical_state == output::PhysicalOutputState::Unknown);
  assert(!lamp.physical_independent);

  const auto& humidifier = snapshot.endpoints[2];
  assert(humidifier.manual.active && humidifier.manual.level == 1.0F);
  assert(humidifier.held_by_dwell);
}

void testFailedHistoricalAttemptIsNotCurrentAndDoesNotInventCommandOrPhysicalTruth() {
  auto store = makeStore();
  output::OutputCommand command{};
  command.endpoint = kLamp;
  command.state = output::BinaryOutputState::Off;
  command.source = output::OutputSource::Lifecycle;
  command.reason = output::OutputReason::LifecyclePolicy;
  assert(store.recordAttempt(command, 100U,
                             {output::TransportStatus::Failed, output::TransportError::IoFailure}));

  output::OutputSupervisorCycleInput cycle{};
  cycle.mode = output::SupervisorMode::FaultLocked;
  cycle.monotonic_ms = 200U;
  output::OutputSupervisorResolution resolution{};
  resolution.endpoint_count = 1U;
  resolution.endpoints[0].endpoint = kLamp;

  output::OutputExecutionTelemetrySnapshot snapshot{};
  assert(output::buildOutputExecutionTelemetry(
      cycle, resolution, store, false, false, output::OutputLifecycleEvent::Fault, false,
      snapshot));
  const auto& lamp = snapshot.endpoints[0];
  assert(lamp.attempt_known);
  assert(!lamp.attempted_this_cycle);
  assert(lamp.transport_status == output::TransportStatus::Failed);
  assert(!lamp.last_command_known);
  assert(lamp.physical_state == output::PhysicalOutputState::Unknown);
  assert(!lamp.physical_independent);
}

} // namespace

int main() {
  testSnapshotKeepsIntentResolutionTransportAndPhysicalTruthSeparate();
  testFailedHistoricalAttemptIsNotCurrentAndDoesNotInventCommandOrPhysicalTruth();
  return 0;
}
