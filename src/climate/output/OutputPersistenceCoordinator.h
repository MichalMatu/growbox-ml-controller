#pragma once

#include "climate/output/OutputPersistenceStore.h"
#include "climate/output/OutputStateStore.h"

#include <cstdint>

namespace growbox::app::output {

enum class OutputPersistenceCoordinatorStatus : std::uint8_t {
  Ok = 0U,
  Unchanged,
  SuppressedDuplicate,
  InvalidStateStore,
  InvalidPolicy,
  StoreError,
};

struct OutputPersistenceCoordinatorInitResult {
  OutputPersistenceCoordinatorStatus status = OutputPersistenceCoordinatorStatus::StoreError;
  OutputPersistenceLoadResult load{};
  bool restored_command_truth = false;
};

class OutputPersistenceCoordinator final {
public:
  explicit OutputPersistenceCoordinator(OutputPersistenceStore& store) noexcept : store_(store) {}

  OutputPersistenceCoordinatorInitResult initialize(OutputStateStore& state_store) noexcept;

  bool valid() const noexcept { return valid_; }
  const OutputPolicyConfig& policy() const noexcept { return policy_; }
  const OutputPersistenceSnapshot& snapshot() const noexcept { return snapshot_; }
  std::uint32_t writeAttemptCount() const noexcept { return write_attempt_count_; }
  std::uint32_t writeSuccessCount() const noexcept { return write_success_count_; }

  OutputPersistenceCoordinatorStatus syncFromStateStore(
      const OutputStateStore& state_store, bool persist_command_truth) noexcept;
  OutputPersistenceCoordinatorStatus applyPolicy(
      const OutputPolicyConfig& policy, const OutputStateStore& state_store,
      bool persist_command_truth) noexcept;

private:
  bool buildSnapshot(const OutputPolicyConfig& policy, const OutputStateStore& state_store,
                     bool persist_command_truth,
                     OutputPersistenceSnapshot& candidate) const noexcept;
  OutputPersistenceCoordinatorStatus saveIfChanged(
      const OutputPersistenceSnapshot& candidate) noexcept;
  static bool encodeSnapshot(const OutputPersistenceSnapshot& snapshot,
                             OutputPersistenceBlob& blob) noexcept;
  static bool sameBlob(const OutputPersistenceBlob& lhs,
                       const OutputPersistenceBlob& rhs) noexcept;

  OutputPersistenceStore& store_;
  OutputPolicyConfig policy_{};
  OutputPersistenceSnapshot snapshot_{};
  OutputPersistenceBlob persisted_blob_{};
  OutputPersistenceBlob last_attempted_blob_{};
  bool has_persisted_blob_{false};
  bool has_last_attempted_blob_{false};
  bool valid_{false};
  std::uint32_t write_attempt_count_{0U};
  std::uint32_t write_success_count_{0U};
};

} // namespace growbox::app::output
