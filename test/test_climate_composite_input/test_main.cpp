#include "climate/ClimateApplication.h"
#include "climate/ClimateCompositeInput.h"

#include <cassert>
#include <cmath>
#include <cstddef>
#include <cstdint>

using namespace growbox::app::climate_io;
using namespace growbox::climate;

namespace {

bool near(float left, float right, float tolerance = 1.0e-5F) {
  return std::fabs(left - right) <= tolerance;
}

bool off(const ClimatePolicyRequest& request) {
  return near(request.heater, 0.0F) && near(request.cooler, 0.0F) &&
         near(request.exhaust_fan, 0.0F) && near(request.humidifier, 0.0F) &&
         near(request.dehumidifier, 0.0F) && near(request.co2_doser, 0.0F);
}

class FakeInsideSource final : public InsideEnvironmentSource {
public:
  bool sample(std::uint64_t monotonic_ms, InsideEnvironmentSnapshot& output) noexcept override {
    ++calls;
    last_monotonic_ms = monotonic_ms;
    if (!available) {
      return false;
    }
    output.air_temperature_c = {temperature_c, true, age_ms};
    output.relative_humidity_pct = {humidity_pct, true, age_ms};
    output.co2_ppm = {co2_ppm, true, age_ms};
    return true;
  }

  bool available = true;
  float temperature_c = 20.0F;
  float humidity_pct = 58.0F;
  float co2_ppm = 500.0F;
  std::uint64_t age_ms = 7U;
  std::size_t calls = 0U;
  std::uint64_t last_monotonic_ms = 0U;
};

class FakeOutsideSource final : public OutsideEnvironmentSource {
public:
  bool sample(std::uint64_t monotonic_ms, OutsideEnvironmentSnapshot& output) noexcept override {
    ++calls;
    last_monotonic_ms = monotonic_ms;
    if (!available) {
      return false;
    }
    output.air_temperature_c = {temperature_c, true, age_ms};
    output.relative_humidity_pct = {humidity_pct, true, age_ms};
    return true;
  }

  bool available = true;
  float temperature_c = 14.0F;
  float humidity_pct = 48.0F;
  std::uint64_t age_ms = 9U;
  std::size_t calls = 0U;
  std::uint64_t last_monotonic_ms = 0U;
};

class FakeClockSource final : public ClimateClockSource {
public:
  bool sample(std::uint64_t monotonic_ms, ClimateWallClockSnapshot& output) noexcept override {
    ++calls;
    last_monotonic_ms = monotonic_ms;
    if (!available) {
      return false;
    }
    output.valid = valid;
    output.unix_time_s = unix_time_s;
    return true;
  }

  bool available = true;
  bool valid = true;
  std::uint64_t unix_time_s = 3'600U;
  std::size_t calls = 0U;
  std::uint64_t last_monotonic_ms = 0U;
};

class FakeScheduleConfigSource final : public ClimateScheduleConfigSource {
public:
  bool resolve(std::uint64_t monotonic_ms, const ClimateWallClockSnapshot& clock,
               ClimateScheduleConfigSnapshot& output) noexcept override {
    ++calls;
    last_monotonic_ms = monotonic_ms;
    last_clock = clock;
    if (!available) {
      return false;
    }

    const std::uint64_t seconds_in_day = clock.unix_time_s % 86'400U;
    const bool day = seconds_in_day >= 6U * 3'600U && seconds_in_day < 18U * 3'600U;
    output.humidity_control_mode = HumidityControlMode::Rh;
    output.targets.air_temperature_c = day ? 24.0F : 21.0F;
    output.targets.relative_humidity_pct = day ? 60.0F : 65.0F;
    output.targets.air_vpd_kpa = day ? 1.2F : 0.9F;
    output.targets.co2_enabled = day;
    output.targets.co2_ppm = day ? 950.0F : 450.0F;
    output.schedule.light_level = day ? 1.0F : 0.0F;
    output.capabilities.heater = heater_available;
    output.capabilities.cooler = true;
    output.capabilities.exhaust_fan = true;
    output.capabilities.humidifier = true;
    output.capabilities.dehumidifier = true;
    output.capabilities.co2_doser = co2_doser_available;
    output.sensor_timeout_ms = sensor_timeout_ms;
    return true;
  }

  bool available = true;
  bool heater_available = true;
  bool co2_doser_available = true;
  std::uint64_t sensor_timeout_ms = 30'000U;
  std::size_t calls = 0U;
  std::uint64_t last_monotonic_ms = 0U;
  ClimateWallClockSnapshot last_clock{};
};

class AcceptAllRoleDriver final : public ClimateRoleDriver {
public:
  bool apply(ClimateActuatorRole, float, std::uint64_t) noexcept override {
    ++calls;
    return true;
  }

  std::size_t calls = 0U;
};

ClimateRuntimeConfig ruleConfig() {
  ClimateRuntimeConfig config{};
  config.mode = ClimatePolicyMode::Rule;
  config.sensor_timeout_ms = kDefaultSensorTimeoutMs;
  config.timestep_s = 1.0F;
  return config;
}

void testNominalAggregationUsesEachComponentOnce() {
  FakeInsideSource inside;
  FakeOutsideSource outside;
  FakeClockSource clock;
  FakeScheduleConfigSource schedule_config;
  clock.unix_time_s = 12U * 3'600U;
  CompositeClimateSnapshotProvider provider(inside, outside, clock, schedule_config);

  ClimateInputSnapshot snapshot{};
  assert(provider.snapshot(42'000U, snapshot));
  assert(inside.calls == 1U);
  assert(outside.calls == 1U);
  assert(clock.calls == 1U);
  assert(schedule_config.calls == 1U);
  assert(inside.last_monotonic_ms == 42'000U);
  assert(outside.last_monotonic_ms == 42'000U);
  assert(clock.last_monotonic_ms == 42'000U);
  assert(schedule_config.last_monotonic_ms == 42'000U);
  assert(schedule_config.last_clock.valid);
  assert(schedule_config.last_clock.unix_time_s == clock.unix_time_s);

  assert(near(snapshot.measurements.air_temperature_c.value, 20.0F));
  assert(snapshot.measurements.air_temperature_c.valid);
  assert(snapshot.measurements.air_temperature_c.age_ms == 7U);
  assert(near(snapshot.measurements.outside_temperature_c.value, 14.0F));
  assert(snapshot.measurements.outside_temperature_c.age_ms == 9U);
  assert(near(snapshot.targets.air_temperature_c, 24.0F));
  assert(snapshot.targets.co2_enabled);
  assert(near(snapshot.schedule.light_level, 1.0F));
  assert(snapshot.capabilities.heater);
  assert(snapshot.sensor_timeout_ms == 30'000U);
}

void testSensorComponentUnavailabilityDegradesToInvalidMeasurements() {
  FakeInsideSource inside;
  FakeOutsideSource outside;
  FakeClockSource clock;
  FakeScheduleConfigSource schedule_config;
  clock.unix_time_s = 12U * 3'600U;
  CompositeClimateSnapshotProvider provider(inside, outside, clock, schedule_config);

  inside.available = false;
  ClimateInputSnapshot missing_inside{};
  assert(provider.snapshot(1'000U, missing_inside));
  assert(!missing_inside.measurements.air_temperature_c.valid);
  assert(!missing_inside.measurements.relative_humidity_pct.valid);
  assert(!missing_inside.measurements.co2_ppm.valid);
  assert(missing_inside.measurements.outside_temperature_c.valid);
  assert(near(missing_inside.targets.air_temperature_c, 24.0F));

  inside.available = true;
  outside.available = false;
  ClimateInputSnapshot missing_outside{};
  assert(provider.snapshot(2'000U, missing_outside));
  assert(missing_outside.measurements.air_temperature_c.valid);
  assert(!missing_outside.measurements.outside_temperature_c.valid);
  assert(!missing_outside.measurements.outside_humidity_pct.valid);
}

void testClockAndScheduleConfigAreRequiredContext() {
  FakeInsideSource inside;
  FakeOutsideSource outside;
  FakeClockSource clock;
  FakeScheduleConfigSource schedule_config;
  CompositeClimateSnapshotProvider provider(inside, outside, clock, schedule_config);

  ClimateInputSnapshot snapshot{};
  clock.available = false;
  assert(!provider.snapshot(3'000U, snapshot));
  assert(clock.calls == 1U);
  assert(schedule_config.calls == 0U);
  assert(inside.calls == 0U);
  assert(outside.calls == 0U);

  clock.available = true;
  clock.valid = false;
  assert(!provider.snapshot(4'000U, snapshot));
  assert(schedule_config.calls == 0U);

  clock.valid = true;
  schedule_config.available = false;
  assert(!provider.snapshot(5'000U, snapshot));
  assert(schedule_config.calls == 1U);
  assert(inside.calls == 0U);
  assert(outside.calls == 0U);
}

void testCompositeProviderThroughClimateApplication() {
  FakeInsideSource inside;
  FakeOutsideSource outside;
  FakeClockSource clock;
  FakeScheduleConfigSource schedule_config;
  AcceptAllRoleDriver driver;
  CompositeClimateSnapshotProvider provider(inside, outside, clock, schedule_config);
  ClimateRuntimeController runtime(nullptr, ruleConfig());
  ClimateApplication application(runtime, provider, driver);

  clock.unix_time_s = 12U * 3'600U;
  ClimateRuntimeDecision nominal{};
  const ClimateLoopResult nominal_result = application.tick(10'000U, nominal);
  assert(nominal_result.io_status == ClimateLoopIoStatus::Ok);
  assert(nominal_result.input_sampled);
  assert(nominal_result.command_applied);
  assert(nominal.applied.heater > 0.0F);

  outside.available = false;
  ClimateRuntimeDecision no_outside{};
  const ClimateLoopResult no_outside_result = application.tick(11'000U, no_outside);
  assert(no_outside_result.io_status == ClimateLoopIoStatus::Ok);
  assert(no_outside_result.input_sampled);
  assert(no_outside.applied.heater > 0.0F);

  outside.available = true;
  inside.available = false;
  ClimateRuntimeDecision no_inside{};
  const ClimateLoopResult no_inside_result = application.tick(12'000U, no_inside);
  assert(no_inside_result.io_status == ClimateLoopIoStatus::Ok);
  assert(no_inside_result.input_sampled);
  assert(off(no_inside.applied));

  inside.available = true;
  clock.available = false;
  ClimateRuntimeDecision no_clock{};
  const ClimateLoopResult no_clock_result = application.tick(13'000U, no_clock);
  assert(no_clock_result.io_status == ClimateLoopIoStatus::InputUnavailable);
  assert(!no_clock_result.input_sampled);
  assert(off(no_clock.applied));

  clock.available = true;
  clock.unix_time_s = 2U * 3'600U;
  ClimateRuntimeDecision night{};
  const ClimateLoopResult night_result = application.tick(14'000U, night);
  assert(night_result.io_status == ClimateLoopIoStatus::Ok);
  assert(night_result.input_sampled);
  assert(night.applied.heater > 0.0F);
  assert(near(night.rule.raw.co2_doser, 0.0F));
  assert(driver.calls == 5U * 6U);
}

} // namespace

int main() {
  testNominalAggregationUsesEachComponentOnce();
  testSensorComponentUnavailabilityDegradesToInvalidMeasurements();
  testClockAndScheduleConfigAreRequiredContext();
  testCompositeProviderThroughClimateApplication();
  return 0;
}
