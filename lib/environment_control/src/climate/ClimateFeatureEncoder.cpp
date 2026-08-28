#include "ClimateFeatureEncoder.h"
#include "ClimateMath.h"
#include <algorithm>
#include <cmath>
#include <cstdint>
namespace growbox::climate {
namespace {
struct MeasurementStatus {
  bool valid = false, fresh = false, usable = false;
};
MeasurementStatus statusOf(const MeasuredValue& m, std::uint64_t timeout) noexcept {
  const bool valid = m.valid && std::isfinite(m.value);
  const bool fresh = m.age_ms <= timeout;
  return {valid, fresh, valid && fresh};
}
class Writer {
public:
  Writer(ClimateFeatureVector& v, ClimateEncoderReport& r) : v_(v), r_(r) {}
  void write(contract::FeatureIndex f, float raw, bool substitute = false) noexcept {
    const auto i = contract::index(f);
    if (substitute || !std::isfinite(raw)) {
      raw = contract::kFeatureDefaults[i];
      r_.substituted_feature_mask |= std::uint64_t{1U} << i;
    }
    const float lo = contract::kFeatureMinimums[i], hi = contract::kFeatureMaximums[i],
                clipped = std::clamp(raw, lo, hi);
    if (clipped != raw) {
      r_.clamped_feature_mask |= std::uint64_t{1U} << i;
    }
    const float span = hi - lo;
    v_.values[i] = span > 0.0F ? (clipped - lo) / span : 0.0F;
  }
  void flag(contract::FeatureIndex f, bool value) noexcept {
    write(f, value ? 1.0F : 0.0F);
  }

private:
  ClimateFeatureVector& v_;
  ClimateEncoderReport& r_;
};
} // namespace
ClimateFeatureVector ClimateFeatureEncoder::encode(const ClimateControllerInput& input,
                                                   ClimateEncoderReport* report) noexcept {
  ClimateFeatureVector vector{};
  ClimateEncoderReport local{};
  Writer w(vector, local);
  const auto& m = input.state.measurements;
  const auto t = statusOf(m.air_temperature_c, input.sensor_timeout_ms),
             rh = statusOf(m.relative_humidity_pct, input.sensor_timeout_ms),
             co2 = statusOf(m.co2_ppm, input.sensor_timeout_ms),
             ot = statusOf(m.outside_temperature_c, input.sensor_timeout_ms),
             oh = statusOf(m.outside_humidity_pct, input.sensor_timeout_ms);
  w.write(contract::FeatureIndex::AirTemperatureC, m.air_temperature_c.value, !t.usable);
  w.write(contract::FeatureIndex::RelativeHumidityPct, m.relative_humidity_pct.value, !rh.usable);
  w.write(contract::FeatureIndex::Co2Ppm, m.co2_ppm.value, !co2.usable);
  w.write(contract::FeatureIndex::OutsideTemperatureC, m.outside_temperature_c.value, !ot.usable);
  w.write(contract::FeatureIndex::OutsideHumidityPct, m.outside_humidity_pct.value, !oh.usable);
  w.flag(contract::FeatureIndex::AirTemperatureValid, t.valid);
  w.flag(contract::FeatureIndex::AirTemperatureFresh, t.fresh);
  w.flag(contract::FeatureIndex::RelativeHumidityValid, rh.valid);
  w.flag(contract::FeatureIndex::RelativeHumidityFresh, rh.fresh);
  w.flag(contract::FeatureIndex::Co2Valid, co2.valid);
  w.flag(contract::FeatureIndex::Co2Fresh, co2.fresh);
  w.flag(contract::FeatureIndex::OutsideTemperatureValid, ot.valid);
  w.flag(contract::FeatureIndex::OutsideTemperatureFresh, ot.fresh);
  w.flag(contract::FeatureIndex::OutsideHumidityValid, oh.valid);
  w.flag(contract::FeatureIndex::OutsideHumidityFresh, oh.fresh);
  const bool vpd_ok = t.usable && rh.usable;
  w.write(contract::FeatureIndex::AirVpdKpa,
          vpd_ok ? airVpdKpa(m.air_temperature_c.value, m.relative_humidity_pct.value) : 0.0F,
          !vpd_ok);
  w.write(contract::FeatureIndex::HumidityControlMode,
          input.humidity_control_mode == HumidityControlMode::Vpd ? 1.0F : 0.0F);
  w.write(contract::FeatureIndex::TargetAirTemperatureC, input.targets.air_temperature_c);
  w.write(contract::FeatureIndex::TargetRelativeHumidityPct, input.targets.relative_humidity_pct);
  w.write(contract::FeatureIndex::TargetAirVpdKpa, input.targets.air_vpd_kpa);
  w.flag(contract::FeatureIndex::Co2ControlEnabled, input.targets.co2_enabled);
  w.write(contract::FeatureIndex::TargetCo2Ppm, input.targets.co2_ppm);
  w.write(contract::FeatureIndex::LightLevel, input.schedule.light_level);
  const auto& tr = input.state.trends;
  w.write(contract::FeatureIndex::TemperatureRateCMin, tr.temperature.rate_per_min,
          !t.usable || !tr.temperature.available);
  w.write(contract::FeatureIndex::HumidityRatePctMin, tr.humidity.rate_per_min,
          !rh.usable || !tr.humidity.available);
  w.write(contract::FeatureIndex::Co2RatePpmMin, tr.co2.rate_per_min,
          !co2.usable || !tr.co2.available);
  w.write(contract::FeatureIndex::PreviousHeater, input.previous.heater);
  w.write(contract::FeatureIndex::PreviousCooler, input.previous.cooler);
  w.write(contract::FeatureIndex::PreviousExhaustFan, input.previous.exhaust_fan);
  w.write(contract::FeatureIndex::PreviousHumidifier, input.previous.humidifier);
  w.write(contract::FeatureIndex::PreviousDehumidifier, input.previous.dehumidifier);
  w.write(contract::FeatureIndex::PreviousCo2Doser, input.previous.co2_doser);
  w.write(contract::FeatureIndex::EstimatedEffectiveHeater, input.estimated_effective.heater);
  w.write(contract::FeatureIndex::EstimatedEffectiveCooler, input.estimated_effective.cooler);
  w.write(contract::FeatureIndex::EstimatedEffectiveExhaustFan,
          input.estimated_effective.exhaust_fan);
  w.write(contract::FeatureIndex::EstimatedEffectiveHumidifier,
          input.estimated_effective.humidifier);
  w.write(contract::FeatureIndex::EstimatedEffectiveDehumidifier,
          input.estimated_effective.dehumidifier);
  w.write(contract::FeatureIndex::EstimatedEffectiveCo2Doser, input.estimated_effective.co2_doser);
  w.flag(contract::FeatureIndex::HeaterAvailable, input.capabilities.heater);
  w.flag(contract::FeatureIndex::CoolerAvailable, input.capabilities.cooler);
  w.flag(contract::FeatureIndex::ExhaustFanAvailable, input.capabilities.exhaust_fan);
  w.flag(contract::FeatureIndex::HumidifierAvailable, input.capabilities.humidifier);
  w.flag(contract::FeatureIndex::DehumidifierAvailable, input.capabilities.dehumidifier);
  w.flag(contract::FeatureIndex::Co2DoserAvailable, input.capabilities.co2_doser);
  if (report) {
    *report = local;
  }
  return vector;
}
} // namespace growbox::climate
