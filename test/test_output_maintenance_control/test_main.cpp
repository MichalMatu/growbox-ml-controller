#include "climate/output/control/OutputMaintenanceControl.h"

#include <array>
#include <cassert>
#include <cstdint>

namespace {
namespace output = growbox::app::output;

class FakeTransport final : public output::OutputTransport {
public:
  output::TxResult send(const output::OutputCommand& command) noexcept override {
    ++count;
    last = command;
    return result;
  }
  output::TxResult result{output::TransportStatus::Completed, output::TransportError::None};
  output::OutputCommand last{};
  unsigned count{0U};
};

struct Fixture {
  output::OutputPolicyConfig policy{output::makeSafeDefaultOutputPolicyConfig(1U, 2U, 3U)};
  output::OutputStateStore state{};
  output::BinaryActuatorPolicy fan{};
  output::BinaryActuatorPolicy humidifier{};
  output::OutputSupervisorResolverConfig resolver{};
  output::OutputSupervisorLifecycle lifecycle{policy};
  FakeTransport lifecycle_transport{};
  output::OutputLifecycleExecutor executor;
  output::OutputAutomationControl automation;
  FakeTransport raw_transport{};
  output::OutputMaintenanceControl maintenance;

  Fixture()
      : executor(policy, lifecycle, lifecycle_transport, state, configureResolver()),
        automation(lifecycle, executor),
        maintenance(policy, lifecycle, automation, executor, state, resolver, raw_transport) {
    assert(output::validateOutputPolicyConfig(policy) == output::OutputPolicyConfigStatus::Ok);
    assert(state.valid());
    assert(executor.valid());
    assert(automation.valid());
    assert(maintenance.valid());
  }

  output::OutputSupervisorResolverConfig configureResolver() {
    const std::array<output::OutputEndpointId, output::kOutputEndpointCapacity> endpoints{1U, 2U,
                                                                                          3U};
    assert(state.configure(endpoints, endpoints.size()));
    resolver.endpoints[0] = {1U, &fan};
    resolver.endpoints[1] = {2U, nullptr};
    resolver.endpoints[2] = {3U, &humidifier};
    resolver.count = 3U;
    return resolver;
  }

  output::ScheduleIntent scheduleOff() const {
    output::ScheduleIntent schedule{};
    schedule.metadata.source = output::OutputSource::Schedule;
    schedule.metadata.reason = output::OutputReason::ScheduleRequest;
    assert(output::setEndpointIntent(schedule.endpoints[0], 2U, 0.0F));
    return schedule;
  }

  void bootstrapAutomatic() {
    const auto begin = lifecycle.apply(output::OutputLifecycleCommand::BeginArming);
    assert(begin.status == output::OutputLifecycleTransitionStatus::Applied);
    assert(executor.start(begin, 0U, scheduleOff()));
    for (std::uint64_t now = 0U; executor.active() && now < 10U; ++now) {
      executor.tick(now);
    }
    assert(!executor.active());
    const auto armed = lifecycle.apply(output::OutputLifecycleCommand::ArmingSucceeded);
    assert(armed.status == output::OutputLifecycleTransitionStatus::Applied);
    assert(lifecycle.mode() == output::SupervisorMode::Automatic);
  }

  void enterMaintenance(output::SafetyEnvelope safety = {}) {
    assert(maintenance.requestEnter());
    for (std::uint64_t now = 100U;
         now < 120U && lifecycle.mode() != output::SupervisorMode::MaintenanceLocked; ++now) {
      automation.tick(now, scheduleOff(), safety);
      maintenance.tick(now, safety);
    }
    assert(lifecycle.mode() == output::SupervisorMode::MaintenanceLocked);
    assert(!maintenance.transitionActive());
  }
};

void testRawDeniedOutsideMaintenance() {
  Fixture f;
  f.bootstrapAutomatic();
  assert(!f.maintenance.requestRaw(output::OutputEndpointRole::ScheduledLight,
                                   output::BinaryOutputState::On, 10U));
  assert(f.raw_transport.count == 0U);
}

void testSafeEntryCompletesBeforeMaintenanceAndClearsPhysicalTruth() {
  Fixture f;
  f.bootstrapAutomatic();
  assert(f.state.recordPhysicalObservation(2U, output::PhysicalOutputState::On, 50U, 1U));
  const unsigned before = f.lifecycle_transport.count;
  assert(f.maintenance.requestEnter());
  f.automation.tick(100U, f.scheduleOff(), {});
  auto report = f.maintenance.tick(100U, {});
  assert(report.mode == output::SupervisorMode::Disabled);
  assert(report.enter_pending);
  assert(f.lifecycle.mode() != output::SupervisorMode::MaintenanceLocked);
  for (std::uint64_t now = 101U;
       now < 120U && f.lifecycle.mode() != output::SupervisorMode::MaintenanceLocked; ++now) {
    f.automation.tick(now, f.scheduleOff(), {});
    report = f.maintenance.tick(now, {});
  }
  assert(f.lifecycle.mode() == output::SupervisorMode::MaintenanceLocked);
  assert(f.lifecycle_transport.count >= before + 3U);
  const auto* lamp = f.state.find(2U);
  assert(lamp != nullptr);
  assert(!lamp->physical.has_independent_feedback);
  assert(lamp->physical.state == output::PhysicalOutputState::Unknown);
}

void testHardSafetyVetoAndAlignedRawCommand() {
  Fixture f;
  f.bootstrapAutomatic();
  f.enterMaintenance();

  output::SafetyEnvelope safety{};
  assert(output::setSafetyConstraint(safety.endpoints[0], 1U, output::SafetyConstraint::ForceOn,
                                     output::OutputReason::ThermalSafety));
  assert(f.maintenance.requestRaw(output::OutputEndpointRole::ExhaustFan,
                                  output::BinaryOutputState::Off, 200U));
  auto report = f.maintenance.tick(200U, safety);
  assert(report.status == output::OutputMaintenanceStatus::SafetyVeto);
  assert(f.raw_transport.count == 0U);

  assert(f.maintenance.requestRaw(output::OutputEndpointRole::ExhaustFan,
                                  output::BinaryOutputState::On, 201U));
  report = f.maintenance.tick(201U, safety);
  assert(report.status == output::OutputMaintenanceStatus::Ready);
  assert(report.has_raw_result);
  assert(f.raw_transport.count == 1U);
  assert(f.raw_transport.last.source == output::OutputSource::Maintenance);
  assert(f.raw_transport.last.reason == output::OutputReason::MaintenanceRequest);
  assert(f.fan.known() && f.fan.on());
  const auto* fan = f.state.find(1U);
  assert(fan != nullptr && fan->has_successful_command);
  assert(fan->last_successful_command.source == output::OutputSource::Maintenance);
  assert(fan->physical.state == output::PhysicalOutputState::Unknown);
}

void testFailedRawDoesNotAdvanceBinaryPolicy() {
  Fixture f;
  f.bootstrapAutomatic();
  f.enterMaintenance();
  assert(!f.humidifier.known() || !f.humidifier.on());
  f.raw_transport.result = {output::TransportStatus::Failed, output::TransportError::IoFailure};
  assert(f.maintenance.requestRaw(output::OutputEndpointRole::Humidifier,
                                  output::BinaryOutputState::On, 300U));
  const auto report = f.maintenance.tick(300U, {});
  assert(report.status == output::OutputMaintenanceStatus::TxFailed);
  assert(!f.humidifier.on());
  const auto* humidifier = f.state.find(3U);
  assert(humidifier != nullptr && humidifier->has_attempt);
  assert(humidifier->last_transport.status == output::TransportStatus::Failed);
  assert(!humidifier->has_successful_command ||
         humidifier->last_successful_command.state != output::BinaryOutputState::On);
}

void testExitRearmsThroughDisabledAndArming() {
  Fixture f;
  f.bootstrapAutomatic();
  f.enterMaintenance();
  assert(f.maintenance.requestExit());
  auto report = f.maintenance.tick(400U, {});
  assert(report.mode == output::SupervisorMode::Disabled);
  assert(report.rearm_pending);
  assert(f.automation.requestedEnabled());

  auto automation_report = f.automation.tick(401U, f.scheduleOff(), {});
  report = f.maintenance.tick(401U, {});
  assert(automation_report.mode == output::SupervisorMode::Arming);
  assert(report.rearm_pending);

  automation_report = f.automation.tick(402U, f.scheduleOff(), {});
  report = f.maintenance.tick(402U, {});
  assert(automation_report.mode == output::SupervisorMode::Automatic);
  assert(report.mode == output::SupervisorMode::Automatic);
  assert(!report.rearm_pending);
  assert(report.status == output::OutputMaintenanceStatus::Ready);
}

void testEntryFailureFaultLocks() {
  Fixture f;
  f.bootstrapAutomatic();
  f.lifecycle_transport.result = {output::TransportStatus::Failed,
                                  output::TransportError::IoFailure};
  assert(f.maintenance.requestEnter());
  output::OutputMaintenanceReport report{};
  for (std::uint64_t now = 500U;
       now < 540U && f.lifecycle.mode() != output::SupervisorMode::FaultLocked; ++now) {
    f.automation.tick(now, f.scheduleOff(), {});
    report = f.maintenance.tick(now, {});
  }
  assert(f.lifecycle.mode() == output::SupervisorMode::FaultLocked);
  report = f.maintenance.tick(540U, {});
  assert(report.status == output::OutputMaintenanceStatus::FaultLocked);
  assert(f.raw_transport.count == 0U);
}

} // namespace

int main() {
  testRawDeniedOutsideMaintenance();
  testSafeEntryCompletesBeforeMaintenanceAndClearsPhysicalTruth();
  testHardSafetyVetoAndAlignedRawCommand();
  testFailedRawDoesNotAdvanceBinaryPolicy();
  testExitRearmsThroughDisabledAndArming();
  testEntryFailureFaultLocks();
  return 0;
}
