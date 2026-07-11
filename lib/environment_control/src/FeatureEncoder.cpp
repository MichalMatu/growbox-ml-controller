#include "FeatureEncoder.h"

#include <cmath>
#include <cstdint>

namespace growbox {
namespace control {
namespace {

using schema::FeatureIndex;

constexpr std::uint64_t featureBit(FeatureIndex feature) noexcept {
  return std::uint64_t{1U} << schema::index(feature);
}

float normalize(float value, FeatureIndex feature, EncoderReport& report) noexcept {
  const std::size_t position = schema::index(feature);
  const float minimum = schema::kFeatureMinimums[position];
  const float maximum = schema::kFeatureMaximums[position];
  float clamped = value;
  if (clamped < minimum) {
    clamped = minimum;
    report.clamped_feature_mask |= featureBit(feature);
  } else if (clamped > maximum) {
    clamped = maximum;
    report.clamped_feature_mask |= featureBit(feature);
  }
  return (clamped - minimum) / (maximum - minimum);
}

bool encodeFinite(float value, FeatureIndex feature, FeatureVector& output,
                  EncoderReport& report) noexcept {
  const std::size_t position = schema::index(feature);
  if (!std::isfinite(value)) {
    output.values[position] = normalize(schema::kFeatureDefaults[position], feature, report);
    report.substituted_feature_mask |= featureBit(feature);
    return false;
  }
  output.values[position] = normalize(value, feature, report);
  return true;
}

bool encodeSensor(float value, bool valid, FeatureIndex value_feature,
                  FeatureIndex validity_feature, FeatureVector& output,
                  EncoderReport& report) noexcept {
  const std::size_t value_position = schema::index(value_feature);
  if (!std::isfinite(value)) {
    output.values[value_position] =
        normalize(schema::kFeatureDefaults[value_position], value_feature, report);
    output.values[schema::index(validity_feature)] = 0.0f;
    report.substituted_feature_mask |= featureBit(value_feature);
    return false;
  }
  if (!valid) {
    output.values[value_position] =
        normalize(schema::kFeatureDefaults[value_position], value_feature, report);
    output.values[schema::index(validity_feature)] = 0.0f;
    report.substituted_feature_mask |= featureBit(value_feature);
    return true;
  }

  output.values[schema::index(validity_feature)] = 1.0f;
  return encodeFinite(value, value_feature, output, report);
}

void markSubstitutionIfNeeded(float supplied, float canonical, FeatureIndex feature,
                              EncoderReport& report) noexcept {
  if (supplied != canonical) {
    report.substituted_feature_mask |= featureBit(feature);
  }
}

} // namespace

EncoderStatus FeatureEncoder::encode(const ControllerInput& input, FeatureVector& output,
                                     EncoderReport& report) noexcept {
  output = FeatureVector{};
  report = EncoderReport{};
  bool finite = true;

  finite &= encodeSensor(input.sensors.air_temperature_c, input.validity.air_temperature,
                         FeatureIndex::AirTemperatureC, FeatureIndex::AirTemperatureValid, output,
                         report);
  finite &=
      encodeSensor(input.sensors.air_humidity_pct, input.validity.air_humidity,
                   FeatureIndex::AirHumidityPct, FeatureIndex::AirHumidityValid, output, report);
  finite &= encodeSensor(input.sensors.co2_ppm, input.validity.co2, FeatureIndex::Co2Ppm,
                         FeatureIndex::Co2Valid, output, report);
  finite &=
      encodeSensor(input.sensors.soil_moisture_pct, input.validity.soil_moisture,
                   FeatureIndex::SoilMoisturePct, FeatureIndex::SoilMoistureValid, output, report);
  finite &= encodeSensor(input.sensors.outside_temperature_c, input.validity.outside_temperature,
                         FeatureIndex::OutsideTemperatureC, FeatureIndex::OutsideTemperatureValid,
                         output, report);
  finite &= encodeSensor(input.sensors.outside_humidity_pct, input.validity.outside_humidity,
                         FeatureIndex::OutsideHumidityPct, FeatureIndex::OutsideHumidityValid,
                         output, report);

  finite &= encodeFinite(input.environment.growbox_volume_m3, FeatureIndex::GrowboxVolumeM3, output,
                         report);
  finite &= encodeFinite(input.environment.thermal_mass_j_per_k, FeatureIndex::ThermalMassJPerK,
                         output, report);
  finite &= encodeFinite(input.environment.heat_loss_w_per_k, FeatureIndex::HeatLossWPerK, output,
                         report);
  finite &= encodeFinite(input.environment.air_leak_rate_ach, FeatureIndex::AirLeakRateAch, output,
                         report);
  finite &= encodeFinite(input.cultivation.pot_volume_l, FeatureIndex::PotVolumeL, output, report);
  finite &= encodeFinite(input.cultivation.substrate_water_capacity_ml,
                         FeatureIndex::SubstrateWaterCapacityMl, output, report);
  finite &= encodeFinite(input.cultivation.transpiration_factor, FeatureIndex::TranspirationFactor,
                         output, report);

  output.values[schema::index(FeatureIndex::HeaterAvailable)] =
      input.actuators.heater.available ? 1.0f : 0.0f;
  const float heater_power =
      input.actuators.heater.available ? input.actuators.heater.max_power_w : 0.0f;
  const float heater_efficiency = input.actuators.heater.efficiency;
  const float heater_control = static_cast<float>(input.actuators.heater.control_type);
  if (!input.actuators.heater.available) {
    markSubstitutionIfNeeded(input.actuators.heater.max_power_w, heater_power,
                             FeatureIndex::HeaterMaxPowerW, report);
  }
  finite &= encodeFinite(heater_power, FeatureIndex::HeaterMaxPowerW, output, report);
  finite &= encodeFinite(heater_efficiency, FeatureIndex::HeaterEfficiency, output, report);
  finite &= encodeFinite(heater_control, FeatureIndex::HeaterControlType, output, report);

  output.values[schema::index(FeatureIndex::FanAvailable)] =
      input.actuators.fan.available ? 1.0f : 0.0f;
  const float fan_airflow =
      input.actuators.fan.available ? input.actuators.fan.max_airflow_m3_h : 0.0f;
  const float fan_minimum = input.actuators.fan.minimum_command;
  if (!input.actuators.fan.available) {
    markSubstitutionIfNeeded(input.actuators.fan.max_airflow_m3_h, fan_airflow,
                             FeatureIndex::FanMaxAirflowM3H, report);
  }
  finite &= encodeFinite(fan_airflow, FeatureIndex::FanMaxAirflowM3H, output, report);
  finite &= encodeFinite(fan_minimum, FeatureIndex::FanMinimumCommand, output, report);

  output.values[schema::index(FeatureIndex::HumidifierAvailable)] =
      input.actuators.humidifier.available ? 1.0f : 0.0f;
  const float humidifier_output =
      input.actuators.humidifier.available ? input.actuators.humidifier.max_output_g_h : 0.0f;
  if (!input.actuators.humidifier.available) {
    markSubstitutionIfNeeded(input.actuators.humidifier.max_output_g_h, humidifier_output,
                             FeatureIndex::HumidifierMaxOutputGH, report);
  }
  finite &= encodeFinite(humidifier_output, FeatureIndex::HumidifierMaxOutputGH, output, report);

  output.values[schema::index(FeatureIndex::IrrigationAvailable)] =
      input.actuators.irrigation_pump.available ? 1.0f : 0.0f;
  const float pump_flow =
      input.actuators.irrigation_pump.available ? input.actuators.irrigation_pump.flow_ml_s : 0.0f;
  const float pump_pulse = input.actuators.irrigation_pump.available
                               ? input.actuators.irrigation_pump.maximum_pulse_s
                               : 0.0f;
  const float pump_interval = input.actuators.irrigation_pump.minimum_interval_s;
  if (!input.actuators.irrigation_pump.available) {
    markSubstitutionIfNeeded(input.actuators.irrigation_pump.flow_ml_s, pump_flow,
                             FeatureIndex::IrrigationFlowMlS, report);
    markSubstitutionIfNeeded(input.actuators.irrigation_pump.maximum_pulse_s, pump_pulse,
                             FeatureIndex::IrrigationMaximumPulseS, report);
  }
  finite &= encodeFinite(pump_flow, FeatureIndex::IrrigationFlowMlS, output, report);
  finite &= encodeFinite(pump_pulse, FeatureIndex::IrrigationMaximumPulseS, output, report);
  finite &= encodeFinite(pump_interval, FeatureIndex::IrrigationMinimumIntervalS, output, report);

  finite &= encodeFinite(input.targets.air_temperature_c, FeatureIndex::TargetAirTemperatureC,
                         output, report);
  finite &= encodeFinite(input.targets.air_humidity_pct, FeatureIndex::TargetAirHumidityPct, output,
                         report);
  finite &= encodeFinite(input.targets.co2_ppm, FeatureIndex::TargetCo2Ppm, output, report);
  finite &= encodeFinite(input.targets.soil_moisture_pct, FeatureIndex::TargetSoilMoisturePct,
                         output, report);
  finite &= encodeFinite(input.previous.heater, FeatureIndex::PreviousHeater, output, report);
  finite &= encodeFinite(input.previous.fan, FeatureIndex::PreviousFan, output, report);
  finite &=
      encodeFinite(input.previous.humidifier, FeatureIndex::PreviousHumidifier, output, report);
  finite &=
      encodeFinite(input.previous.irrigation, FeatureIndex::PreviousIrrigation, output, report);

  return finite ? EncoderStatus::Ok : EncoderStatus::NonFiniteInput;
}

} // namespace control
} // namespace growbox
