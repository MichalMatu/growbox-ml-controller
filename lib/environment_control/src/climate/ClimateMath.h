#pragma once
#include <algorithm>
#include <cmath>
namespace growbox::climate {
inline float saturationVapourPressureKpa(float temperature_c) noexcept {
  const float temperature = std::clamp(temperature_c, -40.0F, 80.0F);
  return 0.61094F * std::exp((17.625F * temperature) / (temperature + 243.04F));
}
inline float airVpdKpa(float temperature_c, float relative_humidity_pct) noexcept {
  const float humidity = std::clamp(relative_humidity_pct, 0.0F, 100.0F);
  return std::max(0.0F, saturationVapourPressureKpa(temperature_c) * (1.0F - humidity / 100.0F));
}
}  // namespace growbox::climate
