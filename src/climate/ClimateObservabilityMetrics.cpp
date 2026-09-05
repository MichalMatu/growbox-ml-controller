#include "climate/ClimateObservabilityMetrics.h"

#include <cmath>

namespace growbox::app::climate_io {
namespace {

constexpr float kMagnusA = 17.62F;
constexpr float kMagnusB = 243.12F;
constexpr float kAbsoluteHumidityScale = 216.7F;

bool validTemperatureRh(float temperature_c, float relative_humidity_pct) noexcept {
  return std::isfinite(temperature_c) && std::isfinite(relative_humidity_pct) &&
         temperature_c >= -40.0F && temperature_c <= 85.0F && relative_humidity_pct > 0.0F &&
         relative_humidity_pct <= 100.0F;
}

float saturationVaporPressureHpa(float temperature_c) noexcept {
  return 6.112F * std::exp((kMagnusA * temperature_c) / (kMagnusB + temperature_c));
}

} // namespace

AirMoistureMetrics calculateAirMoistureMetrics(float temperature_c,
                                               float relative_humidity_pct) noexcept {
  AirMoistureMetrics output{};
  if (!validTemperatureRh(temperature_c, relative_humidity_pct)) {
    return output;
  }

  const float saturation_hpa = saturationVaporPressureHpa(temperature_c);
  const float vapor_pressure_hpa = saturation_hpa * (relative_humidity_pct / 100.0F);
  const float gamma = std::log(relative_humidity_pct / 100.0F) +
                      (kMagnusA * temperature_c) / (kMagnusB + temperature_c);
  const float dew_point_c = (kMagnusB * gamma) / (kMagnusA - gamma);
  const float absolute_humidity_g_m3 =
      kAbsoluteHumidityScale * vapor_pressure_hpa / (273.15F + temperature_c);
  const float air_vpd_kpa = (saturation_hpa - vapor_pressure_hpa) / 10.0F;

  if (!std::isfinite(dew_point_c) || !std::isfinite(absolute_humidity_g_m3) ||
      !std::isfinite(air_vpd_kpa)) {
    return output;
  }

  output.dew_point_c = dew_point_c;
  output.absolute_humidity_g_m3 = absolute_humidity_g_m3;
  output.air_vpd_kpa = air_vpd_kpa;
  output.valid = true;
  return output;
}

VentilationGradientMetrics calculateVentilationGradients(
    float inside_temperature_c, float inside_relative_humidity_pct,
    float intake_temperature_c, float intake_relative_humidity_pct) noexcept {
  VentilationGradientMetrics output{};
  const AirMoistureMetrics inside =
      calculateAirMoistureMetrics(inside_temperature_c, inside_relative_humidity_pct);
  const AirMoistureMetrics intake =
      calculateAirMoistureMetrics(intake_temperature_c, intake_relative_humidity_pct);
  if (!inside.valid || !intake.valid) {
    return output;
  }

  output.temperature_delta_c = inside_temperature_c - intake_temperature_c;
  output.absolute_humidity_delta_g_m3 =
      inside.absolute_humidity_g_m3 - intake.absolute_humidity_g_m3;
  output.valid = true;
  return output;
}

} // namespace growbox::app::climate_io
