from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement, found {count}")
    p.write_text(text.replace(old, new, 1))


Path("src/climate/output/OutputPersistenceCoordinator.h").write_text(r'''#pragma once

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
''')

Path("src/climate/output/OutputPersistenceCoordinator.cpp").write_text(r'''#include "climate/output/OutputPersistenceCoordinator.h"

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

OutputPersistenceCoordinatorStatus OutputPersistenceCoordinator::saveIfChanged(
    const OutputPersistenceSnapshot& candidate) noexcept {
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

OutputPersistenceCoordinatorStatus OutputPersistenceCoordinator::syncFromStateStore(
    const OutputStateStore& state_store, bool persist_command_truth) noexcept {
  OutputPersistenceSnapshot candidate{};
  if (!buildSnapshot(policy_, state_store, persist_command_truth, candidate)) {
    return state_store.valid() ? OutputPersistenceCoordinatorStatus::InvalidPolicy
                               : OutputPersistenceCoordinatorStatus::InvalidStateStore;
  }
  return saveIfChanged(candidate);
}

OutputPersistenceCoordinatorStatus OutputPersistenceCoordinator::applyPolicy(
    const OutputPolicyConfig& policy, const OutputStateStore& state_store,
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
''')

replace_once(
    "src/climate/output/OutputStateStore.h",
    "  bool recordAttempt(const OutputCommand& command, std::uint64_t attempted_ms,\n                     TxResult result) noexcept;\n  bool recordPhysicalObservation(OutputEndpointId endpoint, PhysicalOutputState state,",
    "  bool recordAttempt(const OutputCommand& command, std::uint64_t attempted_ms,\n                     TxResult result) noexcept;\n  bool restoreLastSuccessfulCommand(OutputEndpointId endpoint, BinaryOutputState state) noexcept;\n  bool recordPhysicalObservation(OutputEndpointId endpoint, PhysicalOutputState state,",
)

replace_once(
    "src/climate/output/OutputStateStore.cpp",
    "  return true;\n}\n\nbool OutputStateStore::recordPhysicalObservation(OutputEndpointId endpoint,",
    "  return true;\n}\n\nbool OutputStateStore::restoreLastSuccessfulCommand(OutputEndpointId endpoint,\n                                                    BinaryOutputState state) noexcept {\n  if (state != BinaryOutputState::Off && state != BinaryOutputState::On) {\n    return false;\n  }\n  OutputStateEntry* entry = findMutable(endpoint);\n  if (entry == nullptr) {\n    return false;\n  }\n\n  OutputCommand restored{};\n  restored.endpoint = endpoint;\n  restored.state = state;\n  entry->last_successful_command = restored;\n  entry->last_successful_ms = 0U;\n  entry->has_successful_command = true;\n  return true;\n}\n\nbool OutputStateStore::recordPhysicalObservation(OutputEndpointId endpoint,",
)

replace_once(
    "src/climate/Stage28dOutputBindings.h",
    "::growbox::app::output::OutputPolicyConfig makeOutputPolicyConfig() noexcept;\nClimateSemanticOutputConfig makeClimateSemanticOutputConfig() noexcept;\nOutputBindingStatus validateOutputBindings(const ClimateSemanticOutputConfig& config) noexcept;\nbool isScheduledLightEndpoint(ClimateEndpointId endpoint) noexcept;",
    "::growbox::app::output::OutputPolicyConfig makeOutputPolicyConfig() noexcept;\nClimateSemanticOutputConfig makeClimateSemanticOutputConfig() noexcept;\nClimateSemanticOutputConfig makeClimateSemanticOutputConfig(\n    const ::growbox::app::output::OutputPolicyConfig& policy) noexcept;\nOutputBindingStatus validateOutputBindings(const ClimateSemanticOutputConfig& config) noexcept;\nOutputBindingStatus validateOutputBindings(\n    const ClimateSemanticOutputConfig& config,\n    const ::growbox::app::output::OutputPolicyConfig& policy) noexcept;\nbool isScheduledLightEndpoint(ClimateEndpointId endpoint) noexcept;\nbool isScheduledLightEndpoint(\n    ClimateEndpointId endpoint, const ::growbox::app::output::OutputPolicyConfig& policy) noexcept;",
)

replace_once(
    "src/climate/Stage28dOutputBindings.cpp",
    "ClimateSemanticOutputConfig makeClimateSemanticOutputConfig() noexcept {\n  const OutputPolicyConfig policy = makeOutputPolicyConfig();\n  if (::growbox::app::output::validateOutputPolicyConfig(policy) != OutputPolicyConfigStatus::Ok) {\n    return {};\n  }\n\n  ClimateSemanticOutputConfig config{};",
    "ClimateSemanticOutputConfig makeClimateSemanticOutputConfig() noexcept {\n  return makeClimateSemanticOutputConfig(makeOutputPolicyConfig());\n}\n\nClimateSemanticOutputConfig makeClimateSemanticOutputConfig(\n    const OutputPolicyConfig& policy) noexcept {\n  if (::growbox::app::output::validateOutputPolicyConfig(policy) != OutputPolicyConfigStatus::Ok) {\n    return {};\n  }\n\n  ClimateSemanticOutputConfig config{};",
)

replace_once(
    "src/climate/Stage28dOutputBindings.cpp",
    "OutputBindingStatus validateOutputBindings(const ClimateSemanticOutputConfig& config) noexcept {\n  const OutputPolicyConfig policy = makeOutputPolicyConfig();\n  if (::growbox::app::output::validateOutputPolicyConfig(policy) != OutputPolicyConfigStatus::Ok) {",
    "OutputBindingStatus validateOutputBindings(const ClimateSemanticOutputConfig& config) noexcept {\n  return validateOutputBindings(config, makeOutputPolicyConfig());\n}\n\nOutputBindingStatus validateOutputBindings(const ClimateSemanticOutputConfig& config,\n                                          const OutputPolicyConfig& policy) noexcept {\n  if (::growbox::app::output::validateOutputPolicyConfig(policy) != OutputPolicyConfigStatus::Ok) {",
)

replace_once(
    "src/climate/Stage28dOutputBindings.cpp",
    "bool isScheduledLightEndpoint(ClimateEndpointId endpoint) noexcept {\n  const OutputPolicyConfig policy = makeOutputPolicyConfig();\n  const auto* lamp = requiredRole(policy, OutputEndpointRole::ScheduledLight);\n  return lamp != nullptr && endpoint == lamp->endpoint;\n}",
    "bool isScheduledLightEndpoint(ClimateEndpointId endpoint) noexcept {\n  return isScheduledLightEndpoint(endpoint, makeOutputPolicyConfig());\n}\n\nbool isScheduledLightEndpoint(ClimateEndpointId endpoint, const OutputPolicyConfig& policy) noexcept {\n  if (::growbox::app::output::validateOutputPolicyConfig(policy) != OutputPolicyConfigStatus::Ok) {\n    return false;\n  }\n  const auto* lamp = requiredRole(policy, OutputEndpointRole::ScheduledLight);\n  return lamp != nullptr && endpoint == lamp->endpoint;\n}",
)

replace_once(
    "src/CMakeLists.txt",
    '    "climate/output/OutputPersistenceSchema.cpp"\n',
    '    "climate/output/OutputPersistenceSchema.cpp"\n    "climate/output/OutputPersistenceCoordinator.cpp"\n',
)

replace_once(
    "src/climate/ClimateV6RealInputRuntime.cpp",
    '#include "climate/output/OutputLifecycleExecutor.h"\n#include "climate/output/OutputSupervisorLifecycle.h"',
    '#include "climate/output/OutputLifecycleExecutor.h"\n#include "climate/output/OutputNvsBackend.h"\n#include "climate/output/OutputPersistenceCoordinator.h"\n#include "climate/output/OutputPersistenceStore.h"\n#include "climate/output/OutputSupervisorLifecycle.h"',
)

replace_once(
    "src/climate/ClimateV6RealInputRuntime.cpp",
    "  const auto semantic_output_config = stage28d::makeClimateSemanticOutputConfig();\n  const bool output_bindings_valid =\n      stage28d::validateOutputBindings(semantic_output_config) == stage28d::OutputBindingStatus::Ok;",
    "  const output::OutputPolicyConfig safe_output_policy = stage28d::makeOutputPolicyConfig();\n  static output::OutputNvsBackend output_nvs_backend;\n  static output::OutputPersistenceStore output_persistence_store(output_nvs_backend,\n                                                                 stage28d::makeOutputPolicyConfig());\n  static output::OutputPersistenceCoordinator output_persistence(output_persistence_store);\n  const auto persistence_init = output_state_store_ready\n                                    ? output_persistence.initialize(output_state_store)\n                                    : output::OutputPersistenceCoordinatorInitResult{};\n  const output::OutputPolicyConfig output_policy =\n      output_persistence.valid() ? output_persistence.policy() : safe_output_policy;\n  if (!output_persistence.valid()) {\n    ESP_LOGW(kTag, \"Output persistence unavailable status=%u store_status=%u; using safe policy\",\n             static_cast<unsigned>(persistence_init.status),\n             static_cast<unsigned>(persistence_init.load.status));\n  }\n\n  const auto semantic_output_config = stage28d::makeClimateSemanticOutputConfig(output_policy);\n  const bool output_bindings_valid =\n      stage28d::validateOutputBindings(semantic_output_config, output_policy) ==\n      stage28d::OutputBindingStatus::Ok;",
)

replace_once(
    "src/climate/ClimateV6RealInputRuntime.cpp",
    "  RuntimeOutputTransport supervisor_transport(rf_output_transport, real_output_ready);\n  const output::OutputPolicyConfig output_policy = stage28d::makeOutputPolicyConfig();\n  output::OutputSupervisorLifecycle output_lifecycle(output_policy);",
    "  RuntimeOutputTransport supervisor_transport(rf_output_transport, real_output_ready);\n  output::OutputSupervisorLifecycle output_lifecycle(output_policy);",
)

replace_once(
    "src/climate/ClimateV6RealInputRuntime.cpp",
    "    const std::uint64_t control_started_us = static_cast<std::uint64_t>(esp_timer_get_time());\n    if (GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED != 0 && real_output_ready &&",
    "    const std::uint64_t control_started_us = static_cast<std::uint64_t>(esp_timer_get_time());\n    const bool real_transport_active_this_cycle = real_output_ready;\n    if (GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED != 0 && real_output_ready &&",
)

replace_once(
    "src/climate/ClimateV6RealInputRuntime.cpp",
    "    runtime_timing.control_cycle.observe(\n        static_cast<std::uint64_t>(esp_timer_get_time()) - control_started_us);",
    "    if (output_persistence.valid()) {\n      const auto persistence_status = output_persistence.syncFromStateStore(\n          output_state_store, real_transport_active_this_cycle);\n      if (persistence_status == output::OutputPersistenceCoordinatorStatus::InvalidPolicy ||\n          persistence_status == output::OutputPersistenceCoordinatorStatus::InvalidStateStore) {\n        ESP_LOGE(kTag, \"Output persistence synchronization invalid status=%u\",\n                 static_cast<unsigned>(persistence_status));\n      }\n    }\n    runtime_timing.control_cycle.observe(\n        static_cast<std::uint64_t>(esp_timer_get_time()) - control_started_us);",
)

Path("test/test_output_persistence_coordinator/test_main.cpp").parent.mkdir(parents=True, exist_ok=True)
Path("test/test_output_persistence_coordinator/test_main.cpp").write_text(r'''#include "climate/output/OutputLifecycleExecutor.h"
#include "climate/output/OutputPersistenceCoordinator.h"
#include "climate/output/OutputSupervisorLifecycle.h"

#include <array>
#include <cassert>
#include <cstddef>

namespace {
namespace output = growbox::app::output;

class FakeBackend final : public output::OutputPersistenceBackend {
public:
  output::OutputPersistenceBackendStatus read(output::OutputPersistenceBlob& output_blob,
                                              std::size_t& output_size) noexcept override {
    ++read_count;
    if (read_status != output::OutputPersistenceBackendStatus::Ok) {
      output_blob = {};
      output_size = 0U;
      return read_status;
    }
    output_blob = blob;
    output_size = stored_size;
    return output::OutputPersistenceBackendStatus::Ok;
  }

  output::OutputPersistenceBackendStatus
  write(const output::OutputPersistenceBlob& input_blob) noexcept override {
    ++write_count;
    if (write_status != output::OutputPersistenceBackendStatus::Ok) {
      return write_status;
    }
    blob = input_blob;
    stored_size = blob.bytes.size();
    read_status = output::OutputPersistenceBackendStatus::Ok;
    return output::OutputPersistenceBackendStatus::Ok;
  }

  output::OutputPersistenceBackendStatus read_status = output::OutputPersistenceBackendStatus::NotFound;
  output::OutputPersistenceBackendStatus write_status = output::OutputPersistenceBackendStatus::Ok;
  output::OutputPersistenceBlob blob{};
  std::size_t stored_size = 0U;
  unsigned read_count = 0U;
  unsigned write_count = 0U;
};

class CapturingTransport final : public output::OutputTransport {
public:
  output::TxResult send(const output::OutputCommand& command) noexcept override {
    if (count < commands.size()) {
      commands[count] = command;
    }
    ++count;
    return {output::TransportStatus::Completed, output::TransportError::None};
  }

  bool saw(output::OutputEndpointId endpoint, output::BinaryOutputState state) const noexcept {
    const std::size_t bounded = count < commands.size() ? count : commands.size();
    for (std::size_t index = 0U; index < bounded; ++index) {
      if (commands[index].endpoint == endpoint && commands[index].state == state) {
        return true;
      }
    }
    return false;
  }

  std::array<output::OutputCommand, 8U> commands{};
  std::size_t count = 0U;
};

output::OutputPolicyConfig safePolicy() {
  return output::makeSafeDefaultOutputPolicyConfig(1U, 2U, 3U);
}

output::OutputStateStore configuredStateStore() {
  output::OutputStateStore state;
  const std::array<output::OutputEndpointId, output::kOutputEndpointCapacity> endpoints{1U, 2U, 3U};
  assert(state.configure(endpoints, endpoints.size()));
  return state;
}

output::OutputCommand command(output::OutputEndpointId endpoint, output::BinaryOutputState state) {
  output::OutputCommand value{};
  value.endpoint = endpoint;
  value.state = state;
  value.source = output::OutputSource::Climate;
  value.reason = output::OutputReason::ClimateDecision;
  value.sequence = 1U;
  return value;
}

output::ScheduleIntent lampOffSchedule() {
  output::ScheduleIntent schedule{};
  schedule.metadata.sequence = 1U;
  schedule.metadata.source = output::OutputSource::Schedule;
  schedule.metadata.reason = output::OutputReason::ScheduleRequest;
  assert(output::setEndpointIntent(schedule.endpoints[0], 2U, 0.0F));
  return schedule;
}

output::OutputSupervisorResolverConfig resolverConfig() {
  output::OutputSupervisorResolverConfig config{};
  config.endpoints[0] = {1U, nullptr};
  config.endpoints[1] = {2U, nullptr};
  config.endpoints[2] = {3U, nullptr};
  config.count = 3U;
  return config;
}

void testSuccessfulCommandWritesOnceAndRestoresWithoutAttempt() {
  FakeBackend backend;
  output::OutputPersistenceStore persistence_store(backend, safePolicy());
  auto state = configuredStateStore();
  output::OutputPersistenceCoordinator coordinator(persistence_store);
  const auto init = coordinator.initialize(state);
  assert(init.status == output::OutputPersistenceCoordinatorStatus::Ok);
  assert(coordinator.valid());
  assert(!init.restored_command_truth);

  assert(state.recordAttempt(command(1U, output::BinaryOutputState::On), 100U,
                             {output::TransportStatus::Completed, output::TransportError::None}));
  assert(coordinator.syncFromStateStore(state, true) == output::OutputPersistenceCoordinatorStatus::Ok);
  assert(backend.write_count == 1U);
  for (unsigned index = 0U; index < 20U; ++index) {
    assert(coordinator.syncFromStateStore(state, true) ==
           output::OutputPersistenceCoordinatorStatus::Unchanged);
  }
  assert(backend.write_count == 1U);

  output::OutputPersistenceStore persistence_store_after_reboot(backend, safePolicy());
  auto reboot_state = configuredStateStore();
  output::OutputPersistenceCoordinator rebooted(persistence_store_after_reboot);
  const auto reboot_init = rebooted.initialize(reboot_state);
  assert(reboot_init.status == output::OutputPersistenceCoordinatorStatus::Ok);
  assert(reboot_init.restored_command_truth);
  const auto* restored = reboot_state.find(1U);
  assert(restored != nullptr);
  assert(restored->has_successful_command);
  assert(restored->last_successful_command.state == output::BinaryOutputState::On);
  assert(restored->last_successful_command.source == output::OutputSource::None);
  assert(restored->last_successful_ms == 0U);
  assert(!restored->has_attempt);
  assert(!restored->physical.has_independent_feedback);
}

void testFailedTransportDoesNotPersistFalseCommand() {
  FakeBackend backend;
  output::OutputPersistenceStore persistence_store(backend, safePolicy());
  auto state = configuredStateStore();
  output::OutputPersistenceCoordinator coordinator(persistence_store);
  assert(coordinator.initialize(state).status == output::OutputPersistenceCoordinatorStatus::Ok);

  assert(state.recordAttempt(command(1U, output::BinaryOutputState::On), 100U,
                             {output::TransportStatus::Failed, output::TransportError::IoFailure}));
  assert(coordinator.syncFromStateStore(state, true) ==
         output::OutputPersistenceCoordinatorStatus::Unchanged);
  assert(backend.write_count == 0U);
}

void testFakeModeCommandTruthIsNotDurable() {
  FakeBackend backend;
  output::OutputPersistenceStore persistence_store(backend, safePolicy());
  auto state = configuredStateStore();
  output::OutputPersistenceCoordinator coordinator(persistence_store);
  assert(coordinator.initialize(state).status == output::OutputPersistenceCoordinatorStatus::Ok);

  assert(state.recordAttempt(command(1U, output::BinaryOutputState::On), 100U,
                             {output::TransportStatus::Completed, output::TransportError::None}));
  assert(coordinator.syncFromStateStore(state, false) ==
         output::OutputPersistenceCoordinatorStatus::Unchanged);
  assert(backend.write_count == 0U);
  assert(coordinator.syncFromStateStore(state, true) == output::OutputPersistenceCoordinatorStatus::Ok);
  assert(backend.write_count == 1U);
}

void testFailedWriteIsSuppressedUntilSnapshotChanges() {
  FakeBackend backend;
  backend.write_status = output::OutputPersistenceBackendStatus::WriteFailed;
  output::OutputPersistenceStore persistence_store(backend, safePolicy());
  auto state = configuredStateStore();
  output::OutputPersistenceCoordinator coordinator(persistence_store);
  assert(coordinator.initialize(state).status == output::OutputPersistenceCoordinatorStatus::Ok);

  assert(state.recordAttempt(command(1U, output::BinaryOutputState::On), 100U,
                             {output::TransportStatus::Completed, output::TransportError::None}));
  assert(coordinator.syncFromStateStore(state, true) ==
         output::OutputPersistenceCoordinatorStatus::StoreError);
  assert(backend.write_count == 1U);
  for (unsigned index = 0U; index < 20U; ++index) {
    assert(coordinator.syncFromStateStore(state, true) ==
           output::OutputPersistenceCoordinatorStatus::SuppressedDuplicate);
  }
  assert(backend.write_count == 1U);

  assert(state.recordAttempt(command(1U, output::BinaryOutputState::Off), 200U,
                             {output::TransportStatus::Completed, output::TransportError::None}));
  assert(coordinator.syncFromStateStore(state, true) ==
         output::OutputPersistenceCoordinatorStatus::StoreError);
  assert(backend.write_count == 2U);
}

void testPolicyChangeWritesOnlyWhenChanged() {
  FakeBackend backend;
  output::OutputPersistenceStore persistence_store(backend, safePolicy());
  auto state = configuredStateStore();
  output::OutputPersistenceCoordinator coordinator(persistence_store);
  assert(coordinator.initialize(state).status == output::OutputPersistenceCoordinatorStatus::Ok);

  auto policy = coordinator.policy();
  policy.endpoints[0].lifecycle[output::outputLifecycleEventIndex(
      output::OutputLifecycleEvent::Recovery)].delay_ms = 500U;
  assert(output::validateOutputPolicyConfig(policy) == output::OutputPolicyConfigStatus::Ok);
  assert(coordinator.applyPolicy(policy, state, false) == output::OutputPersistenceCoordinatorStatus::Ok);
  assert(backend.write_count == 1U);
  assert(coordinator.applyPolicy(policy, state, false) ==
         output::OutputPersistenceCoordinatorStatus::Unchanged);
  assert(backend.write_count == 1U);
}

bool runRestoreLifecycle(const output::OutputPolicyConfig& policy, output::OutputStateStore& state,
                         bool expect_retransmit) {
  output::OutputSupervisorLifecycle lifecycle(policy);
  assert(lifecycle.valid());
  assert(lifecycle.apply(output::OutputLifecycleCommand::BeginArming).status ==
         output::OutputLifecycleTransitionStatus::Applied);
  assert(lifecycle.apply(output::OutputLifecycleCommand::ArmingSucceeded).status ==
         output::OutputLifecycleTransitionStatus::Applied);
  const auto disabled = lifecycle.apply(output::OutputLifecycleCommand::DisableAutomation);
  assert(disabled.status == output::OutputLifecycleTransitionStatus::Applied);

  CapturingTransport transport;
  output::OutputLifecycleExecutor executor(policy, lifecycle, transport, state, resolverConfig());
  assert(executor.valid());
  assert(executor.start(disabled, 100U, lampOffSchedule()));
  for (unsigned tick = 0U; tick < 5U && executor.active(); ++tick) {
    executor.tick(100U);
  }
  assert(!executor.active());
  const bool saw_restore = transport.saw(1U, output::BinaryOutputState::On);
  assert(saw_restore == expect_retransmit);
  return saw_restore;
}

void testRestoreLastCommandHonorsRetransmitPolicyAcrossReboot() {
  FakeBackend backend;
  output::OutputPersistenceStore persistence_store(backend, safePolicy());
  auto state = configuredStateStore();
  output::OutputPersistenceCoordinator coordinator(persistence_store);
  assert(coordinator.initialize(state).status == output::OutputPersistenceCoordinatorStatus::Ok);
  assert(state.recordAttempt(command(1U, output::BinaryOutputState::On), 100U,
                             {output::TransportStatus::Completed, output::TransportError::None}));
  assert(coordinator.syncFromStateStore(state, true) == output::OutputPersistenceCoordinatorStatus::Ok);

  auto policy = coordinator.policy();
  auto& restore = policy.endpoints[0].lifecycle[output::outputLifecycleEventIndex(
      output::OutputLifecycleEvent::AutomationOff)];
  restore.action = output::OutputPolicyAction::RestoreLastCommand;
  restore.retransmit = true;
  restore.max_retries = 1U;
  assert(coordinator.applyPolicy(policy, state, true) == output::OutputPersistenceCoordinatorStatus::Ok);

  output::OutputPersistenceStore reboot_store(backend, safePolicy());
  auto reboot_state = configuredStateStore();
  output::OutputPersistenceCoordinator rebooted(reboot_store);
  assert(rebooted.initialize(reboot_state).status == output::OutputPersistenceCoordinatorStatus::Ok);
  assert(runRestoreLifecycle(rebooted.policy(), reboot_state, true));

  output::OutputPersistenceStore second_reboot_store(backend, safePolicy());
  auto second_state = configuredStateStore();
  output::OutputPersistenceCoordinator second_reboot(second_reboot_store);
  assert(second_reboot.initialize(second_state).status ==
         output::OutputPersistenceCoordinatorStatus::Ok);
  auto no_retransmit_policy = second_reboot.policy();
  no_retransmit_policy.endpoints[0].lifecycle[output::outputLifecycleEventIndex(
      output::OutputLifecycleEvent::AutomationOff)].retransmit = false;
  assert(output::validateOutputPolicyConfig(no_retransmit_policy) == output::OutputPolicyConfigStatus::Ok);
  runRestoreLifecycle(no_retransmit_policy, second_state, false);
}

} // namespace

int main() {
  testSuccessfulCommandWritesOnceAndRestoresWithoutAttempt();
  testFailedTransportDoesNotPersistFalseCommand();
  testFakeModeCommandTruthIsNotDurable();
  testFailedWriteIsSuppressedUntilSnapshotChanges();
  testPolicyChangeWritesOnlyWhenChanged();
  testRestoreLastCommandHonorsRetransmitPolicyAcrossReboot();
  return 0;
}
''')

replace_once(
    "test/host/CMakeLists.txt",
    "target_compile_options(output_persistence_schema_tests PRIVATE -Wall -Wextra -Wpedantic)\n\nadd_executable(\n  output_supervisor_lifecycle_tests",
    "target_compile_options(output_persistence_schema_tests PRIVATE -Wall -Wextra -Wpedantic)\n\nadd_executable(\n  output_persistence_coordinator_tests\n  \"${PROJECT_ROOT}/test/test_output_persistence_coordinator/test_main.cpp\"\n  \"${PROJECT_ROOT}/src/climate/output/OutputPersistenceCoordinator.cpp\"\n  \"${PROJECT_ROOT}/src/climate/output/OutputPersistenceStore.cpp\"\n  \"${PROJECT_ROOT}/src/climate/output/OutputPersistenceSchema.cpp\"\n  \"${PROJECT_ROOT}/src/climate/output/OutputPolicyConfig.cpp\"\n  \"${PROJECT_ROOT}/src/climate/output/OutputStateStore.cpp\"\n  \"${PROJECT_ROOT}/src/climate/output/OutputLifecycleExecutor.cpp\"\n  \"${PROJECT_ROOT}/src/climate/output/OutputSupervisorLifecycle.cpp\"\n  \"${PROJECT_ROOT}/src/climate/output/BinaryActuatorPolicy.cpp\"\n)\ntarget_include_directories(output_persistence_coordinator_tests PRIVATE \"${PROJECT_ROOT}/src\")\ntarget_compile_features(output_persistence_coordinator_tests PRIVATE cxx_std_17)\ntarget_compile_options(output_persistence_coordinator_tests PRIVATE -Wall -Wextra -Wpedantic)\n\nadd_executable(\n  output_supervisor_lifecycle_tests",
)

replace_once(
    "test/host/CMakeLists.txt",
    "add_test(NAME output_persistence_schema_tests COMMAND output_persistence_schema_tests)\nadd_test(NAME output_supervisor_lifecycle_tests COMMAND output_supervisor_lifecycle_tests)",
    "add_test(NAME output_persistence_schema_tests COMMAND output_persistence_schema_tests)\nadd_test(NAME output_persistence_coordinator_tests COMMAND output_persistence_coordinator_tests)\nadd_test(NAME output_supervisor_lifecycle_tests COMMAND output_supervisor_lifecycle_tests)",
)

print("A9_3_EDIT_PASS")
