#include "climate/Stage28dBinaryRoleArbiter.h"

#include <cassert>
#include <cmath>
#include <cstdint>
#include <limits>
#include <vector>

using growbox::app::climate_io::ClimateActuatorRole;
using growbox::app::climate_io::ClimateRoleDriver;
using growbox::app::climate_io::stage28d::BinaryRoleArbiterConfig;
using growbox::app::climate_io::stage28d::Stage28dBinaryRoleArbiter;
using growbox::app::climate_io::stage28d::binaryArbiterCounterRegressed;

namespace {

bool near(float left, float right) {
  return std::fabs(left - right) <= 1.0e-6F;
}

struct Call {
  ClimateActuatorRole role{};
  float level{0.0F};
  std::uint64_t at_ms{0U};
  bool safe_off{false};
};

class FakeDriver final : public ClimateRoleDriver {
public:
  std::vector<Call> calls{};
  bool fail_next{false};

  bool apply(ClimateActuatorRole role, float level, std::uint64_t monotonic_ms) noexcept override {
    calls.push_back({role, level, monotonic_ms, false});
    if (fail_next) {
      fail_next = false;
      return false;
    }
    return true;
  }

  bool forceSafeOff(ClimateActuatorRole role, std::uint64_t monotonic_ms) noexcept override {
    calls.push_back({role, 0.0F, monotonic_ms, true});
    if (fail_next) {
      fail_next = false;
      return false;
    }
    return true;
  }
};

void testInstanceIdentityIsMonotonic() {
  FakeDriver downstream{};
  const std::uint32_t before = Stage28dBinaryRoleArbiter::constructionCount();
  Stage28dBinaryRoleArbiter first(downstream);
  Stage28dBinaryRoleArbiter second(downstream);

  assert(first.instanceId() != 0U);
  assert(second.instanceId() > first.instanceId());
  assert(Stage28dBinaryRoleArbiter::constructionCount() >= before + 2U);
}

void testCounterRegressionDistinguishesWrap() {
  assert(!binaryArbiterCounterRegressed(43U, 44U));
  assert(binaryArbiterCounterRegressed(43U, 1U));
  assert(!binaryArbiterCounterRegressed(std::numeric_limits<std::uint32_t>::max() - 2U, 2U));
  assert(binaryArbiterCounterRegressed(std::numeric_limits<std::uint32_t>::max() - 2048U, 2U));
}

void testV5SameInstanceDwellContinuityProof() {
  FakeDriver downstream{};
  Stage28dBinaryRoleArbiter arbiter(downstream);
  const std::uint32_t instance_id = arbiter.instanceId();
  arbiter.synchronizeSafeOff(0U);

  assert(!arbiter.exhaustOn());
  assert(arbiter.transitionCount() == 0U);
  assert(arbiter.dwellHoldCount() == 0U);
  assert(arbiter.continuityFaultCount() == 0U);

  // A request below the ON threshold keeps the synchronized safe-OFF state
  // without consuming minimum-OFF dwell holds.
  assert(arbiter.apply(ClimateActuatorRole::ExhaustFan, 0.099F, 500U));
  assert(downstream.calls.empty());
  assert(arbiter.dwellHoldCount() == 0U);
  assert(arbiter.transitionCount() == 0U);

  // Reproduce the historical V5 request magnitude while remaining inside the
  // 120 s minimum-OFF window. One continuously living arbiter can only advance
  // this cumulative counter; it cannot produce 43 -> 1 without uint32 wrap.
  for (std::uint32_t index = 0U; index < 43U; ++index) {
    const std::uint32_t before = arbiter.dwellHoldCount();
    assert(arbiter.apply(ClimateActuatorRole::ExhaustFan, 0.111F, 1'000U + index));
    assert(arbiter.instanceId() == instance_id);
    assert(arbiter.dwellHoldCount() == before + 1U);
    assert(arbiter.dwellHoldCount() == index + 1U);
    assert(arbiter.transitionCount() == 0U);
    assert(arbiter.continuityFaultCount() == 0U);
    assert(downstream.calls.empty());
  }

  assert(arbiter.dwellHoldCount() == 43U);
  assert(binaryArbiterCounterRegressed(arbiter.dwellHoldCount(), 1U));

  // Immediately before the dwell boundary the same request is still held OFF
  // and the cumulative counter advances 43 -> 44, never 43 -> 1.
  assert(arbiter.apply(ClimateActuatorRole::ExhaustFan, 0.111F, 119'999U));
  assert(arbiter.instanceId() == instance_id);
  assert(arbiter.dwellHoldCount() == 44U);
  assert(arbiter.transitionCount() == 0U);
  assert(!arbiter.exhaustOn());
  assert(downstream.calls.empty());
  assert(arbiter.continuityFaultCount() == 0U);

  // At the exact 120 s minimum-OFF boundary the 0.111 request becomes eligible
  // and produces one OFF -> ON transition without resetting dwell history.
  assert(arbiter.apply(ClimateActuatorRole::ExhaustFan, 0.111F, 120'000U));
  assert(arbiter.instanceId() == instance_id);
  assert(arbiter.exhaustOn());
  assert(arbiter.transitionCount() == 1U);
  assert(arbiter.dwellHoldCount() == 44U);
  assert(downstream.calls.size() == 1U);
  assert(near(downstream.calls.back().level, 1.0F));

  // A subsequent same-state call causes continuity checking to observe the
  // transition as monotonic and still reports no continuity fault.
  assert(arbiter.apply(ClimateActuatorRole::ExhaustFan, 0.111F, 120'001U));
  assert(arbiter.transitionCount() == 1U);
  assert(arbiter.dwellHoldCount() == 44U);
  assert(arbiter.continuityFaultCount() == 0U);
}

void testFanUsesHysteresisAndMinimumDwell() {
  FakeDriver downstream{};
  Stage28dBinaryRoleArbiter arbiter(downstream);
  arbiter.synchronizeSafeOff(1'000U);

  assert(arbiter.apply(ClimateActuatorRole::ExhaustFan, 0.29F, 60'000U));
  assert(downstream.calls.empty());
  assert(near(arbiter.appliedLevel(ClimateActuatorRole::ExhaustFan, 0.29F), 0.0F));

  assert(arbiter.apply(ClimateActuatorRole::ExhaustFan, 0.29F, 121'000U));
  assert(downstream.calls.size() == 1U);
  assert(near(downstream.calls.back().level, 1.0F));
  assert(arbiter.exhaustOn());

  assert(arbiter.apply(ClimateActuatorRole::ExhaustFan, 0.0F, 180'000U));
  assert(downstream.calls.size() == 1U);
  assert(near(arbiter.appliedLevel(ClimateActuatorRole::ExhaustFan, 0.0F), 1.0F));

  assert(arbiter.apply(ClimateActuatorRole::ExhaustFan, 0.0F, 241'000U));
  assert(downstream.calls.size() == 2U);
  assert(near(downstream.calls.back().level, 0.0F));
  assert(!arbiter.exhaustOn());

  assert(arbiter.apply(ClimateActuatorRole::ExhaustFan, 0.05F, 400'000U));
  assert(downstream.calls.size() == 2U);
  assert(!arbiter.exhaustOn());
  assert(arbiter.dwellHoldCount() >= 2U);
  assert(arbiter.continuityFaultCount() == 0U);
}

void testThermalSafetyBypassesMinimumOffButNotMinimumOn() {
  FakeDriver downstream{};
  Stage28dBinaryRoleArbiter arbiter(downstream);
  arbiter.synchronizeSafeOff(10'000U);

  arbiter.setSafetyForceExhaust(true);
  assert(arbiter.apply(ClimateActuatorRole::ExhaustFan, 0.0F, 11'000U));
  assert(downstream.calls.size() == 1U);
  assert(near(downstream.calls.back().level, 1.0F));
  assert(arbiter.exhaustOn());
  assert(arbiter.safetyOverrideCount() == 1U);

  arbiter.setSafetyForceExhaust(false);
  assert(arbiter.apply(ClimateActuatorRole::ExhaustFan, 0.0F, 12'000U));
  assert(downstream.calls.size() == 1U);
  assert(arbiter.exhaustOn());

  assert(arbiter.apply(ClimateActuatorRole::ExhaustFan, 0.0F, 131'000U));
  assert(downstream.calls.size() == 2U);
  assert(!arbiter.exhaustOn());
  assert(arbiter.continuityFaultCount() == 0U);
}

void testHumidifierUsesLongerDwell() {
  FakeDriver downstream{};
  Stage28dBinaryRoleArbiter arbiter(downstream);
  arbiter.synchronizeSafeOff(0U);

  assert(arbiter.apply(ClimateActuatorRole::Humidifier, 0.40F, 120'000U));
  assert(downstream.calls.empty());
  assert(!arbiter.humidifierOn());

  assert(arbiter.apply(ClimateActuatorRole::Humidifier, 0.40F, 180'000U));
  assert(downstream.calls.size() == 1U);
  assert(arbiter.humidifierOn());

  assert(arbiter.apply(ClimateActuatorRole::Humidifier, 0.0F, 300'000U));
  assert(downstream.calls.size() == 1U);
  assert(arbiter.humidifierOn());

  assert(arbiter.apply(ClimateActuatorRole::Humidifier, 0.0F, 360'000U));
  assert(downstream.calls.size() == 2U);
  assert(!arbiter.humidifierOn());
  assert(arbiter.continuityFaultCount() == 0U);
}

void testFailedTransitionDoesNotAdvanceState() {
  FakeDriver downstream{};
  Stage28dBinaryRoleArbiter arbiter(downstream);
  arbiter.synchronizeSafeOff(0U);
  downstream.fail_next = true;

  assert(!arbiter.apply(ClimateActuatorRole::ExhaustFan, 0.50F, 120'000U));
  assert(!arbiter.exhaustOn());
  assert(near(arbiter.appliedLevel(ClimateActuatorRole::ExhaustFan, 0.50F), 0.0F));

  assert(arbiter.apply(ClimateActuatorRole::ExhaustFan, 0.50F, 121'000U));
  assert(arbiter.exhaustOn());
  assert(arbiter.continuityFaultCount() == 0U);
}

void testFailSafeOffBypassesDwell() {
  FakeDriver downstream{};
  Stage28dBinaryRoleArbiter arbiter(downstream);
  arbiter.synchronizeSafeOff(0U);
  assert(arbiter.apply(ClimateActuatorRole::ExhaustFan, 0.50F, 120'000U));
  assert(arbiter.exhaustOn());

  assert(arbiter.forceSafeOff(ClimateActuatorRole::ExhaustFan, 121'000U));
  assert(!arbiter.exhaustOn());
  assert(downstream.calls.back().safe_off);
  assert(near(downstream.calls.back().level, 0.0F));
  assert(arbiter.continuityFaultCount() == 0U);
}

} // namespace

int main() {
  testInstanceIdentityIsMonotonic();
  testCounterRegressionDistinguishesWrap();
  testV5SameInstanceDwellContinuityProof();
  testFanUsesHysteresisAndMinimumDwell();
  testThermalSafetyBypassesMinimumOffButNotMinimumOn();
  testHumidifierUsesLongerDwell();
  testFailedTransitionDoesNotAdvanceState();
  testFailSafeOffBypassesDwell();
  return 0;
}
