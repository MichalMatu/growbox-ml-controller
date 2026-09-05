#include "climate/Stage28dBinaryRoleArbiter.h"

#include <cassert>
#include <cmath>
#include <cstdint>
#include <vector>

using growbox::app::climate_io::ClimateActuatorRole;
using growbox::app::climate_io::ClimateRoleDriver;
using growbox::app::climate_io::stage28d::BinaryRoleArbiterConfig;
using growbox::app::climate_io::stage28d::Stage28dBinaryRoleArbiter;

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
}

} // namespace

int main() {
  testFanUsesHysteresisAndMinimumDwell();
  testThermalSafetyBypassesMinimumOffButNotMinimumOn();
  testHumidifierUsesLongerDwell();
  testFailedTransitionDoesNotAdvanceState();
  testFailSafeOffBypassesDwell();
  return 0;
}
