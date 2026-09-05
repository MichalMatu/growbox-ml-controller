#include "climate/Stage28dLampSafety.h"

#include <cassert>
#include <cstdint>
#include <limits>

using growbox::app::climate_io::stage28d::LampSafetyConfig;
using growbox::app::climate_io::stage28d::LampSafetyController;
using growbox::app::climate_io::stage28d::LampSafetyInput;
using growbox::app::climate_io::stage28d::LampSafetyReason;
using growbox::app::climate_io::stage28d::validateLampSafetyConfig;

namespace {

LampSafetyInput input(float light, float temperature_c, bool valid, std::uint64_t age_ms,
                      std::uint64_t now_ms, bool fan = true) {
  LampSafetyInput value{};
  value.scheduled_light_level = light;
  value.inside_temperature_c = {temperature_c, valid, age_ms};
  value.exhaust_fan_available = fan;
  value.monotonic_ms = now_ms;
  return value;
}

void testSafeTimerOnAndTimerOff() {
  LampSafetyController controller;
  auto on = controller.evaluate(input(1.0F, 24.0F, true, 100U, 1'000U));
  assert(on.schedule_requests_lamp_on);
  assert(on.effective_lamp_on);
  assert(!on.force_exhaust_on);
  assert(!on.thermal_latched);
  assert(on.reason == LampSafetyReason::Safe);

  auto off = controller.evaluate(input(0.0F, 24.0F, true, 100U, 2'000U));
  assert(!off.schedule_requests_lamp_on);
  assert(!off.effective_lamp_on);
  assert(off.reason == LampSafetyReason::TimerOff);
}

void testTripAt28ForcesLampOffAndFanOn() {
  LampSafetyController controller;
  auto decision = controller.evaluate(input(1.0F, 28.0F, true, 0U, 10'000U));
  assert(decision.schedule_requests_lamp_on);
  assert(!decision.effective_lamp_on);
  assert(decision.force_exhaust_on);
  assert(decision.thermal_latched);
  assert(decision.reason == LampSafetyReason::OverTemperature);
}

void testRecoveryRequires26OrBelowForTenMinutes() {
  LampSafetyController controller;
  controller.evaluate(input(1.0F, 28.2F, true, 0U, 0U));

  auto start = controller.evaluate(input(1.0F, 26.0F, true, 0U, 10'000U));
  assert(!start.effective_lamp_on);
  assert(start.force_exhaust_on);
  assert(start.reason == LampSafetyReason::RecoveryHold);

  auto almost = controller.evaluate(input(1.0F, 25.9F, true, 0U, 609'999U));
  assert(!almost.effective_lamp_on);
  assert(almost.thermal_latched);

  auto recovered = controller.evaluate(input(1.0F, 25.9F, true, 0U, 610'000U));
  assert(recovered.effective_lamp_on);
  assert(!recovered.force_exhaust_on);
  assert(!recovered.thermal_latched);
  assert(recovered.reason == LampSafetyReason::Safe);
}

void testRecoveryHoldResetsAbove26() {
  LampSafetyController controller;
  controller.evaluate(input(1.0F, 29.0F, true, 0U, 0U));
  controller.evaluate(input(1.0F, 25.5F, true, 0U, 100U));
  controller.evaluate(input(1.0F, 26.1F, true, 0U, 500'000U));
  auto restarted = controller.evaluate(input(1.0F, 25.5F, true, 0U, 600'000U));
  assert(!restarted.effective_lamp_on);
  auto recovered = controller.evaluate(input(1.0F, 25.5F, true, 0U, 1'200'000U));
  assert(recovered.effective_lamp_on);
}

void testStaleInvalidAndNonFiniteTemperatureFailClosed() {
  LampSafetyController stale_controller;
  auto stale = stale_controller.evaluate(input(1.0F, 24.0F, true, 30'001U, 1U));
  assert(!stale.effective_lamp_on);
  assert(stale.force_exhaust_on);
  assert(stale.thermal_latched);
  assert(stale.reason == LampSafetyReason::TemperatureUnavailable);

  LampSafetyController invalid_controller;
  auto invalid = invalid_controller.evaluate(input(1.0F, 24.0F, false, 0U, 1U));
  assert(!invalid.effective_lamp_on);
  assert(invalid.force_exhaust_on);

  LampSafetyController nan_controller;
  auto nonfinite = nan_controller.evaluate(
      input(1.0F, std::numeric_limits<float>::quiet_NaN(), true, 0U, 1U));
  assert(!nonfinite.effective_lamp_on);
  assert(nonfinite.force_exhaust_on);
}

void testNoFanCapabilityDoesNotInventActuation() {
  LampSafetyController controller;
  auto decision = controller.evaluate(input(1.0F, 28.5F, true, 0U, 0U, false));
  assert(!decision.effective_lamp_on);
  assert(!decision.force_exhaust_on);
  assert(decision.thermal_latched);
}

void testInvalidConfigFailsClosed() {
  LampSafetyConfig config{};
  config.recovery_temperature_c = 29.0F;
  assert(!validateLampSafetyConfig(config));
  LampSafetyController controller(config);
  auto decision = controller.evaluate(input(1.0F, 24.0F, true, 0U, 0U));
  assert(!decision.effective_lamp_on);
  assert(decision.force_exhaust_on);
  assert(decision.reason == LampSafetyReason::InvalidConfig);
}

} // namespace

int main() {
  testSafeTimerOnAndTimerOff();
  testTripAt28ForcesLampOffAndFanOn();
  testRecoveryRequires26OrBelowForTenMinutes();
  testRecoveryHoldResetsAbove26();
  testStaleInvalidAndNonFiniteTemperatureFailClosed();
  testNoFanCapabilityDoesNotInventActuation();
  testInvalidConfigFailsClosed();
  return 0;
}
