#include "climate/Stage28dLampSafety.h"
#include "climate/Stage28dOutputBindings.h"
#include "climate/output/OutputIntents.h"
#include "climate/runtime/Stage27ScheduleIntentAdapter.h"

#include <cassert>
#include <cstdint>
#include <limits>

namespace {

namespace output = growbox::app::output;
using growbox::app::climate_io::ClimateWallClockSnapshot;
using growbox::app::climate_io::runtime::buildStage27ScheduleIntent;
using growbox::app::climate_io::stage28d::buildLampSafetyEnvelope;
using growbox::app::climate_io::stage28d::kExhaustFanEndpoint;
using growbox::app::climate_io::stage28d::kScheduledLightEndpoint;
using growbox::app::climate_io::stage28d::LampSafetyConfig;
using growbox::app::climate_io::stage28d::LampSafetyController;
using growbox::app::climate_io::stage28d::LampSafetyDecision;
using growbox::app::climate_io::stage28d::LampSafetyEnvelopeSnapshot;
using growbox::app::climate_io::stage28d::LampSafetyInput;
using growbox::app::climate_io::stage28d::LampSafetyReason;

struct ShadowProjection {
  bool lamp_on{false};
  bool fan_forced_on{false};
};

const output::EndpointIntent* findIntent(const output::ScheduleIntent& intent,
                                         output::OutputEndpointId endpoint) {
  for (const auto& candidate : intent.endpoints) {
    if (output::endpointIntentActive(candidate) && candidate.endpoint == endpoint) {
      return &candidate;
    }
  }
  return nullptr;
}

const output::SafetyEndpointConstraint* findConstraint(const output::SafetyEnvelope& envelope,
                                                       output::OutputEndpointId endpoint) {
  for (const auto& candidate : envelope.endpoints) {
    if (output::safetyConstraintActive(candidate) && candidate.endpoint == endpoint) {
      return &candidate;
    }
  }
  return nullptr;
}

ShadowProjection projectShadow(const output::ScheduleIntent& schedule,
                               const output::SafetyEnvelope& safety) {
  ShadowProjection result{};
  const auto* lamp = findIntent(schedule, kScheduledLightEndpoint);
  assert(lamp != nullptr);
  result.lamp_on = lamp->level >= 0.5F;

  if (const auto* lamp_safety = findConstraint(safety, kScheduledLightEndpoint)) {
    if (lamp_safety->constraint == output::SafetyConstraint::ForceOff ||
        lamp_safety->constraint == output::SafetyConstraint::Inhibit) {
      result.lamp_on = false;
    } else if (lamp_safety->constraint == output::SafetyConstraint::ForceOn) {
      result.lamp_on = true;
    }
  }

  if (const auto* fan = findConstraint(safety, kExhaustFanEndpoint)) {
    result.fan_forced_on = fan->constraint == output::SafetyConstraint::ForceOn;
  }
  return result;
}

output::ScheduleIntent scheduleAt(std::uint64_t unix_time_s, std::uint64_t now_ms) {
  output::ScheduleIntent intent{};
  const ClimateWallClockSnapshot clock{true, unix_time_s};
  assert(buildStage27ScheduleIntent(now_ms, clock, now_ms + 1U, intent));
  return intent;
}

float scheduledLevel(const output::ScheduleIntent& intent) {
  const auto* lamp = findIntent(intent, kScheduledLightEndpoint);
  assert(lamp != nullptr);
  return lamp->level;
}

void assertParity(LampSafetyController& controller, const output::ScheduleIntent& schedule,
                  float temperature_c, bool temperature_valid, std::uint64_t temperature_age_ms,
                  std::uint64_t now_ms, bool fan_available, LampSafetyReason expected_reason) {
  const LampSafetyInput input{scheduledLevel(schedule),
                              {temperature_c, temperature_valid, temperature_age_ms},
                              fan_available,
                              now_ms};
  const LampSafetyDecision legacy = controller.evaluate(input);
  assert(legacy.reason == expected_reason);

  LampSafetyEnvelopeSnapshot envelope{};
  assert(buildLampSafetyEnvelope(input, legacy, now_ms + 10U, envelope));
  const auto shadow = projectShadow(schedule, envelope.envelope);
  assert(shadow.lamp_on == legacy.effective_lamp_on);
  assert(shadow.fan_forced_on == legacy.force_exhaust_on);
}

void testDayAndNightScheduleParity() {
  LampSafetyController controller;
  const auto day = scheduleAt(1768453200ULL, 1'000U); // Warsaw 06:00 winter
  assertParity(controller, day, 24.0F, true, 0U, 1'000U, true, LampSafetyReason::Safe);

  const auto night = scheduleAt(1768510800ULL, 2'000U); // Warsaw 22:00 winter
  assertParity(controller, night, 24.0F, true, 0U, 2'000U, true, LampSafetyReason::TimerOff);
}

void testTemperatureUnavailableParity() {
  LampSafetyController controller;
  const auto day = scheduleAt(1768453200ULL, 10'000U);
  assertParity(controller, day, 24.0F, false, 0U, 10'000U, true,
               LampSafetyReason::TemperatureUnavailable);
}

void testOverTemperatureParity() {
  LampSafetyController controller;
  const auto day = scheduleAt(1768453200ULL, 20'000U);
  assertParity(controller, day, 28.0F, true, 0U, 20'000U, true, LampSafetyReason::OverTemperature);
}

void testRecoveryHoldParity() {
  LampSafetyController controller;
  const auto day = scheduleAt(1768453200ULL, 30'000U);
  assertParity(controller, day, 29.0F, true, 0U, 30'000U, true, LampSafetyReason::OverTemperature);
  assertParity(controller, day, 26.0F, true, 0U, 40'000U, true, LampSafetyReason::RecoveryHold);
}

void testInvalidConfigParity() {
  LampSafetyConfig config{};
  config.recovery_temperature_c = config.trip_temperature_c;
  LampSafetyController controller(config);
  const auto day = scheduleAt(1768453200ULL, 50'000U);
  assertParity(controller, day, 24.0F, true, 0U, 50'000U, true, LampSafetyReason::InvalidConfig);
}

void testUnavailableFanIsNotInvented() {
  LampSafetyController controller;
  const auto day = scheduleAt(1768453200ULL, 60'000U);
  assertParity(controller, day, std::numeric_limits<float>::quiet_NaN(), true, 0U, 60'000U, false,
               LampSafetyReason::TemperatureUnavailable);
}

} // namespace

int main() {
  testDayAndNightScheduleParity();
  testTemperatureUnavailableParity();
  testOverTemperatureParity();
  testRecoveryHoldParity();
  testInvalidConfigParity();
  testUnavailableFanIsNotInvented();
  return 0;
}
