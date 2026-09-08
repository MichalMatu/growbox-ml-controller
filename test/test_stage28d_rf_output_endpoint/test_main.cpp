#include "climate/Stage28dOutputBindings.h"
#include "climate/Stage28dRfOutputEndpoint.h"
#include "climate/output/OutputTransport.h"

#include <array>
#include <cassert>
#include <cstddef>

using namespace growbox::app::climate_io;
using namespace growbox::app::climate_io::stage28d;

namespace {

class FakeTransport final : public growbox::app::output::OutputTransport {
public:
  growbox::app::output::TxResult
  send(const growbox::app::output::OutputCommand& command) noexcept override {
    assert(count < commands.size());
    commands[count++] = command;
    if (fail_next) {
      fail_next = false;
      return {growbox::app::output::TransportStatus::Failed,
              growbox::app::output::TransportError::IoFailure};
    }
    return {growbox::app::output::TransportStatus::Completed,
            growbox::app::output::TransportError::None};
  }

  std::array<growbox::app::output::OutputCommand, 16U> commands{};
  std::size_t count{0U};
  bool fail_next{false};
};

void expectLast(const FakeTransport& tx, ClimateEndpointId endpoint, bool on) {
  assert(tx.count > 0U);
  const auto& command = tx.commands[tx.count - 1U];
  assert(command.endpoint == endpoint);
  assert(command.state == (on ? growbox::app::output::BinaryOutputState::On
                              : growbox::app::output::BinaryOutputState::Off));
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

} // namespace

int main() {
  testSafeInitializationAndDeduplication();
  testSafetyForceExhaustOverridesRuleRequest();
  testEmergencyOffBypassesSafetyForce();
  testScheduledLightUsesDedicatedPath();
  testTransmitFailureDoesNotAdvanceState();
  testDisabledEndpointFailsClosed();
  return 0;
}
