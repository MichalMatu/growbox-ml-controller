#include "climate/compatibility/stage28d/Stage28dRfOutputEndpoint.h"
#include "climate/output/OutputBindings.h"
#include "climate/output/OutputStateStore.h"
#include "climate/output/OutputTransport.h"

#include <array>
#include <cassert>
#include <cstddef>

using namespace growbox::app::climate_io;
using namespace growbox::app::climate_io::stage28d;

namespace {

namespace output = growbox::app::output;

constexpr std::array<output::OutputEndpointId, output::kOutputEndpointCapacity> kOutputEndpoints{
    kExhaustFanEndpoint, kScheduledLightEndpoint, kHumidifierEndpoint};

class FakeTransport final : public output::OutputTransport {
public:
  output::TxResult send(const output::OutputCommand& command) noexcept override {
    assert(count < commands.size());
    commands[count++] = command;
    if (fail_next) {
      fail_next = false;
      return {output::TransportStatus::Failed, output::TransportError::IoFailure};
    }
    return {output::TransportStatus::Completed, output::TransportError::None};
  }

  std::array<output::OutputCommand, 16U> commands{};
  std::size_t count{0U};
  bool fail_next{false};
};

void expectLast(const FakeTransport& tx, ClimateEndpointId endpoint, bool on) {
  assert(tx.count > 0U);
  const auto& command = tx.commands[tx.count - 1U];
  assert(command.endpoint == endpoint);
  assert(command.state == (on ? output::BinaryOutputState::On : output::BinaryOutputState::Off));
}

void testSafeInitializationAndDeduplication() {
  FakeTransport tx;
  Stage28dRfOutputEndpoint endpoint({true, 0.5F}, tx);
  assert(endpoint.initializeSafeState(100U));
  assert(tx.count == 3U);
  assert(endpoint.stateKnown(kScheduledLightEndpoint));
  assert(!endpoint.stateOn(kScheduledLightEndpoint));
  assert(endpoint.stateKnown(kExhaustFanEndpoint));
  assert(!endpoint.stateOn(kExhaustFanEndpoint));
  assert(endpoint.stateKnown(kHumidifierEndpoint));
  assert(!endpoint.stateOn(kHumidifierEndpoint));

  assert(endpoint.write(kExhaustFanEndpoint, 0.0F, 200U));
  assert(tx.count == 3U);
  assert(endpoint.write(kExhaustFanEndpoint, 1.0F, 300U));
  assert(tx.count == 4U);
  expectLast(tx, kExhaustFanEndpoint, true);
  assert(endpoint.write(kExhaustFanEndpoint, 1.0F, 400U));
  assert(tx.count == 4U);
}

void testSafetyForceExhaustOverridesRuleRequest() {
  FakeTransport tx;
  Stage28dRfOutputEndpoint endpoint({true, 0.5F}, tx);
  assert(endpoint.initializeSafeState(0U));
  endpoint.setSafetyForceExhaust(true);
  assert(endpoint.write(kExhaustFanEndpoint, 0.0F, 100U));
  assert(endpoint.stateOn(kExhaustFanEndpoint));
  expectLast(tx, kExhaustFanEndpoint, true);

  endpoint.setSafetyForceExhaust(false);
  assert(endpoint.write(kExhaustFanEndpoint, 0.0F, 200U));
  assert(!endpoint.stateOn(kExhaustFanEndpoint));
  expectLast(tx, kExhaustFanEndpoint, false);
}

void testEmergencyOffBypassesSafetyForce() {
  FakeTransport tx;
  Stage28dRfOutputEndpoint endpoint({true, 0.5F}, tx);
  assert(endpoint.initializeSafeState(0U));
  endpoint.setSafetyForceExhaust(true);
  assert(endpoint.write(kExhaustFanEndpoint, 0.0F, 100U));
  assert(endpoint.stateOn(kExhaustFanEndpoint));

  assert(endpoint.forceOff(kExhaustFanEndpoint, 101U));
  assert(!endpoint.stateOn(kExhaustFanEndpoint));
  expectLast(tx, kExhaustFanEndpoint, false);

  assert(endpoint.write(kExhaustFanEndpoint, 0.0F, 102U));
  assert(endpoint.stateOn(kExhaustFanEndpoint));
  expectLast(tx, kExhaustFanEndpoint, true);
}

void testScheduledLightUsesDedicatedPath() {
  FakeTransport tx;
  Stage28dRfOutputEndpoint endpoint({true, 0.5F}, tx);
  assert(endpoint.initializeSafeState(0U));
  assert(!endpoint.write(kScheduledLightEndpoint, 1.0F, 100U));
  assert(!endpoint.forceOff(kScheduledLightEndpoint, 100U));
  assert(endpoint.writeScheduledLight(true, 100U));
  assert(endpoint.stateOn(kScheduledLightEndpoint));
  expectLast(tx, kScheduledLightEndpoint, true);
  assert(endpoint.writeScheduledLight(true, 200U));
  assert(tx.count == 4U);
  assert(endpoint.writeScheduledLight(false, 300U));
  assert(!endpoint.stateOn(kScheduledLightEndpoint));
  expectLast(tx, kScheduledLightEndpoint, false);
}

void testTransmitFailureDoesNotAdvanceState() {
  FakeTransport tx;
  Stage28dRfOutputEndpoint endpoint({true, 0.5F}, tx);
  assert(endpoint.initializeSafeState(0U));
  tx.fail_next = true;
  assert(!endpoint.write(kHumidifierEndpoint, 1.0F, 100U));
  assert(!endpoint.stateOn(kHumidifierEndpoint));
  assert(endpoint.transmitErrorCount() == 1U);
  assert(endpoint.write(kHumidifierEndpoint, 1.0F, 200U));
  assert(endpoint.stateOn(kHumidifierEndpoint));
  expectLast(tx, kHumidifierEndpoint, true);
}

void testDisabledEndpointFailsClosed() {
  FakeTransport tx;
  Stage28dRfOutputEndpoint endpoint({false, 0.5F}, tx);
  assert(!endpoint.initializeSafeState(0U));
  assert(!endpoint.write(kExhaustFanEndpoint, 1.0F, 100U));
  assert(!endpoint.forceOff(kExhaustFanEndpoint, 100U));
  assert(!endpoint.writeScheduledLight(true, 100U));
  assert(tx.count == 0U);
}

void testShadowStoreMirrorsCommandTruthWithoutFabricatingPhysicalState() {
  output::OutputStateStore store;
  assert(store.configure(kOutputEndpoints, kOutputEndpoints.size()));
  FakeTransport tx;
  Stage28dRfOutputEndpoint endpoint({true, 0.5F}, tx, &store);
  assert(endpoint.initializeSafeState(10U));

  const auto* fan_after_boot = store.find(kExhaustFanEndpoint);
  assert(fan_after_boot != nullptr && fan_after_boot->has_successful_command);
  assert(fan_after_boot->last_successful_command.state == output::BinaryOutputState::Off);
  assert(fan_after_boot->physical.state == output::PhysicalOutputState::Unknown);
  assert(!fan_after_boot->physical.has_independent_feedback);

  endpoint.setSafetyForceExhaust(true);
  assert(endpoint.write(kExhaustFanEndpoint, 0.0F, 100U));
  const auto* fan = store.find(kExhaustFanEndpoint);
  assert(fan != nullptr && fan->has_desired && fan->has_resolved && fan->has_attempt);
  assert(fan->desired.state == output::BinaryOutputState::Off);
  assert(fan->resolved.state == output::BinaryOutputState::On);
  assert(fan->last_transport.status == output::TransportStatus::Completed);
  assert(fan->last_successful_command.state == output::BinaryOutputState::On);
  assert(endpoint.stateOn(kExhaustFanEndpoint));
  assert(fan->physical.state == output::PhysicalOutputState::Unknown);
  const auto fan_attempt_ms = fan->last_attempt_ms;
  const auto tx_count = tx.count;

  assert(endpoint.write(kExhaustFanEndpoint, 0.0F, 110U));
  assert(tx.count == tx_count);
  fan = store.find(kExhaustFanEndpoint);
  assert(fan != nullptr && fan->last_attempt_ms == fan_attempt_ms);

  tx.fail_next = true;
  assert(!endpoint.write(kHumidifierEndpoint, 1.0F, 200U));
  const auto* humidifier = store.find(kHumidifierEndpoint);
  assert(humidifier != nullptr && humidifier->has_desired && humidifier->has_resolved);
  assert(humidifier->desired.state == output::BinaryOutputState::On);
  assert(humidifier->resolved.state == output::BinaryOutputState::On);
  assert(humidifier->has_attempt);
  assert(humidifier->last_attempt.state == output::BinaryOutputState::On);
  assert(humidifier->last_transport.status == output::TransportStatus::Failed);
  assert(humidifier->has_successful_command);
  assert(humidifier->last_successful_command.state == output::BinaryOutputState::Off);
  assert(!endpoint.stateOn(kHumidifierEndpoint));
  assert(humidifier->physical.state == output::PhysicalOutputState::Unknown);
  assert(!humidifier->physical.has_independent_feedback);
}

} // namespace

int main() {
  testSafeInitializationAndDeduplication();
  testSafetyForceExhaustOverridesRuleRequest();
  testEmergencyOffBypassesSafetyForce();
  testScheduledLightUsesDedicatedPath();
  testTransmitFailureDoesNotAdvanceState();
  testDisabledEndpointFailsClosed();
  testShadowStoreMirrorsCommandTruthWithoutFabricatingPhysicalState();
  return 0;
}
