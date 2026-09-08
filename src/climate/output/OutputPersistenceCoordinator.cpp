#include "climate/output/OutputPersistenceCoordinator.h"

#include <cstddef>

namespace growbox::app::output {
namespace {

const DurableOutputCommandState* findDurableCommand(const OutputPersistenceSnapshot& snapshot,
                                                    OutputEndpointId endpoint) noexcept {
  for (std::size_t index = 0U; index < snapshot.command_count; ++index) {
    if (snapshot.commands[index].endpoint == endpoint) {
      return &snapshot.commands[index];
    }
  }
  return nullptr;
}

} // namespace

bool OutputPersistenceCoordinator::encodeSnapshot(const OutputPersistenceSnapshot& snapshot,
                                                  OutputPersistenceBlob& blob) noexcept {
  return encodeOutputPersistence(snapshot, blob) == OutputPersistenceStatus::Ok;
}

bool OutputPersistenceCoordinator::sameBlob(const OutputPersistenceBlob& lhs,
                                            const OutputPersistenceBlob& rhs) noexcept {
  return lhs.bytes == rhs.bytes;
}

OutputPersistenceCoordinatorInitResult
OutputPersistenceCoordinator::initialize(OutputStateStore& state_store) noexcept {
  valid_ = false;
  policy_ = {};
  snapshot_ = {};
  has_persisted_blob_ = false;
  has_last_attempted_blob_ = false;
  write_attempt_count_ = 0U;
  write_success_count_ = 0U;

  OutputPersistenceCoordinatorInitResult result{};
  result.load = store_.load();
  if (!state_store.valid() ||
      validateOutputPersistenceSnapshot(result.load.snapshot) != OutputPersistenceStatus::Ok) {
    result.status = OutputPersistenceCoordinatorStatus::InvalidStateStore;
    return result;
  }

  for (std::size_t index = 0U; index < result.load.snapshot.command_count; ++index) {
    const auto& durable = result.load.snapshot.commands[index];
    if (state_store.find(durable.endpoint) == nullptr) {
      result.status = OutputPersistenceCoordinatorStatus::InvalidStateStore;
      return result;
    }
    if (durable.has_last_successful_command) {
      if (!state_store.restoreLastSuccessfulCommand(durable.endpoint, durable.state)) {
        result.status = OutputPersistenceCoordinatorStatus::InvalidStateStore;
        return result;
      }
      result.restored_command_truth = true;
    }
  }

  OutputPersistenceBlob encoded{};
  if (!encodeSnapshot(result.load.snapshot, encoded)) {
    result.status = OutputPersistenceCoordinatorStatus::InvalidPolicy;
    return result;
  }

  snapshot_ = result.load.snapshot;
  policy_ = snapshot_.policy;
  persisted_blob_ = encoded;
  has_persisted_blob_ = true;
  valid_ = true;
  result.status = OutputPersistenceCoordinatorStatus::Ok;
  return result;
}

bool OutputPersistenceCoordinator::buildSnapshot(
    const OutputPolicyConfig& policy, const OutputStateStore& state_store,
    bool persist_command_truth, OutputPersistenceSnapshot& candidate) const noexcept {
  candidate = {};
  if (!valid_ || !state_store.valid() ||
      validateOutputPolicyConfig(policy) != OutputPolicyConfigStatus::Ok) {
    return false;
  }

  candidate.policy = policy;
  candidate.command_count = policy.count;
  for (std::size_t index = 0U; index < policy.count; ++index) {
    const OutputEndpointId endpoint = policy.endpoints[index].endpoint;
    const OutputStateEntry* state = state_store.find(endpoint);
    if (state == nullptr) {
      return false;
    }

    auto& durable = candidate.commands[index];
    durable.endpoint = endpoint;
    durable.has_last_successful_command = false;
    durable.state = BinaryOutputState::Off;

    if (persist_command_truth) {
      if (state->has_successful_command) {
        durable.has_last_successful_command = true;
        durable.state = state->last_successful_command.state;
      }
      continue;
    }

    const DurableOutputCommandState* existing = findDurableCommand(snapshot_, endpoint);
    if (existing != nullptr) {
      durable.has_last_successful_command = existing->has_last_successful_command;
      durable.state = existing->state;
    }
  }

  return validateOutputPersistenceSnapshot(candidate) == OutputPersistenceStatus::Ok;
}

OutputPersistenceCoordinatorStatus
OutputPersistenceCoordinator::saveIfChanged(const OutputPersistenceSnapshot& candidate) noexcept {
  OutputPersistenceBlob candidate_blob{};
  if (!valid_ || !encodeSnapshot(candidate, candidate_blob)) {
    return OutputPersistenceCoordinatorStatus::InvalidPolicy;
  }
  if (has_persisted_blob_ && sameBlob(candidate_blob, persisted_blob_)) {
    return OutputPersistenceCoordinatorStatus::Unchanged;
  }
  if (has_last_attempted_blob_ && sameBlob(candidate_blob, last_attempted_blob_)) {
    return OutputPersistenceCoordinatorStatus::SuppressedDuplicate;
  }

  last_attempted_blob_ = candidate_blob;
  has_last_attempted_blob_ = true;
  ++write_attempt_count_;
  if (store_.save(candidate) != OutputPersistenceStoreStatus::Ok) {
    return OutputPersistenceCoordinatorStatus::StoreError;
  }

  snapshot_ = candidate;
  policy_ = candidate.policy;
  persisted_blob_ = candidate_blob;
  has_persisted_blob_ = true;
  ++write_success_count_;
  return OutputPersistenceCoordinatorStatus::Ok;
}

OutputPersistenceCoordinatorStatus
OutputPersistenceCoordinator::syncFromStateStore(const OutputStateStore& state_store,
                                                 bool persist_command_truth) noexcept {
  OutputPersistenceSnapshot candidate{};
  if (!buildSnapshot(policy_, state_store, persist_command_truth, candidate)) {
    return state_store.valid() ? OutputPersistenceCoordinatorStatus::InvalidPolicy
                               : OutputPersistenceCoordinatorStatus::InvalidStateStore;
  }
  return saveIfChanged(candidate);
}

OutputPersistenceCoordinatorStatus
OutputPersistenceCoordinator::applyPolicy(const OutputPolicyConfig& policy,
                                          const OutputStateStore& state_store,
                                          bool persist_command_truth) noexcept {
  if (validateOutputPolicyConfig(policy) != OutputPolicyConfigStatus::Ok) {
    return OutputPersistenceCoordinatorStatus::InvalidPolicy;
  }
  OutputPersistenceSnapshot candidate{};
  if (!buildSnapshot(policy, state_store, persist_command_truth, candidate)) {
    return OutputPersistenceCoordinatorStatus::InvalidStateStore;
  }
  return saveIfChanged(candidate);
}

} // namespace growbox::app::output
