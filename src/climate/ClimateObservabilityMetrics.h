#pragma once

namespace growbox::app::climate_io {

struct AirMoistureMetrics {
  float dew_point_c{0.0F};
  float absolute_humidity_g_m3{0.0F};
  float air_vpd_kpa{0.0F};
  bool valid{false};
};

struct VentilationGradientMetrics {
  float temperature_delta_c{0.0F};
  float absolute_humidity_delta_g_m3{0.0F};
  bool valid{false};
};

AirMoistureMetrics calculateAirMoistureMetrics(float temperature_c,
                                               float relative_humidity_pct) noexcept;

VentilationGradientMetrics calculateVentilationGradients(
    float inside_temperature_c, float inside_relative_humidity_pct,
    float intake_temperature_c, float intake_relative_humidity_pct) noexcept;

} // namespace growbox::app::climate_io
