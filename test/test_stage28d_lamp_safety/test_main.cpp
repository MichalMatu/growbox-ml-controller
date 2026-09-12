#include "climate/output/LampSafety.h"
#include "climate/output/OutputBindings.h"

#include <cassert>
#include <cstdint>
#include <limits>

using growbox::app::climate_io::stage28d::buildLampSafetyEnvelope;
using growbox::app::climate_io::stage28d::kExhaustFanEndpoint;
using growbox::app::climate_io::stage28d::kScheduledLightEndpoint;
using growbox::app::climate_io::stage28d::LampSafetyConfig;
using growbox::app::climate_io::stage28d::LampSafetyController;
using growbox::app::climate_io::stage28d::LampSafetyEnvelopeSnapshot;
using growbox::app::climate_io::stage28d::LampSafetyInput;
using growbox::app::climate_io::stage28d::LampSafetyReason;
using growbox::app::climate_io::stage28d::validateLampSafetyConfig;
namespace output = growbox::app::output;

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
  auto nonfinite =
      nan_controller.evaluate(input(1.0F, std::numeric_limits<float>::quiet_NaN(), true, 0U, 1U));
  assert(!nonfinite.effective_lamp_on);
  assert(nonfinite.force_exhaust_on);
}

void testInitialTemperatureUnavailableDoesNotStartThermalRecovery() {
  LampSafetyController controller;
  const auto unavailable = controller.evaluate(input(1.0F, 24.0F, false, 0U, 1U));
  assert(!unavailable.effective_lamp_on);
  assert(unavailable.force_exhaust_on);
  assert(unavailable.thermal_latched);
  assert(unavailable.reason == LampSafetyReason::TemperatureUnavailable);

  const auto valid = controller.evaluate(input(1.0F, 27.0F, true, 0U, 2U));
  assert(valid.effective_lamp_on);
  assert(!valid.force_exhaust_on);
  assert(!valid.thermal_latched);
  assert(!valid.recovery_running);
  assert(valid.reason == LampSafetyReason::Safe);
}

void testTemperatureUnavailablePreservesRealOvertemperatureLatch() {
  LampSafetyController controller;
  const auto tripped = controller.evaluate(input(1.0F, 29.0F, true, 0U, 0U));
  assert(tripped.thermal_latched);
  assert(tripped.reason == LampSafetyReason::OverTemperature);

  const auto unavailable = controller.evaluate(input(1.0F, 24.0F, false, 0U, 100U));
  assert(!unavailable.effective_lamp_on);
  assert(unavailable.thermal_latched);
  assert(unavailable.reason == LampSafetyReason::TemperatureUnavailable);

  const auto warm = controller.evaluate(input(1.0F, 27.0F, true, 0U, 200U));
  assert(!warm.effective_lamp_on);
  assert(warm.thermal_latched);
  assert(!warm.recovery_running);
  assert(warm.reason == LampSafetyReason::RecoveryHold);

  const auto recovery_start = controller.evaluate(input(1.0F, 25.5F, true, 0U, 1'000U));
  assert(!recovery_start.effective_lamp_on);
  assert(recovery_start.thermal_latched);
  assert(recovery_start.recovery_running);

  const auto almost = controller.evaluate(input(1.0F, 25.5F, true, 0U, 600'999U));
  assert(!almost.effective_lamp_on);
  assert(almost.thermal_latched);

  const auto recovered = controller.evaluate(input(1.0F, 25.5F, true, 0U, 601'000U));
  assert(recovered.effective_lamp_on);
  assert(!recovered.thermal_latched);
  assert(!recovered.recovery_running);
  assert(recovered.reason == LampSafetyReason::Safe);
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

void testEnvelopeLeavesScheduleAuthorityUnconstrainedWhenThermallySafe() {
  LampSafetyController controller;
  const auto sample = input(0.0F, 24.0F, true, 77U, 2'000U);
  const auto decision = controller.evaluate(sample);
  LampSafetyEnvelopeSnapshot snapshot{};
  assert(buildLampSafetyEnvelope(sample, decision, 9U, snapshot));
  assert(snapshot.reason == LampSafetyReason::TimerOff);
  assert(!snapshot.thermal_latched);
  assert(!snapshot.recovery_running);
  assert(snapshot.evidence_monotonic_ms == 2'000U);
  assert(snapshot.temperature_age_ms == 77U);
  assert(snapshot.envelope.metadata.sequence == 9U);
  assert(snapshot.envelope.metadata.monotonic_ms == 2'000U);
  assert(snapshot.envelope.metadata.source == output::OutputSource::Safety);
  assert(snapshot.envelope.metadata.reason == output::OutputReason::None);
  for (const auto& constraint : snapshot.envelope.endpoints) {
    assert(!output::safetyConstraintActive(constraint));
  }
}

void testEnvelopeMapsThermalLatchToLampOffAndFanOn() {
  LampSafetyController controller;
  const auto sample = input(1.0F, 28.0F, true, 321U, 10'000U);
  const auto decision = controller.evaluate(sample);
  LampSafetyEnvelopeSnapshot snapshot{};
  assert(buildLampSafetyEnvelope(sample, decision, 55U, snapshot));
  assert(snapshot.reason == LampSafetyReason::OverTemperature);
  assert(snapshot.thermal_latched);
  assert(!snapshot.recovery_running);
  assert(snapshot.evidence_monotonic_ms == 10'000U);
  assert(snapshot.temperature_age_ms == 321U);
  assert(snapshot.envelope.metadata.reason == output::OutputReason::ThermalSafety);
  assert(output::safetyConstraintActive(snapshot.envelope.endpoints[0]));
  assert(snapshot.envelope.endpoints[0].endpoint == kScheduledLightEndpoint);
  assert(snapshot.envelope.endpoints[0].constraint == output::SafetyConstraint::ForceOff);
  assert(snapshot.envelope.endpoints[0].reason == output::OutputReason::ThermalSafety);
  assert(output::safetyConstraintActive(snapshot.envelope.endpoints[1]));
  assert(snapshot.envelope.endpoints[1].endpoint == kExhaustFanEndpoint);
  assert(snapshot.envelope.endpoints[1].constraint == output::SafetyConstraint::ForceOn);
  assert(!output::safetyConstraintActive(snapshot.envelope.endpoints[2]));
}

void testEnvelopePreservesRecoveryMetadata() {
  LampSafetyController controller;
  (void)controller.evaluate(input(1.0F, 29.0F, true, 0U, 0U));
  const auto sample = input(1.0F, 26.0F, true, 10U, 10'000U);
  const auto decision = controller.evaluate(sample);
  assert(decision.recovery_running);
  assert(decision.recovery_started_ms == 10'000U);

  LampSafetyEnvelopeSnapshot snapshot{};
  assert(buildLampSafetyEnvelope(sample, decision, 3U, snapshot));
  assert(snapshot.reason == LampSafetyReason::RecoveryHold);
  assert(snapshot.thermal_latched);
  assert(snapshot.recovery_running);
  assert(snapshot.recovery_started_ms == 10'000U);
  assert(snapshot.envelope.endpoints[0].constraint == output::SafetyConstraint::ForceOff);
  assert(snapshot.envelope.endpoints[1].constraint == output::SafetyConstraint::ForceOn);

  const auto recovered_sample = input(1.0F, 25.9F, true, 0U, 610'000U);
  const auto recovered = controller.evaluate(recovered_sample);
  assert(!recovered.thermal_latched);
  assert(!recovered.recovery_running);
  assert(recovered.recovery_started_ms == 0U);
  assert(buildLampSafetyEnvelope(recovered_sample, recovered, 4U, snapshot));
  for (const auto& constraint : snapshot.envelope.endpoints) {
    assert(!output::safetyConstraintActive(constraint));
  }
}

void testEnvelopeDoesNotInventUnavailableFan() {
  LampSafetyController controller;
  const auto sample = input(1.0F, 28.5F, true, 0U, 1U, false);
  const auto decision = controller.evaluate(sample);
  LampSafetyEnvelopeSnapshot snapshot{};
  assert(buildLampSafetyEnvelope(sample, decision, 1U, snapshot));
  assert(snapshot.thermal_latched);
  assert(snapshot.envelope.endpoints[0].endpoint == kScheduledLightEndpoint);
  assert(snapshot.envelope.endpoints[0].constraint == output::SafetyConstraint::ForceOff);
  assert(!output::safetyConstraintActive(snapshot.envelope.endpoints[1]));
}

} // namespace

int main() {
  testSafeTimerOnAndTimerOff();
  testTripAt28ForcesLampOffAndFanOn();
  testRecoveryRequires26OrBelowForTenMinutes();
  testRecoveryHoldResetsAbove26();
  testStaleInvalidAndNonFiniteTemperatureFailClosed();
  testInitialTemperatureUnavailableDoesNotStartThermalRecovery();
  testTemperatureUnavailablePreservesRealOvertemperatureLatch();
  testNoFanCapabilityDoesNotInventActuation();
  testInvalidConfigFailsClosed();
  testEnvelopeLeavesScheduleAuthorityUnconstrainedWhenThermallySafe();
  testEnvelopeMapsThermalLatchToLampOffAndFanOn();
  testEnvelopePreservesRecoveryMetadata();
  testEnvelopeDoesNotInventUnavailableFan();
  return 0;
}
