#include "climate/runtime/Stage27RuntimeAdapters.h"

namespace growbox::app::climate_io::runtime {

bool LockedFakeRoleDriver::apply(ClimateActuatorRole, float,
                                 std::uint64_t) noexcept {
  return true;
}

Stage27InsideSource::Stage27InsideSource(native::BleClimateScanner& ble,
                                         native::Scd41InsideSource& scd41) noexcept
    : ble_(ble), scd41_(scd41) {}

bool Stage27InsideSource::sample(std::uint64_t monotonic_ms,
                                 InsideEnvironmentSnapshot& output) noexcept {
  output = {};

  native::BleClimateReading tp357{};
  const bool tp357_sampled = ble_.sampleTp357(monotonic_ms, tp357);
  if (tp357_sampled) {
    output.air_temperature_c = {tp357.temperature_c, true, tp357.age_ms};
    output.relative_humidity_pct = {tp357.relative_humidity_pct, true,
                                    tp357.age_ms};
  }

  InsideEnvironmentSnapshot scd41{};
  if (scd41_.sample(monotonic_ms, scd41) && scd41.co2_ppm.valid) {
    output.co2_ppm = scd41.co2_ppm;
  }

  return tp357_sampled || output.co2_ppm.valid;
}

Stage27NearbySource::Stage27NearbySource(native::BleClimateScanner& ble) noexcept
    : ble_(ble) {}

bool Stage27NearbySource::sample(std::uint64_t monotonic_ms,
                                 OutsideEnvironmentSnapshot& output) noexcept {
  output = {};
  native::BleClimateReading xiaomi{};
  if (!ble_.sampleXiaomi(monotonic_ms, xiaomi)) {
    return false;
  }
  output.air_temperature_c = {xiaomi.temperature_c, true, xiaomi.age_ms};
  output.relative_humidity_pct = {xiaomi.relative_humidity_pct, true,
                                  xiaomi.age_ms};
  return true;
}

bool FixedStage27ScheduleConfigSource::resolve(
    std::uint64_t, const ClimateWallClockSnapshot& clock,
    ClimateScheduleConfigSnapshot& output) noexcept {
  if (!clock.valid) {
    return false;
  }

  output = {};
  output.sensor_timeout_ms = ::growbox::climate::kDefaultSensorTimeoutMs;
  output.humidity_control_mode = ::growbox::climate::HumidityControlMode::Rh;
  output.capabilities.heater = true;
  output.capabilities.cooler = true;
  output.capabilities.exhaust_fan = true;
  output.capabilities.humidifier = true;
  output.capabilities.dehumidifier = true;
  output.capabilities.co2_doser = true;

  const std::uint8_t hour =
      static_cast<std::uint8_t>((clock.unix_time_s / 3600U) % 24U);
  const bool day = hour >= 6U && hour < 22U;
  output.targets.air_temperature_c = day ? 24.5F : 21.5F;
  output.targets.relative_humidity_pct = day ? 58.0F : 65.0F;
  output.targets.air_vpd_kpa = day ? 1.2F : 0.9F;
  output.targets.co2_enabled = day;
  output.targets.co2_ppm = day ? 950.0F : 450.0F;
  output.schedule.light_level = day ? 1.0F : 0.0F;
  return true;
}

::growbox::climate::ClimateRuntimeConfig defaultRuntimeConfig() noexcept {
  ::growbox::climate::ClimateRuntimeConfig config{};
  config.mode = ::growbox::climate::ClimatePolicyMode::Rule;
  config.sensor_timeout_ms = ::growbox::climate::kDefaultSensorTimeoutMs;
  config.timestep_s = 1.0F;
  return config;
}

}  // namespace growbox::app::climate_io::runtime
