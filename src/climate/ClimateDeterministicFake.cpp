#include "climate/ClimateDeterministicFake.h"

namespace growbox::app::climate_io {
namespace {

constexpr std::uint32_t kQuarterTicks = DeterministicClimateScenarioProvider::kPeriodTicks / 4U;

float lerp(float start, float end, float fraction) noexcept {
  return start + ((end - start) * fraction);
}

float quarterFraction(std::uint32_t phase_tick) noexcept {
  const std::uint32_t within = phase_tick % kQuarterTicks;
  return static_cast<float>(within) / static_cast<float>(kQuarterTicks - 1U);
}

void enableAll(ClimateInputSnapshot& output) noexcept {
  output.capabilities.heater = true;
  output.capabilities.cooler = true;
  output.capabilities.exhaust_fan = true;
  output.capabilities.humidifier = true;
  output.capabilities.dehumidifier = true;
  output.capabilities.co2_doser = true;
}

void setDayTargets(ClimateInputSnapshot& output) noexcept {
  output.targets.air_temperature_c = 24.5F;
  output.targets.relative_humidity_pct = 58.0F;
  output.targets.air_vpd_kpa = 1.2F;
  output.targets.co2_enabled = true;
  output.targets.co2_ppm = 950.0F;
  output.schedule.light_level = 1.0F;
}

void setNightTargets(ClimateInputSnapshot& output) noexcept {
  output.targets.air_temperature_c = 21.5F;
  output.targets.relative_humidity_pct = 65.0F;
  output.targets.air_vpd_kpa = 0.9F;
  output.targets.co2_enabled = false;
  output.targets.co2_ppm = 450.0F;
  output.schedule.light_level = 0.0F;
}

} // namespace

std::uint32_t DeterministicClimateScenarioProvider::phaseTick(std::uint64_t monotonic_ms) noexcept {
  return static_cast<std::uint32_t>((monotonic_ms / kTickIntervalMs) % kPeriodTicks);
}

bool DeterministicClimateScenarioProvider::snapshot(std::uint64_t monotonic_ms,
                                                    ClimateInputSnapshot& output) noexcept {
  output = {};
  output.sensor_timeout_ms = ::growbox::climate::kDefaultSensorTimeoutMs;
  enableAll(output);

  const std::uint32_t phase_tick = phaseTick(monotonic_ms);
  const std::uint32_t quarter = phase_tick / kQuarterTicks;
  const float fraction = quarterFraction(phase_tick);

  float temperature = 20.0F;
  float humidity = 68.0F;
  float co2 = 450.0F;
  float outside_temperature = 14.0F;
  float outside_humidity = 72.0F;

  switch (quarter) {
  case 0U:
    temperature = lerp(20.0F, 24.0F, fraction);
    humidity = lerp(68.0F, 60.0F, fraction);
    co2 = lerp(450.0F, 900.0F, fraction);
    outside_temperature = lerp(14.0F, 16.0F, fraction);
    outside_humidity = lerp(72.0F, 65.0F, fraction);
    setDayTargets(output);
    break;
  case 1U:
    temperature = lerp(24.0F, 28.0F, fraction);
    humidity = lerp(60.0F, 50.0F, fraction);
    co2 = lerp(900.0F, 1'200.0F, fraction);
    outside_temperature = lerp(16.0F, 20.0F, fraction);
    outside_humidity = lerp(65.0F, 55.0F, fraction);
    output.capabilities.cooler = false;
    setDayTargets(output);
    break;
  case 2U:
    temperature = lerp(28.0F, 25.0F, fraction);
    humidity = lerp(50.0F, 60.0F, fraction);
    co2 = lerp(1'200.0F, 700.0F, fraction);
    outside_temperature = lerp(20.0F, 16.0F, fraction);
    outside_humidity = lerp(55.0F, 70.0F, fraction);
    output.capabilities.humidifier = false;
    output.capabilities.co2_doser = false;
    setNightTargets(output);
    break;
  default:
    temperature = lerp(25.0F, 20.0F, fraction);
    humidity = lerp(60.0F, 68.0F, fraction);
    co2 = lerp(700.0F, 450.0F, fraction);
    outside_temperature = lerp(16.0F, 14.0F, fraction);
    outside_humidity = lerp(70.0F, 72.0F, fraction);
    output.capabilities.heater = false;
    output.capabilities.dehumidifier = false;
    setNightTargets(output);
    break;
  }

  output.measurements.air_temperature_c = {temperature, true, 0U};
  output.measurements.relative_humidity_pct = {humidity, true, 0U};
  output.measurements.co2_ppm = {co2, true, 0U};
  output.measurements.outside_temperature_c = {outside_temperature, true, 0U};
  output.measurements.outside_humidity_pct = {outside_humidity, true, 0U};
  return true;
}

} // namespace growbox::app::climate_io
