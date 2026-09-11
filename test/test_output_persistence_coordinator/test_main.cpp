#include "climate/output/OutputLifecycleExecutor.h"
#include "climate/output/OutputSupervisorLifecycle.h"
#include "climate/output/persistence/OutputPersistenceCoordinator.h"

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

  output::OutputPersistenceBackendStatus read_status =
      output::OutputPersistenceBackendStatus::NotFound;
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
  assert(coordinator.syncFromStateStore(state, true) ==
         output::OutputPersistenceCoordinatorStatus::Ok);
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
  assert(coordinator.syncFromStateStore(state, true) ==
         output::OutputPersistenceCoordinatorStatus::Ok);
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
  policy.endpoints[0]
      .lifecycle[output::outputLifecycleEventIndex(output::OutputLifecycleEvent::Recovery)]
      .delay_ms = 500U;
  assert(output::validateOutputPolicyConfig(policy) == output::OutputPolicyConfigStatus::Ok);
  assert(coordinator.applyPolicy(policy, state, false) ==
         output::OutputPersistenceCoordinatorStatus::Ok);
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
  assert(coordinator.syncFromStateStore(state, true) ==
         output::OutputPersistenceCoordinatorStatus::Ok);

  auto policy = coordinator.policy();
  auto& restore = policy.endpoints[0].lifecycle[output::outputLifecycleEventIndex(
      output::OutputLifecycleEvent::AutomationOff)];
  restore.action = output::OutputPolicyAction::RestoreLastCommand;
  restore.retransmit = true;
  restore.max_retries = 1U;
  assert(coordinator.applyPolicy(policy, state, true) ==
         output::OutputPersistenceCoordinatorStatus::Ok);

  output::OutputPersistenceStore reboot_store(backend, safePolicy());
  auto reboot_state = configuredStateStore();
  output::OutputPersistenceCoordinator rebooted(reboot_store);
  assert(rebooted.initialize(reboot_state).status ==
         output::OutputPersistenceCoordinatorStatus::Ok);
  assert(runRestoreLifecycle(rebooted.policy(), reboot_state, true));

  output::OutputPersistenceStore second_reboot_store(backend, safePolicy());
  auto second_state = configuredStateStore();
  output::OutputPersistenceCoordinator second_reboot(second_reboot_store);
  assert(second_reboot.initialize(second_state).status ==
         output::OutputPersistenceCoordinatorStatus::Ok);
  auto no_retransmit_policy = second_reboot.policy();
  no_retransmit_policy.endpoints[0]
      .lifecycle[output::outputLifecycleEventIndex(output::OutputLifecycleEvent::AutomationOff)]
      .retransmit = false;
  assert(output::validateOutputPolicyConfig(no_retransmit_policy) ==
         output::OutputPolicyConfigStatus::Ok);
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
