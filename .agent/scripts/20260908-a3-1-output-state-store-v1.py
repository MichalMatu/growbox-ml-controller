from pathlib import Path

HEADER = r'''#pragma once

#include "climate/output/OutputExecution.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace growbox::app::output {

struct PhysicalObservation {
  PhysicalOutputState state = PhysicalOutputState::Unknown;
  bool has_independent_feedback = false;
  std::uint64_t observed_ms = 0U;
  std::uint64_t sequence = 0U;
};

struct OutputStateEntry {
  OutputEndpointId endpoint = kInvalidOutputEndpoint;
  bool configured = false;

  bool has_desired = false;
  OutputCommand desired{};

  bool has_resolved = false;
  OutputCommand resolved{};

  bool has_attempt = false;
  OutputCommand last_attempt{};
  std::uint64_t last_attempt_ms = 0U;
  TxResult last_transport{};

  bool has_successful_command = false;
  OutputCommand last_successful_command{};
  std::uint64_t last_successful_ms = 0U;

  PhysicalObservation physical{};
};

class OutputStateStore final {
public:
  bool configure(const std::array<OutputEndpointId, kOutputEndpointCapacity>& endpoints,
                 std::size_t count) noexcept;
  void resetRuntimeTruth() noexcept;

  bool valid() const noexcept { return valid_; }
  std::size_t configuredCount() const noexcept { return configured_count_; }

  const OutputStateEntry* find(OutputEndpointId endpoint) const noexcept;

  bool recordDesired(const OutputCommand& command) noexcept;
  bool recordResolved(const OutputCommand& command) noexcept;
  bool recordAttempt(const OutputCommand& command, std::uint64_t attempted_ms,
                     TxResult result) noexcept;
  bool recordPhysicalObservation(OutputEndpointId endpoint, PhysicalOutputState state,
                                 std::uint64_t observed_ms,
                                 std::uint64_t sequence = 0U) noexcept;

private:
  static bool commandStateValid(const OutputCommand& command) noexcept;
  OutputStateEntry* findMutable(OutputEndpointId endpoint) noexcept;
  void clearAll() noexcept;

  std::array<OutputStateEntry, kOutputEndpointCapacity> entries_{};
  std::size_t configured_count_{0U};
  bool valid_{false};
};

} // namespace growbox::app::output
'''

SOURCE = r'''#include "climate/output/OutputStateStore.h"

namespace growbox::app::output {
namespace {

OutputStateEntry resetEntry(OutputEndpointId endpoint, bool configured) noexcept {
  OutputStateEntry entry{};
  entry.endpoint = endpoint;
  entry.configured = configured;
  return entry;
}

} // namespace

void OutputStateStore::clearAll() noexcept {
  for (auto& entry : entries_) {
    entry = OutputStateEntry{};
  }
  configured_count_ = 0U;
  valid_ = false;
}

bool OutputStateStore::configure(
    const std::array<OutputEndpointId, kOutputEndpointCapacity>& endpoints,
    std::size_t count) noexcept {
  clearAll();
  if (count == 0U || count > kOutputEndpointCapacity) {
    return false;
  }

  for (std::size_t i = 0U; i < count; ++i) {
    if (!isValidOutputEndpoint(endpoints[i])) {
      clearAll();
      return false;
    }
    for (std::size_t prior = 0U; prior < i; ++prior) {
      if (endpoints[prior] == endpoints[i]) {
        clearAll();
        return false;
      }
    }
    entries_[i] = resetEntry(endpoints[i], true);
  }

  configured_count_ = count;
  valid_ = true;
  return true;
}

void OutputStateStore::resetRuntimeTruth() noexcept {
  if (!valid_) {
    clearAll();
    return;
  }
  for (std::size_t i = 0U; i < configured_count_; ++i) {
    entries_[i] = resetEntry(entries_[i].endpoint, true);
  }
  for (std::size_t i = configured_count_; i < entries_.size(); ++i) {
    entries_[i] = OutputStateEntry{};
  }
}

const OutputStateEntry* OutputStateStore::find(OutputEndpointId endpoint) const noexcept {
  if (!valid_) {
    return nullptr;
  }
  for (std::size_t i = 0U; i < configured_count_; ++i) {
    if (entries_[i].endpoint == endpoint) {
      return &entries_[i];
    }
  }
  return nullptr;
}

OutputStateEntry* OutputStateStore::findMutable(OutputEndpointId endpoint) noexcept {
  if (!valid_) {
    return nullptr;
  }
  for (std::size_t i = 0U; i < configured_count_; ++i) {
    if (entries_[i].endpoint == endpoint) {
      return &entries_[i];
    }
  }
  return nullptr;
}

bool OutputStateStore::commandStateValid(const OutputCommand& command) noexcept {
  if (!outputCommandValid(command)) {
    return false;
  }
  switch (command.state) {
  case BinaryOutputState::Off:
  case BinaryOutputState::On:
    return true;
  }
  return false;
}

bool OutputStateStore::recordDesired(const OutputCommand& command) noexcept {
  if (!commandStateValid(command)) {
    return false;
  }
  OutputStateEntry* entry = findMutable(command.endpoint);
  if (entry == nullptr) {
    return false;
  }
  entry->desired = command;
  entry->has_desired = true;
  return true;
}

bool OutputStateStore::recordResolved(const OutputCommand& command) noexcept {
  if (!commandStateValid(command)) {
    return false;
  }
  OutputStateEntry* entry = findMutable(command.endpoint);
  if (entry == nullptr) {
    return false;
  }
  entry->resolved = command;
  entry->has_resolved = true;
  return true;
}

bool OutputStateStore::recordAttempt(const OutputCommand& command, std::uint64_t attempted_ms,
                                     TxResult result) noexcept {
  if (!commandStateValid(command)) {
    return false;
  }
  OutputStateEntry* entry = findMutable(command.endpoint);
  if (entry == nullptr) {
    return false;
  }

  entry->last_attempt = command;
  entry->last_attempt_ms = attempted_ms;
  entry->last_transport = result;
  entry->has_attempt = true;

  if (result.status == TransportStatus::Completed) {
    entry->last_successful_command = command;
    entry->last_successful_ms = attempted_ms;
    entry->has_successful_command = true;
  }
  return true;
}

bool OutputStateStore::recordPhysicalObservation(OutputEndpointId endpoint,
                                                 PhysicalOutputState state,
                                                 std::uint64_t observed_ms,
                                                 std::uint64_t sequence) noexcept {
  OutputStateEntry* entry = findMutable(endpoint);
  if (entry == nullptr) {
    return false;
  }
  entry->physical.state = state;
  entry->physical.has_independent_feedback = true;
  entry->physical.observed_ms = observed_ms;
  entry->physical.sequence = sequence;
  return true;
}

} // namespace growbox::app::output
'''

TEST = r'''#include "climate/output/OutputStateStore.h"

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
  assert(store.recordAttempt(first, 500U,
                             {TransportStatus::Failed, TransportError::IoFailure}));
  const auto* failed = store.find(2U);
  assert(failed != nullptr && failed->has_attempt);
  assert(failed->last_attempt.sequence == 11U);
  assert(failed->last_attempt_ms == 500U);
  assert(failed->last_transport.status == TransportStatus::Failed);
  assert(failed->last_transport.error == TransportError::IoFailure);
  assert(!failed->has_successful_command);
  assert(failed->physical.state == PhysicalOutputState::Unknown);

  const auto second = command(2U, BinaryOutputState::Off, 12U);
  assert(store.recordAttempt(second, 700U,
                             {TransportStatus::Completed, TransportError::None}));
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
  assert(store.recordAttempt(tx, 1'100U,
                             {TransportStatus::Completed, TransportError::None}));
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
  assert(!store.recordAttempt(invalid_state, 1U,
                              {TransportStatus::Completed, TransportError::None}));
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
'''

Path("src/climate/output/OutputStateStore.h").write_text(HEADER)
Path("src/climate/output/OutputStateStore.cpp").write_text(SOURCE)
Path("test/test_output_state_store").mkdir(parents=True, exist_ok=True)
Path("test/test_output_state_store/test_main.cpp").write_text(TEST)

src_cmake = Path("src/CMakeLists.txt")
s = src_cmake.read_text()
anchor = '    "climate/rf433/Rf433OutputTransport.cpp"\n'
assert s.count(anchor) == 1
s = s.replace(anchor, anchor + '    "climate/output/OutputStateStore.cpp"\n', 1)
src_cmake.write_text(s)

host_cmake = Path("test/host/CMakeLists.txt")
s = host_cmake.read_text()
block = r'''

add_executable(
  output_state_store_tests
  "${PROJECT_ROOT}/test/test_output_state_store/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/output/OutputStateStore.cpp"
)
target_include_directories(output_state_store_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(output_state_store_tests PRIVATE cxx_std_17)
target_compile_options(output_state_store_tests PRIVATE -Wall -Wextra -Wpedantic)
add_test(NAME output_state_store_tests COMMAND output_state_store_tests)
'''
assert "output_state_store_tests" not in s
s = s.rstrip() + block + "\n"
host_cmake.write_text(s)
