#include "climate/output/OutputStateStore.h"

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

bool OutputStateStore::restoreLastSuccessfulCommand(OutputEndpointId endpoint,
                                                    BinaryOutputState state) noexcept {
  if (state != BinaryOutputState::Off && state != BinaryOutputState::On) {
    return false;
  }
  OutputStateEntry* entry = findMutable(endpoint);
  if (entry == nullptr) {
    return false;
  }

  OutputCommand restored{};
  restored.endpoint = endpoint;
  restored.state = state;
  entry->last_successful_command = restored;
  entry->last_successful_ms = 0U;
  entry->has_successful_command = true;
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

bool OutputStateStore::clearPhysicalObservation(OutputEndpointId endpoint) noexcept {
  OutputStateEntry* entry = findMutable(endpoint);
  if (entry == nullptr) {
    return false;
  }
  entry->physical = {};
  return true;
}

} // namespace growbox::app::output
