#include "FeatureEncoder.h"

#include <cmath>
#include <cstdint>

namespace growbox {
namespace control {
namespace {

using schema::FeatureIndex;

float normalize(float value, FeatureIndex feature, EncoderReport& report) noexcept {
  const std::size_t position = schema::index(feature);
  const float minimum = schema::kFeatureMinimums[position];
  const float maximum = schema::kFeatureMaximums[position];
  float clamped = value;
  if (clamped < minimum) {
    clamped = minimum;
    report.clamped_feature_mask.set(position);
  } else if (clamped > maximum) {
    clamped = maximum;
    report.clamped_feature_mask.set(position);
  }
  return (clamped - minimum) / (maximum - minimum);
}

bool encodeFinite(float value, FeatureIndex feature, FeatureVector& output,
                  EncoderReport& report) noexcept {
  const std::size_t position = schema::index(feature);
  if (!std::isfinite(value)) {
    output.values[position] = normalize(schema::kFeatureDefaults[position], feature, report);
    report.substituted_feature_mask.set(position);
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
    report.substituted_feature_mask.set(value_position);
    return false;
  }
  if (!valid) {
    output.values[value_position] =
        normalize(schema::kFeatureDefaults[value_position], value_feature, report);
    output.values[schema::index(validity_feature)] = 0.0f;
    report.substituted_feature_mask.set(value_position);
    return true;
  }

  output.values[schema::index(validity_feature)] = 1.0f;
  return encodeFinite(value, value_feature, output, report);
}

void markSubstitutionIfNeeded(float supplied, float canonical, FeatureIndex feature,
                              EncoderReport& report) noexcept {
  if (supplied != canonical) {
    report.substituted_feature_mask.set(schema::index(feature));
  }
}

struct ZoneFeatureMap {
  FeatureIndex available;
  FeatureIndex soil_moisture;
  FeatureIndex soil_temperature;
  FeatureIndex soil_moisture_valid;
  FeatureIndex soil_temperature_valid;
  FeatureIndex pot_volume;
  FeatureIndex water_capacity;
  FeatureIndex transpiration;
  FeatureIndex target_soil;
  FeatureIndex irrigation_available;
  FeatureIndex irrigation_flow;
  FeatureIndex irrigation_pulse;
  FeatureIndex irrigation_interval;
  FeatureIndex irrigation_control;
  FeatureIndex previous_irrigation;
};

constexpr std::array<ZoneFeatureMap, kMaxZones> kZoneFeatures{{
    {FeatureIndex::Zone1Available, FeatureIndex::SoilMoistureZone1Pct,
     FeatureIndex::SoilTemperatureZone1C, FeatureIndex::SoilMoistureZone1Valid,
     FeatureIndex::SoilTemperatureZone1Valid, FeatureIndex::Zone1PotVolumeL,
     FeatureIndex::Zone1SubstrateWaterCapacityMl, FeatureIndex::Zone1TranspirationFactor,
     FeatureIndex::Zone1TargetSoilMoisturePct, FeatureIndex::Zone1IrrigationAvailable,
     FeatureIndex::Zone1IrrigationFlowMlS, FeatureIndex::Zone1IrrigationMaximumPulseS,
     FeatureIndex::Zone1IrrigationMinimumIntervalS, FeatureIndex::Zone1IrrigationControlType,
     FeatureIndex::Zone1PreviousIrrigation},
    {FeatureIndex::Zone2Available, FeatureIndex::SoilMoistureZone2Pct,
     FeatureIndex::SoilTemperatureZone2C, FeatureIndex::SoilMoistureZone2Valid,
     FeatureIndex::SoilTemperatureZone2Valid, FeatureIndex::Zone2PotVolumeL,
     FeatureIndex::Zone2SubstrateWaterCapacityMl, FeatureIndex::Zone2TranspirationFactor,
     FeatureIndex::Zone2TargetSoilMoisturePct, FeatureIndex::Zone2IrrigationAvailable,
     FeatureIndex::Zone2IrrigationFlowMlS, FeatureIndex::Zone2IrrigationMaximumPulseS,
     FeatureIndex::Zone2IrrigationMinimumIntervalS, FeatureIndex::Zone2IrrigationControlType,
     FeatureIndex::Zone2PreviousIrrigation},
    {FeatureIndex::Zone3Available, FeatureIndex::SoilMoistureZone3Pct,
     FeatureIndex::SoilTemperatureZone3C, FeatureIndex::SoilMoistureZone3Valid,
     FeatureIndex::SoilTemperatureZone3Valid, FeatureIndex::Zone3PotVolumeL,
     FeatureIndex::Zone3SubstrateWaterCapacityMl, FeatureIndex::Zone3TranspirationFactor,
     FeatureIndex::Zone3TargetSoilMoisturePct, FeatureIndex::Zone3IrrigationAvailable,
     FeatureIndex::Zone3IrrigationFlowMlS, FeatureIndex::Zone3IrrigationMaximumPulseS,
     FeatureIndex::Zone3IrrigationMinimumIntervalS, FeatureIndex::Zone3IrrigationControlType,
     FeatureIndex::Zone3PreviousIrrigation},
    {FeatureIndex::Zone4Available, FeatureIndex::SoilMoistureZone4Pct,
     FeatureIndex::SoilTemperatureZone4C, FeatureIndex::SoilMoistureZone4Valid,
     FeatureIndex::SoilTemperatureZone4Valid, FeatureIndex::Zone4PotVolumeL,
     FeatureIndex::Zone4SubstrateWaterCapacityMl, FeatureIndex::Zone4TranspirationFactor,
     FeatureIndex::Zone4TargetSoilMoisturePct, FeatureIndex::Zone4IrrigationAvailable,
     FeatureIndex::Zone4IrrigationFlowMlS, FeatureIndex::Zone4IrrigationMaximumPulseS,
     FeatureIndex::Zone4IrrigationMinimumIntervalS, FeatureIndex::Zone4IrrigationControlType,
     FeatureIndex::Zone4PreviousIrrigation},
}};

bool encodeZone(const ZoneConfig& zone, const ZoneFeatureMap& features, FeatureVector& output,
                EncoderReport& report, bool& finite) noexcept {
  output.values[schema::index(features.available)] = zone.available ? 1.0f : 0.0f;
  finite &=
      encodeSensor(zone.sensors.soil_moisture_pct, zone.available && zone.validity.soil_moisture,
                   features.soil_moisture, features.soil_moisture_valid, output, report);
  finite &= encodeSensor(
      zone.sensors.soil_temperature_c, zone.available && zone.validity.soil_temperature,
      features.soil_temperature, features.soil_temperature_valid, output, report);

  finite &= encodeFinite(zone.cultivation.pot_volume_l, features.pot_volume, output, report);
  finite &= encodeFinite(zone.cultivation.substrate_water_capacity_ml, features.water_capacity,
                         output, report);
  finite &=
      encodeFinite(zone.cultivation.transpiration_factor, features.transpiration, output, report);
  finite &= encodeFinite(zone.target_soil_moisture_pct, features.target_soil, output, report);

  output.values[schema::index(features.irrigation_available)] =
      zone.irrigation.available ? 1.0f : 0.0f;
  const float flow = zone.irrigation.available ? zone.irrigation.flow_ml_s : 0.0f;
  const float pulse = zone.irrigation.available ? zone.irrigation.maximum_pulse_s : 0.0f;
  if (!zone.irrigation.available) {
    markSubstitutionIfNeeded(zone.irrigation.flow_ml_s, flow, features.irrigation_flow, report);
    markSubstitutionIfNeeded(zone.irrigation.maximum_pulse_s, pulse, features.irrigation_pulse,
                             report);
  }
  finite &= encodeFinite(flow, features.irrigation_flow, output, report);
  finite &= encodeFinite(pulse, features.irrigation_pulse, output, report);
  finite &= encodeFinite(zone.irrigation.minimum_interval_s, features.irrigation_interval, output,
                         report);
  finite &= encodeFinite(static_cast<float>(zone.irrigation.control_type),
                         features.irrigation_control, output, report);
  finite &= encodeFinite(zone.previous_irrigation, features.previous_irrigation, output, report);
  return finite;
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
  finite &= encodeSensor(input.sensors.nutrient_solution_temperature_c,
                         input.validity.nutrient_solution_temperature,
                         FeatureIndex::NutrientSolutionTemperatureC,
                         FeatureIndex::NutrientSolutionTemperatureValid, output, report);
  finite &= encodeSensor(input.sensors.outside_temperature_c, input.validity.outside_temperature,
                         FeatureIndex::OutsideTemperatureC, FeatureIndex::OutsideTemperatureValid,
                         output, report);
  finite &= encodeSensor(input.sensors.outside_humidity_pct, input.validity.outside_humidity,
                         FeatureIndex::OutsideHumidityPct, FeatureIndex::OutsideHumidityValid,
                         output, report);
  finite &=
      encodeSensor(input.sensors.outside_co2_ppm, input.validity.outside_co2,
                   FeatureIndex::OutsideCo2Ppm, FeatureIndex::OutsideCo2Valid, output, report);

  for (std::size_t zone_index = 0; zone_index < kMaxZones; ++zone_index) {
    finite = encodeZone(input.zones[zone_index], kZoneFeatures[zone_index], output, report, finite);
  }

  output.values[schema::index(FeatureIndex::LightsActive)] = input.lights_active ? 1.0f : 0.0f;

  finite &= encodeFinite(input.environment.growbox_volume_m3, FeatureIndex::GrowboxVolumeM3, output,
                         report);
  finite &= encodeFinite(input.environment.thermal_mass_j_per_k, FeatureIndex::ThermalMassJPerK,
                         output, report);
  finite &= encodeFinite(input.environment.heat_loss_w_per_k, FeatureIndex::HeatLossWPerK, output,
                         report);
  finite &= encodeFinite(input.environment.air_leak_rate_ach, FeatureIndex::AirLeakRateAch, output,
                         report);

  output.values[schema::index(FeatureIndex::HeaterAvailable)] =
      input.actuators.heater.available ? 1.0f : 0.0f;
  const float heater_power =
      input.actuators.heater.available ? input.actuators.heater.max_power_w : 0.0f;
  if (!input.actuators.heater.available) {
    markSubstitutionIfNeeded(input.actuators.heater.max_power_w, heater_power,
                             FeatureIndex::HeaterMaxPowerW, report);
  }
  finite &= encodeFinite(heater_power, FeatureIndex::HeaterMaxPowerW, output, report);
  finite &= encodeFinite(input.actuators.heater.efficiency, FeatureIndex::HeaterEfficiency, output,
                         report);

  output.values[schema::index(FeatureIndex::FanAvailable)] =
      input.actuators.fan.available ? 1.0f : 0.0f;
  const float fan_airflow =
      input.actuators.fan.available ? input.actuators.fan.max_airflow_m3_h : 0.0f;
  if (!input.actuators.fan.available) {
    markSubstitutionIfNeeded(input.actuators.fan.max_airflow_m3_h, fan_airflow,
                             FeatureIndex::FanMaxAirflowM3H, report);
  }
  finite &= encodeFinite(fan_airflow, FeatureIndex::FanMaxAirflowM3H, output, report);
  finite &= encodeFinite(input.actuators.fan.minimum_command, FeatureIndex::FanMinimumCommand,
                         output, report);

  output.values[schema::index(FeatureIndex::HumidifierAvailable)] =
      input.actuators.humidifier.available ? 1.0f : 0.0f;
  const float humidifier_output =
      input.actuators.humidifier.available ? input.actuators.humidifier.max_output_g_h : 0.0f;
  if (!input.actuators.humidifier.available) {
    markSubstitutionIfNeeded(input.actuators.humidifier.max_output_g_h, humidifier_output,
                             FeatureIndex::HumidifierMaxOutputGH, report);
  }
  finite &= encodeFinite(humidifier_output, FeatureIndex::HumidifierMaxOutputGH, output, report);

  output.values[schema::index(FeatureIndex::DehumidifierAvailable)] =
      input.actuators.dehumidifier.available ? 1.0f : 0.0f;
  const float dehumidifier_output =
      input.actuators.dehumidifier.available ? input.actuators.dehumidifier.max_removal_g_h : 0.0f;
  if (!input.actuators.dehumidifier.available) {
    markSubstitutionIfNeeded(input.actuators.dehumidifier.max_removal_g_h, dehumidifier_output,
                             FeatureIndex::DehumidifierMaxRemovalGH, report);
  }
  finite &=
      encodeFinite(dehumidifier_output, FeatureIndex::DehumidifierMaxRemovalGH, output, report);

  output.values[schema::index(FeatureIndex::CoolerAvailable)] =
      input.actuators.cooler.available ? 1.0f : 0.0f;
  const float cooler_output =
      input.actuators.cooler.available ? input.actuators.cooler.max_cooling_w : 0.0f;
  if (!input.actuators.cooler.available) {
    markSubstitutionIfNeeded(input.actuators.cooler.max_cooling_w, cooler_output,
                             FeatureIndex::CoolerMaxCoolingW, report);
  }
  finite &= encodeFinite(cooler_output, FeatureIndex::CoolerMaxCoolingW, output, report);

  output.values[schema::index(FeatureIndex::Co2DoserAvailable)] =
      input.actuators.co2_doser.available ? 1.0f : 0.0f;
  const float co2_dose = input.actuators.co2_doser.available
                             ? input.actuators.co2_doser.dose_ppm_per_full_pulse
                             : 0.0f;
  const float co2_pulse =
      input.actuators.co2_doser.available ? input.actuators.co2_doser.maximum_pulse_s : 0.0f;
  if (!input.actuators.co2_doser.available) {
    markSubstitutionIfNeeded(input.actuators.co2_doser.dose_ppm_per_full_pulse, co2_dose,
                             FeatureIndex::Co2DoserDosePpmPerFullPulse, report);
    markSubstitutionIfNeeded(input.actuators.co2_doser.maximum_pulse_s, co2_pulse,
                             FeatureIndex::Co2DoserMaximumPulseS, report);
  }
  finite &= encodeFinite(co2_dose, FeatureIndex::Co2DoserDosePpmPerFullPulse, output, report);
  finite &= encodeFinite(co2_pulse, FeatureIndex::Co2DoserMaximumPulseS, output, report);

  finite &= encodeFinite(input.targets.air_temperature_c, FeatureIndex::TargetAirTemperatureC,
                         output, report);
  finite &= encodeFinite(input.targets.air_humidity_pct, FeatureIndex::TargetAirHumidityPct, output,
                         report);
  finite &= encodeFinite(input.targets.co2_ppm, FeatureIndex::TargetCo2Ppm, output, report);
  finite &= encodeFinite(input.previous.heater, FeatureIndex::PreviousHeater, output, report);
  finite &= encodeFinite(input.previous.fan, FeatureIndex::PreviousFan, output, report);
  finite &=
      encodeFinite(input.previous.humidifier, FeatureIndex::PreviousHumidifier, output, report);
  finite &=
      encodeFinite(input.previous.dehumidifier, FeatureIndex::PreviousDehumidifier, output, report);
  finite &= encodeFinite(input.previous.cooler, FeatureIndex::PreviousCooler, output, report);
  finite &= encodeFinite(input.previous.co2_doser, FeatureIndex::PreviousCo2Doser, output, report);

  return finite ? EncoderStatus::Ok : EncoderStatus::NonFiniteInput;
}

} // namespace control
} // namespace growbox
