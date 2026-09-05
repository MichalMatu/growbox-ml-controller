#include "climate/runtime/Stage27ScheduleProfile.h"

namespace growbox::app::climate_io::runtime {

bool buildMintScheduleProfile(std::uint8_t local_hour,
                              ClimateScheduleConfigSnapshot& output) noexcept {
  if (local_hour > 23U) {
    output = {};
    return false;
  }

  output = {};
  output.sensor_timeout_ms = ::growbox::climate::kDefaultSensorTimeoutMs;
  output.humidity_control_mode = ::growbox::climate::HumidityControlMode::Rh;
  output.capabilities.heater = false;
  output.capabilities.cooler = false;
  output.capabilities.exhaust_fan = true;
  output.capabilities.humidifier = true;
  output.capabilities.dehumidifier = false;
  output.capabilities.co2_doser = false;

  const bool day = local_hour >= 6U && local_hour < 22U;
  output.targets.air_temperature_c = day ? 24.5F : 21.5F;
  output.targets.relative_humidity_pct = day ? 58.0F : 65.0F;
  output.targets.air_vpd_kpa = day ? 1.2F : 0.9F;
  output.targets.co2_enabled = false;
  output.targets.co2_ppm = 0.0F;
  output.schedule.light_level = day ? 1.0F : 0.0F;
  return true;
}

} // namespace growbox::app::climate_io::runtime
