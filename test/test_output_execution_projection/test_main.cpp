#include "climate/output/OutputExecutionProjection.h"

#include <array>
#include <cassert>
#include <cstdint>

using namespace growbox::app::output;

namespace {

constexpr OutputEndpointId kEndpoint = 41U;
constexpr OutputEndpointId kOtherEndpoint = 42U;

OutputStateStore configuredStore() {
  OutputStateStore store{};
  const std::array<OutputEndpointId, kOutputEndpointCapacity> endpoints{kEndpoint, kOtherEndpoint,
                                                                        43U};
  assert(store.configure(endpoints, endpoints.size()));
  return store;
}

OutputSupervisorResolution resolutionFor(BinaryOutputState resolved_state,
                                         bool held_by_dwell = false) {
  OutputSupervisorResolution resolution{};
  resolution.endpoint_count = 1U;
  auto& endpoint = resolution.endpoints[0];
  endpoint.endpoint = kEndpoint;
  endpoint.has_selected_input = true;
  endpoint.requested_level = resolved_state == BinaryOutputState::On ? 1.0F : 0.0F;
  endpoint.source = OutputSource::Climate;
  endpoint.reason = OutputReason::ClimateDecision;
  endpoint.sequence = 7U;
  endpoint.has_resolved_state = true;
  endpoint.resolved_state = resolved_state;
  endpoint.held_by_dwell = held_by_dwell;
  return resolution;
}

OutputCommand command(BinaryOutputState state, std::uint64_t sequence = 7U) {
  OutputCommand output{};
  output.endpoint = kEndpoint;
  output.state = state;
  output.source = OutputSource::Climate;
  output.reason = OutputReason::ClimateDecision;
  output.sequence = sequence;
  return output;
}

void testSuccessfulCommandProjectsCommandTruthNotPhysicalObservation() {
  auto store = configuredStore();
  const auto on = command(BinaryOutputState::On);
  assert(store.recordAttempt(on, 100U, {TransportStatus::Completed, TransportError::None}));
  assert(store.recordPhysicalObservation(kEndpoint, PhysicalOutputState::Off, 101U, 1U));

  const auto resolution = resolutionFor(BinaryOutputState::On);
  ExecutionReport report{};
  assert(appendExecutionResult(
      report, {on, {TransportStatus::Completed, TransportError::None}, PhysicalOutputState::Unknown}));

  ExecutedControlProjection projection{};
  assert(buildExecutedControlProjection(resolution, report, store, projection));
  assert(projection.size == 1U);
  const auto* endpoint = findExecutedEndpointProjection(projection, kEndpoint);
  assert(endpoint != nullptr);
  assert(endpoint->has_executed_state);
  assert(endpoint->executed_state == BinaryOutputState::On);
  assert(endpoint->attempted);
  assert(endpoint->transport.status == TransportStatus::Completed);
  assert(!endpoint->held_by_dwell);
}

void testFailedAttemptKeepsPreviousSuccessfulState() {
  auto store = configuredStore();
  const auto off = command(BinaryOutputState::Off, 1U);
  const auto on = command(BinaryOutputState::On, 2U);
  assert(store.recordAttempt(off, 10U, {TransportStatus::Completed, TransportError::None}));
  assert(store.recordAttempt(on, 20U, {TransportStatus::Failed, TransportError::IoFailure}));
  assert(store.recordPhysicalObservation(kEndpoint, PhysicalOutputState::On, 21U, 2U));

  const auto resolution = resolutionFor(BinaryOutputState::On);
  ExecutionReport report{};
  assert(appendExecutionResult(
      report, {on, {TransportStatus::Failed, TransportError::IoFailure}, PhysicalOutputState::Unknown}));

  ExecutedControlProjection projection{};
  assert(buildExecutedControlProjection(resolution, report, store, projection));
  const auto* endpoint = findExecutedEndpointProjection(projection, kEndpoint);
  assert(endpoint != nullptr);
  assert(endpoint->has_executed_state);
  assert(endpoint->executed_state == BinaryOutputState::Off);
  assert(endpoint->attempted);
  assert(endpoint->transport.status == TransportStatus::Failed);
}

void testDwellHoldProjectsHeldSuccessfulStateWithoutAttempt() {
  auto store = configuredStore();
  const auto on = command(BinaryOutputState::On, 3U);
  assert(store.recordAttempt(on, 30U, {TransportStatus::Completed, TransportError::None}));

  const auto resolution = resolutionFor(BinaryOutputState::On, true);
  ExecutionReport report{};
  ExecutedControlProjection projection{};
  assert(buildExecutedControlProjection(resolution, report, store, projection));
  const auto* endpoint = findExecutedEndpointProjection(projection, kEndpoint);
  assert(endpoint != nullptr);
  assert(endpoint->has_executed_state);
  assert(endpoint->executed_state == BinaryOutputState::On);
  assert(!endpoint->attempted);
  assert(endpoint->transport.status == TransportStatus::NotAttempted);
  assert(endpoint->held_by_dwell);
}

void testUnknownCommandTruthRemainsUnknownInsteadOfFabricatingOff() {
  auto store = configuredStore();
  const auto resolution = resolutionFor(BinaryOutputState::Off);
  ExecutionReport report{};
  ExecutedControlProjection projection{};
  assert(buildExecutedControlProjection(resolution, report, store, projection));
  const auto* endpoint = findExecutedEndpointProjection(projection, kEndpoint);
  assert(endpoint != nullptr);
  assert(!endpoint->has_executed_state);
  assert(!endpoint->attempted);
}

void testMalformedReportEndpointIsRejected() {
  auto store = configuredStore();
  const auto resolution = resolutionFor(BinaryOutputState::On);
  ExecutionReport report{};
  auto wrong = command(BinaryOutputState::On);
  wrong.endpoint = kOtherEndpoint;
  assert(appendExecutionResult(
      report, {wrong, {TransportStatus::Completed, TransportError::None}, PhysicalOutputState::Unknown}));

  ExecutedControlProjection projection{};
  assert(!buildExecutedControlProjection(resolution, report, store, projection));
  assert(projection.size == 0U);
}

} // namespace

int main() {
  testSuccessfulCommandProjectsCommandTruthNotPhysicalObservation();
  testFailedAttemptKeepsPreviousSuccessfulState();
  testDwellHoldProjectsHeldSuccessfulStateWithoutAttempt();
  testUnknownCommandTruthRemainsUnknownInsteadOfFabricatingOff();
  testMalformedReportEndpointIsRejected();
  return 0;
}
