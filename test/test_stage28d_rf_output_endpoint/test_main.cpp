#include "climate/Stage28dOutputBindings.h"
#include "climate/Stage28dRfOutputEndpoint.h"

#include <array>
#include <cassert>
#include <cstddef>
#include <cstdint>

using namespace growbox::app::climate_io;
using namespace growbox::app::climate_io::stage28d;

namespace {

class FakeTransmitter final : public RfCommandTransmitter {
public:
  bool transmit(const rf433::FrameConfig& frame) noexcept override {
    if (fail_next) {
      fail_next = false;
      return false;
    }
    assert(count < codes.size());
    codes[count++] = frame.key.code;
    return true;
  }

  std::array<std::uint32_t, 16U> codes{};
  std::size_t count{0U};
  bool fail_next{false};
};

void testSafeInitializationAndDeduplication() {
  FakeTransmitter tx;
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
  assert(endpoint.write(kExhaustFanEndpoint, 1.0F, 400U));
  assert(tx.count == 4U);
}

void testSafetyForceExhaustOverridesRuleRequest() {
  FakeTransmitter tx;
  Stage28dRfOutputEndpoint endpoint({true, 0.5F}, tx);
  assert(endpoint.initializeSafeState(0U));
  endpoint.setSafetyForceExhaust(true);
  assert(endpoint.write(kExhaustFanEndpoint, 0.0F, 100U));
  assert(endpoint.stateOn(kExhaustFanEndpoint));
  assert(tx.codes[tx.count - 1U] == rf433::kRemoteSocket1.on.key.code);

  endpoint.setSafetyForceExhaust(false);
  assert(endpoint.write(kExhaustFanEndpoint, 0.0F, 200U));
  assert(!endpoint.stateOn(kExhaustFanEndpoint));
  assert(tx.codes[tx.count - 1U] == rf433::kRemoteSocket1.off.key.code);
}

void testEmergencyOffBypassesSafetyForce() {
  FakeTransmitter tx;
  Stage28dRfOutputEndpoint endpoint({true, 0.5F}, tx);
  assert(endpoint.initializeSafeState(0U));
  endpoint.setSafetyForceExhaust(true);
  assert(endpoint.write(kExhaustFanEndpoint, 0.0F, 100U));
  assert(endpoint.stateOn(kExhaustFanEndpoint));

  assert(endpoint.forceOff(kExhaustFanEndpoint, 101U));
  assert(!endpoint.stateOn(kExhaustFanEndpoint));
  assert(tx.codes[tx.count - 1U] == rf433::kRemoteSocket1.off.key.code);

  // The ordinary path still honors the safety force afterwards.
  assert(endpoint.write(kExhaustFanEndpoint, 0.0F, 102U));
  assert(endpoint.stateOn(kExhaustFanEndpoint));
  assert(tx.codes[tx.count - 1U] == rf433::kRemoteSocket1.on.key.code);
}

void testScheduledLightUsesDedicatedPath() {
  FakeTransmitter tx;
  Stage28dRfOutputEndpoint endpoint({true, 0.5F}, tx);
  assert(endpoint.initializeSafeState(0U));
  assert(!endpoint.write(kScheduledLightEndpoint, 1.0F, 100U));
  assert(!endpoint.forceOff(kScheduledLightEndpoint, 100U));
  assert(endpoint.writeScheduledLight(true, 100U));
  assert(endpoint.stateOn(kScheduledLightEndpoint));
  assert(tx.codes[tx.count - 1U] == rf433::kRemoteSocket2.on.key.code);
  assert(endpoint.writeScheduledLight(true, 200U));
  assert(tx.count == 4U);
  assert(endpoint.writeScheduledLight(false, 300U));
  assert(!endpoint.stateOn(kScheduledLightEndpoint));
  assert(tx.codes[tx.count - 1U] == rf433::kRemoteSocket2.off.key.code);
}

void testTransmitFailureDoesNotAdvanceState() {
  FakeTransmitter tx;
  Stage28dRfOutputEndpoint endpoint({true, 0.5F}, tx);
  assert(endpoint.initializeSafeState(0U));
  tx.fail_next = true;
  assert(!endpoint.write(kHumidifierEndpoint, 1.0F, 100U));
  assert(!endpoint.stateOn(kHumidifierEndpoint));
  assert(endpoint.transmitErrorCount() == 1U);
  assert(endpoint.write(kHumidifierEndpoint, 1.0F, 200U));
  assert(endpoint.stateOn(kHumidifierEndpoint));
}

void testDisabledEndpointFailsClosed() {
  FakeTransmitter tx;
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
