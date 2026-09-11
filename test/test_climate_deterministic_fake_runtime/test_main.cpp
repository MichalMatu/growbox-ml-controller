#include "climate/ClimateApplication.h"
#include "climate/ClimateDeterministicFake.h"

#include <array>
#include <cassert>
#include <cmath>
#include <cstddef>
#include <cstdint>

using namespace growbox::app::climate_io;
using namespace growbox::climate;

namespace {

constexpr std::size_t kRoleCount = 6U;
constexpr std::array<ClimateActuatorRole, kRoleCount> kRoles{
    ClimateActuatorRole::Heater,       ClimateActuatorRole::Cooler,
    ClimateActuatorRole::ExhaustFan,   ClimateActuatorRole::Humidifier,
    ClimateActuatorRole::Dehumidifier, ClimateActuatorRole::Co2Doser,
};

bool near(float left, float right, float tolerance = 1.0e-5F) {
  return std::fabs(left - right) <= tolerance;
}

bool sameMeasured(const MeasuredValue& left, const MeasuredValue& right) {
  return near(left.value, right.value) && left.valid == right.valid && left.age_ms == right.age_ms;
}

bool sameSnapshot(const ClimateInputSnapshot& left, const ClimateInputSnapshot& right) {
  return sameMeasured(left.measurements.air_temperature_c, right.measurements.air_temperature_c) &&
         sameMeasured(left.measurements.relative_humidity_pct,
                      right.measurements.relative_humidity_pct) &&
         sameMeasured(left.measurements.co2_ppm, right.measurements.co2_ppm) &&
         sameMeasured(left.measurements.outside_temperature_c,
                      right.measurements.outside_temperature_c) &&
         sameMeasured(left.measurements.outside_humidity_pct,
                      right.measurements.outside_humidity_pct) &&
         near(left.targets.air_temperature_c, right.targets.air_temperature_c) &&
         near(left.targets.relative_humidity_pct, right.targets.relative_humidity_pct) &&
         near(left.targets.air_vpd_kpa, right.targets.air_vpd_kpa) &&
         left.targets.co2_enabled == right.targets.co2_enabled &&
         near(left.targets.co2_ppm, right.targets.co2_ppm) &&
         near(left.schedule.light_level, right.schedule.light_level) &&
         left.capabilities.heater == right.capabilities.heater &&
         left.capabilities.cooler == right.capabilities.cooler &&
         left.capabilities.exhaust_fan == right.capabilities.exhaust_fan &&
         left.capabilities.humidifier == right.capabilities.humidifier &&
         left.capabilities.dehumidifier == right.capabilities.dehumidifier &&
         left.capabilities.co2_doser == right.capabilities.co2_doser &&
         left.sensor_timeout_ms == right.sensor_timeout_ms;
}

bool sameRequest(const ClimatePolicyRequest& left, const ClimatePolicyRequest& right) {
  return near(left.heater, right.heater) && near(left.cooler, right.cooler) &&
         near(left.exhaust_fan, right.exhaust_fan) && near(left.humidifier, right.humidifier) &&
         near(left.dehumidifier, right.dehumidifier) && near(left.co2_doser, right.co2_doser);
}

bool samePrevious(const PreviousClimateActions& previous, const ClimatePolicyRequest& request) {
  return near(previous.heater, request.heater) && near(previous.cooler, request.cooler) &&
         near(previous.exhaust_fan, request.exhaust_fan) &&
         near(previous.humidifier, request.humidifier) &&
         near(previous.dehumidifier, request.dehumidifier) &&
         near(previous.co2_doser, request.co2_doser);
}

class RecordingRoleDriver final : public ClimateRoleDriver {
public:
  bool apply(ClimateActuatorRole role, float level, std::uint64_t monotonic_ms) noexcept override {
    const std::size_t role_index = calls % kRoleCount;
    assert(role == kRoles[role_index]);
    assert(level >= 0.0F && level <= 1.0F);
    if (role_index == 0U) {
      last_timestamp = monotonic_ms;
    } else {
      assert(monotonic_ms == last_timestamp);
    }
    last_levels[role_index] = level;
    ++calls;
    return true;
  }

  ClimatePolicyRequest lastRequest() const {
    ClimatePolicyRequest request{};
    request.heater = last_levels[0U];
    request.cooler = last_levels[1U];
    request.exhaust_fan = last_levels[2U];
    request.humidifier = last_levels[3U];
    request.dehumidifier = last_levels[4U];
    request.co2_doser = last_levels[5U];
    return request;
  }

  std::size_t calls = 0U;
  std::uint64_t last_timestamp = 0U;
  std::array<float, kRoleCount> last_levels{};
};

ClimateInputSnapshot snapshotAt(DeterministicClimateScenarioProvider& provider,
                                std::uint64_t timestamp) {
  ClimateInputSnapshot snapshot{};
  assert(provider.snapshot(timestamp, snapshot));
  return snapshot;
}

void testTimestampDeterminismAndPeriodicity() {
  DeterministicClimateScenarioProvider first;
  DeterministicClimateScenarioProvider second;
  constexpr std::array<std::uint64_t, 12U> kTimestamps{
      0U,       1'000U,   59'000U,  60'000U,  119'000U, 120'000U,
      179'000U, 180'000U, 239'000U, 240'000U, 241'000U, 777'000U,
  };

  for (const std::uint64_t timestamp : kTimestamps) {
    const ClimateInputSnapshot a = snapshotAt(first, timestamp);
    const ClimateInputSnapshot b = snapshotAt(first, timestamp);
    const ClimateInputSnapshot c = snapshotAt(second, timestamp);
    assert(sameSnapshot(a, b));
    assert(sameSnapshot(a, c));
  }

  assert(DeterministicClimateScenarioProvider::phaseTick(0U) == 0U);
  assert(DeterministicClimateScenarioProvider::phaseTick(239'000U) == 239U);
  assert(DeterministicClimateScenarioProvider::phaseTick(240'000U) == 0U);
  assert(DeterministicClimateScenarioProvider::phaseTick(241'000U) == 1U);
  assert(sameSnapshot(snapshotAt(first, 0U), snapshotAt(first, 240'000U)));
}

void testScenarioTransitionsMeasurementsTargetsScheduleAndCapabilities() {
  DeterministicClimateScenarioProvider provider;
  const ClimateInputSnapshot q0 = snapshotAt(provider, 0U);
  const ClimateInputSnapshot q0_end = snapshotAt(provider, 59'000U);
  const ClimateInputSnapshot q1 = snapshotAt(provider, 60'000U);
  const ClimateInputSnapshot q2 = snapshotAt(provider, 120'000U);
  const ClimateInputSnapshot q3 = snapshotAt(provider, 180'000U);

  assert(q0.measurements.air_temperature_c.valid);
  assert(q0.measurements.relative_humidity_pct.valid);
  assert(q0.measurements.co2_ppm.valid);
  assert(q0.measurements.outside_temperature_c.valid);
  assert(q0.measurements.outside_humidity_pct.valid);
  assert(q0.measurements.air_temperature_c.age_ms == 0U);
  assert(q0.sensor_timeout_ms == kDefaultSensorTimeoutMs);

  assert(q0_end.measurements.air_temperature_c.value > q0.measurements.air_temperature_c.value);
  assert(q0_end.measurements.relative_humidity_pct.value <
         q0.measurements.relative_humidity_pct.value);
  assert(q0_end.measurements.co2_ppm.value > q0.measurements.co2_ppm.value);
  assert(q0_end.measurements.outside_temperature_c.value >
         q0.measurements.outside_temperature_c.value);

  assert(near(q0.schedule.light_level, 1.0F));
  assert(near(q1.schedule.light_level, 1.0F));
  assert(near(q2.schedule.light_level, 0.0F));
  assert(near(q3.schedule.light_level, 0.0F));
  assert(q0.targets.co2_enabled);
  assert(!q2.targets.co2_enabled);
  assert(q0.targets.air_temperature_c > q2.targets.air_temperature_c);

  assert(q0.capabilities.cooler);
  assert(!q1.capabilities.cooler);
  assert(!q2.capabilities.humidifier);
  assert(!q2.capabilities.co2_doser);
  assert(!q3.capabilities.heater);
  assert(!q3.capabilities.dehumidifier);
  assert(q3.capabilities.cooler);
}

void testLongRunThroughFullApplicationPath() {
  DeterministicClimateScenarioProvider provider;
  RecordingRoleDriver driver;
  ClimateRuntimeConfig config{};
  config.mode = ClimatePolicyMode::Rule;
  config.sensor_timeout_ms = kDefaultSensorTimeoutMs;
  config.timestep_s = 1.0F;
  ClimateRuntimeController runtime(nullptr, config);
  ClimateApplication application(runtime, provider, driver);

  ClimatePolicyRequest previous_request{};
  bool saw_output_change = false;
  constexpr std::size_t kTicks = 1'200U;

  for (std::size_t tick = 0U; tick < kTicks; ++tick) {
    const std::uint64_t timestamp = tick * DeterministicClimateScenarioProvider::kTickIntervalMs;
    ClimateRuntimeDecision decision{};
    const ClimateLoopResult result = application.tick(timestamp, decision);

    assert(result.io_status == ClimateLoopIoStatus::Ok);
    assert(result.runtime_status == ClimateRuntimeStatus::Ok);
    assert(result.input_sampled);
    assert(result.command_applied);
    assert(!result.fail_safe_attempted);
    assert(!application.actuatorFaultLatched());
    assert(driver.calls == (tick + 1U) * kRoleCount);
    assert(driver.last_timestamp == timestamp);
    assert(sameRequest(driver.lastRequest(), decision.applied));
    assert(samePrevious(application.previousApplied(), decision.applied));

    if (tick > 0U && !sameRequest(previous_request, decision.applied)) {
      saw_output_change = true;
    }
    previous_request = decision.applied;

    const std::uint32_t phase = DeterministicClimateScenarioProvider::phaseTick(timestamp);
    if (phase == 60U) {
      assert(near(decision.applied.cooler, 0.0F));
    } else if (phase == 120U) {
      assert(near(decision.applied.humidifier, 0.0F));
      assert(near(decision.applied.co2_doser, 0.0F));
    } else if (phase == 180U) {
      assert(near(decision.applied.heater, 0.0F));
      assert(near(decision.applied.dehumidifier, 0.0F));
    }
  }

  assert(saw_output_change);
  assert(driver.calls == kTicks * kRoleCount);
}

} // namespace

int main() {
  testTimestampDeterminismAndPeriodicity();
  testScenarioTransitionsMeasurementsTargetsScheduleAndCapabilities();
  testLongRunThroughFullApplicationPath();
  return 0;
}
