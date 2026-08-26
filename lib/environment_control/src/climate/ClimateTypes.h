#pragma once
#include "ClimateContract.h"
#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>
namespace growbox::climate {
inline constexpr std::uint64_t kUnknownMeasurementAgeMs = std::numeric_limits<std::uint64_t>::max();
inline constexpr std::uint64_t kDefaultSensorTimeoutMs = 30'000ULL;
namespace detail { constexpr float featureDefault(contract::FeatureIndex f) noexcept { return contract::kFeatureDefaults[contract::index(f)]; } }
struct MeasuredValue { float value = 0.0F; bool valid = false; std::uint64_t age_ms = kUnknownMeasurementAgeMs; };
struct ClimateMeasurements {
  MeasuredValue air_temperature_c{detail::featureDefault(contract::FeatureIndex::AirTemperatureC), false, kUnknownMeasurementAgeMs};
  MeasuredValue relative_humidity_pct{detail::featureDefault(contract::FeatureIndex::RelativeHumidityPct), false, kUnknownMeasurementAgeMs};
  MeasuredValue co2_ppm{detail::featureDefault(contract::FeatureIndex::Co2Ppm), false, kUnknownMeasurementAgeMs};
  MeasuredValue outside_temperature_c{detail::featureDefault(contract::FeatureIndex::OutsideTemperatureC), false, kUnknownMeasurementAgeMs};
  MeasuredValue outside_humidity_pct{detail::featureDefault(contract::FeatureIndex::OutsideHumidityPct), false, kUnknownMeasurementAgeMs};
};
struct TrendValue { float rate_per_min = 0.0F; bool available = false; };
struct ClimateTrends { TrendValue temperature{}; TrendValue humidity{}; TrendValue co2{}; };
struct ClimateState { ClimateMeasurements measurements{}; ClimateTrends trends{}; };
enum class HumidityControlMode : std::uint8_t { Rh = 0U, Vpd = 1U };
struct ClimateTargets {
  float air_temperature_c = detail::featureDefault(contract::FeatureIndex::TargetAirTemperatureC);
  float relative_humidity_pct = detail::featureDefault(contract::FeatureIndex::TargetRelativeHumidityPct);
  float air_vpd_kpa = detail::featureDefault(contract::FeatureIndex::TargetAirVpdKpa);
  bool co2_enabled = false;
  float co2_ppm = detail::featureDefault(contract::FeatureIndex::TargetCo2Ppm);
};
struct ClimateSchedule { float light_level = detail::featureDefault(contract::FeatureIndex::LightLevel); };
struct PreviousClimateActions { float heater=0.0F, cooler=0.0F, exhaust_fan=0.0F, humidifier=0.0F, dehumidifier=0.0F, co2_doser=0.0F; };
struct ClimateCapabilities { bool heater=false, cooler=false, exhaust_fan=false, humidifier=false, dehumidifier=false, co2_doser=false; };
struct ClimateControllerInput { ClimateState state{}; HumidityControlMode humidity_control_mode=HumidityControlMode::Rh; ClimateTargets targets{}; ClimateSchedule schedule{}; PreviousClimateActions previous{}; ClimateCapabilities capabilities{}; std::uint64_t sensor_timeout_ms=kDefaultSensorTimeoutMs; };
struct ClimateFeatureVector { std::array<float, contract::kFeatureCount> values{}; };
struct ClimateEncoderReport {
  std::uint64_t substituted_feature_mask=0U, clamped_feature_mask=0U;
  bool substituted(contract::FeatureIndex f) const noexcept { return (substituted_feature_mask & (std::uint64_t{1U} << contract::index(f))) != 0U; }
  bool clamped(contract::FeatureIndex f) const noexcept { return (clamped_feature_mask & (std::uint64_t{1U} << contract::index(f))) != 0U; }
};
struct ClimatePolicyRequest { float heater=0.0F, cooler=0.0F, exhaust_fan=0.0F, humidifier=0.0F, dehumidifier=0.0F, co2_doser=0.0F; };
static_assert(contract::kFeatureCount <= 64U, "Climate encoder masks require at most 64 features");
static_assert(contract::kOutputCount == 6U, "Climate MVP policy request implements six ML outputs");
}  // namespace growbox::climate
