#include "climate/output/OutputStateStore.h"

#include <array>
#include <cassert>
#include <type_traits>

namespace {

using namespace growbox::app::output;

constexpr std::array<OutputEndpointId, kOutputEndpointCapacity> kEndpoints{1U, 2U, 3U};

OutputCommand command(OutputEndpointId endpoint, BinaryOutputState state, std::uint64_t sequence) {
  OutputCommand value{};
  value.endpoint = endpoint;
  value.state = state;
  value.source = OutputSource::Climate;
  value.reason = OutputReason::ClimateDecision;
  value.sequence = sequence;
  value.due_ms = 123U + sequence;
  return value;
}

void testBootAndDesiredResolvedTruth() {
  OutputStateStore store;
  assert(store.configure(kEndpoints, kEndpoints.size()));
  assert(store.valid());
  assert(store.configuredCount() == 3U);

  const auto* initial = store.find(1U);
  assert(initial != nullptr);
  assert(initial->configured);
  assert(!initial->has_desired);
  assert(!initial->has_resolved);
  assert(!initial->has_attempt);
  assert(!initial->has_successful_command);
  assert(initial->physical.state == PhysicalOutputState::Unknown);
  assert(!initial->physical.has_independent_feedback);

  const auto desired = command(1U, BinaryOutputState::On, 7U);
  assert(store.recordDesired(desired));
  const auto* after_desired = store.find(1U);
  assert(after_desired != nullptr && after_desired->has_desired);
  assert(after_desired->desired.sequence == 7U);
  assert(!after_desired->has_resolved);
  assert(!after_desired->has_attempt);
  assert(after_desired->physical.state == PhysicalOutputState::Unknown);

  const auto resolved = command(1U, BinaryOutputState::Off, 8U);
  assert(store.recordResolved(resolved));
  const auto* after_resolved = store.find(1U);
  assert(after_resolved != nullptr && after_resolved->has_resolved);
  assert(after_resolved->resolved.state == BinaryOutputState::Off);
  assert(!after_resolved->has_attempt);
}

void testFailedAndSuccessfulTransportRemainPhysicalUnknown() {
  OutputStateStore store;
  assert(store.configure(kEndpoints, kEndpoints.size()));

  const auto first = command(2U, BinaryOutputState::On, 11U);
  assert(store.recordAttempt(first, 500U, {TransportStatus::Failed, TransportError::IoFailure}));
  const auto* failed = store.find(2U);
  assert(failed != nullptr && failed->has_attempt);
  assert(failed->last_attempt.sequence == 11U);
  assert(failed->last_attempt_ms == 500U);
  assert(failed->last_transport.status == TransportStatus::Failed);
  assert(failed->last_transport.error == TransportError::IoFailure);
  assert(!failed->has_successful_command);
  assert(failed->physical.state == PhysicalOutputState::Unknown);

  const auto second = command(2U, BinaryOutputState::Off, 12U);
  assert(store.recordAttempt(second, 700U, {TransportStatus::Completed, TransportError::None}));
  const auto* completed = store.find(2U);
  assert(completed != nullptr && completed->has_successful_command);
  assert(completed->last_successful_command.sequence == 12U);
  assert(completed->last_successful_command.state == BinaryOutputState::Off);
  assert(completed->last_successful_ms == 700U);
  assert(completed->physical.state == PhysicalOutputState::Unknown);
  assert(!completed->physical.has_independent_feedback);
}

void testIndependentFeedbackIsSeparateFromTransport() {
  OutputStateStore store;
  assert(store.configure(kEndpoints, kEndpoints.size()));
  assert(store.recordPhysicalObservation(3U, PhysicalOutputState::Off, 1'000U, 21U));

  const auto* observed = store.find(3U);
  assert(observed != nullptr);
  assert(observed->physical.state == PhysicalOutputState::Off);
  assert(observed->physical.has_independent_feedback);
  assert(observed->physical.observed_ms == 1'000U);
  assert(observed->physical.sequence == 21U);

  const auto tx = command(3U, BinaryOutputState::On, 22U);
  assert(store.recordAttempt(tx, 1'100U, {TransportStatus::Completed, TransportError::None}));
  const auto* after_tx = store.find(3U);
  assert(after_tx != nullptr && after_tx->has_successful_command);
  assert(after_tx->last_successful_command.state == BinaryOutputState::On);
  assert(after_tx->physical.state == PhysicalOutputState::Off);
  assert(after_tx->physical.has_independent_feedback);
  assert(after_tx->physical.observed_ms == 1'000U);
}

void testResetPreservesConfigurationButClearsRuntimeTruth() {
  OutputStateStore store;
  assert(store.configure(kEndpoints, kEndpoints.size()));
  assert(store.recordDesired(command(1U, BinaryOutputState::On, 1U)));
  assert(store.recordResolved(command(1U, BinaryOutputState::On, 2U)));
  assert(store.recordAttempt(command(1U, BinaryOutputState::On, 3U), 9U,
                             {TransportStatus::Completed, TransportError::None}));
  assert(store.recordPhysicalObservation(1U, PhysicalOutputState::On, 10U, 4U));

  store.resetRuntimeTruth();
  assert(store.valid());
  assert(store.configuredCount() == 3U);
  const auto* entry = store.find(1U);
  assert(entry != nullptr && entry->configured && entry->endpoint == 1U);
  assert(!entry->has_desired);
  assert(!entry->has_resolved);
  assert(!entry->has_attempt);
  assert(!entry->has_successful_command);
  assert(entry->physical.state == PhysicalOutputState::Unknown);
  assert(!entry->physical.has_independent_feedback);
}

void testInvalidConfigurationAndCommandsFailClosed() {
  OutputStateStore store;
  const std::array<OutputEndpointId, kOutputEndpointCapacity> duplicates{1U, 1U, 3U};
  assert(!store.configure(duplicates, duplicates.size()));
  assert(!store.valid());
  assert(store.find(1U) == nullptr);

  assert(store.configure(kEndpoints, kEndpoints.size()));
  assert(!store.recordDesired(command(99U, BinaryOutputState::On, 1U)));

  auto invalid_state = command(1U, BinaryOutputState::On, 1U);
  invalid_state.state = static_cast<BinaryOutputState>(0x7fU);
  assert(!store.recordResolved(invalid_state));
  assert(
      !store.recordAttempt(invalid_state, 1U, {TransportStatus::Completed, TransportError::None}));
  assert(!store.recordPhysicalObservation(99U, PhysicalOutputState::On, 1U));
}

} // namespace

int main() {
  static_assert(std::is_trivially_copyable_v<OutputStateEntry>);
  testBootAndDesiredResolvedTruth();
  testFailedAndSuccessfulTransportRemainPhysicalUnknown();
  testIndependentFeedbackIsSeparateFromTransport();
  testResetPreservesConfigurationButClearsRuntimeTruth();
  testInvalidConfigurationAndCommandsFailClosed();
  return 0;
}
