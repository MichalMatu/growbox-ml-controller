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
  FeatureIndex target_soil_temperature;
  FeatureIndex irrigation_available;
  FeatureIndex irrigation_flow;
  FeatureIndex irrigation_pulse;
  FeatureIndex irrigation_interval;
  FeatureIndex irrigation_control;
  FeatureIndex heat_mat_available;
  FeatureIndex heat_mat_max_power;
  FeatureIndex heat_mat_control;
  FeatureIndex previous_irrigation;
  FeatureIndex previous_heat_mat;
};

constexpr std::array<ZoneFeatureMap, kMaxPots> kZoneFeatures{{
    {FeatureIndex::Pot1Available,
     FeatureIndex::SoilMoisturePot1Pct,
     FeatureIndex::SoilTemperaturePot1C,
     FeatureIndex::SoilMoisturePot1Valid,
     FeatureIndex::SoilTemperaturePot1Valid,
     FeatureIndex::Pot1PotVolumeL,
     FeatureIndex::Pot1SubstrateWaterCapacityMl,
     FeatureIndex::Pot1TranspirationFactor,
     FeatureIndex::Pot1TargetSoilMoisturePct,
     FeatureIndex::Pot1TargetSoilTemperatureC,
     FeatureIndex::Pot1IrrigationAvailable,
     FeatureIndex::Pot1IrrigationFlowMlS,
     FeatureIndex::Pot1IrrigationMaximumPulseS,
     FeatureIndex::Pot1IrrigationMinimumIntervalS,
     FeatureIndex::Pot1IrrigationControlType,
     FeatureIndex::Pot1HeatMatAvailable,
     FeatureIndex::Pot1HeatMatMaxPowerW,
     FeatureIndex::Pot1HeatMatControlType,
     FeatureIndex::Pot1PreviousIrrigation,
     FeatureIndex::Pot1PreviousHeatMat},
    {FeatureIndex::Pot2Available,
     FeatureIndex::SoilMoisturePot2Pct,
     FeatureIndex::SoilTemperaturePot2C,
     FeatureIndex::SoilMoisturePot2Valid,
     FeatureIndex::SoilTemperaturePot2Valid,
     FeatureIndex::Pot2PotVolumeL,
     FeatureIndex::Pot2SubstrateWaterCapacityMl,
     FeatureIndex::Pot2TranspirationFactor,
     FeatureIndex::Pot2TargetSoilMoisturePct,
     FeatureIndex::Pot2TargetSoilTemperatureC,
     FeatureIndex::Pot2IrrigationAvailable,
     FeatureIndex::Pot2IrrigationFlowMlS,
     FeatureIndex::Pot2IrrigationMaximumPulseS,
     FeatureIndex::Pot2IrrigationMinimumIntervalS,
     FeatureIndex::Pot2IrrigationControlType,
     FeatureIndex::Pot2HeatMatAvailable,
     FeatureIndex::Pot2HeatMatMaxPowerW,
     FeatureIndex::Pot2HeatMatControlType,
     FeatureIndex::Pot2PreviousIrrigation,
     FeatureIndex::Pot2PreviousHeatMat},
    {FeatureIndex::Pot3Available,
     FeatureIndex::SoilMoisturePot3Pct,
     FeatureIndex::SoilTemperaturePot3C,
     FeatureIndex::SoilMoisturePot3Valid,
     FeatureIndex::SoilTemperaturePot3Valid,
     FeatureIndex::Pot3PotVolumeL,
     FeatureIndex::Pot3SubstrateWaterCapacityMl,
     FeatureIndex::Pot3TranspirationFactor,
     FeatureIndex::Pot3TargetSoilMoisturePct,
     FeatureIndex::Pot3TargetSoilTemperatureC,
     FeatureIndex::Pot3IrrigationAvailable,
     FeatureIndex::Pot3IrrigationFlowMlS,
     FeatureIndex::Pot3IrrigationMaximumPulseS,
     FeatureIndex::Pot3IrrigationMinimumIntervalS,
     FeatureIndex::Pot3IrrigationControlType,
     FeatureIndex::Pot3HeatMatAvailable,
     FeatureIndex::Pot3HeatMatMaxPowerW,
     FeatureIndex::Pot3HeatMatControlType,
     FeatureIndex::Pot3PreviousIrrigation,
     FeatureIndex::Pot3PreviousHeatMat},
    {FeatureIndex::Pot4Available,
     FeatureIndex::SoilMoisturePot4Pct,
     FeatureIndex::SoilTemperaturePot4C,
     FeatureIndex::SoilMoisturePot4Valid,
     FeatureIndex::SoilTemperaturePot4Valid,
     FeatureIndex::Pot4PotVolumeL,
     FeatureIndex::Pot4SubstrateWaterCapacityMl,
     FeatureIndex::Pot4TranspirationFactor,
     FeatureIndex::Pot4TargetSoilMoisturePct,
     FeatureIndex::Pot4TargetSoilTemperatureC,
     FeatureIndex::Pot4IrrigationAvailable,
     FeatureIndex::Pot4IrrigationFlowMlS,
     FeatureIndex::Pot4IrrigationMaximumPulseS,
     FeatureIndex::Pot4IrrigationMinimumIntervalS,
     FeatureIndex::Pot4IrrigationControlType,
     FeatureIndex::Pot4HeatMatAvailable,
     FeatureIndex::Pot4HeatMatMaxPowerW,
     FeatureIndex::Pot4HeatMatControlType,
     FeatureIndex::Pot4PreviousIrrigation,
     FeatureIndex::Pot4PreviousHeatMat},
}};

bool encodeZone(const PotConfig& pot, const ZoneFeatureMap& features, FeatureVector& output,
                EncoderReport& report, bool& finite) noexcept {
  output.values[schema::index(features.available)] = pot.available ? 1.0f : 0.0f;
  finite &= encodeSensor(pot.sensors.soil_moisture_pct, pot.available && pot.validity.soil_moisture,
                         features.soil_moisture, features.soil_moisture_valid, output, report);
  finite &=
      encodeSensor(pot.sensors.soil_temperature_c, pot.available && pot.validity.soil_temperature,
                   features.soil_temperature, features.soil_temperature_valid, output, report);

  finite &= encodeFinite(pot.cultivation.pot_volume_l, features.pot_volume, output, report);
  finite &= encodeFinite(pot.cultivation.substrate_water_capacity_ml, features.water_capacity,
                         output, report);
  finite &=
      encodeFinite(pot.cultivation.transpiration_factor, features.transpiration, output, report);
  const float target_soil = pot.available
                                ? pot.target_soil_moisture_pct
                                : schema::kFeatureDefaults[schema::index(features.target_soil)];
  if (!pot.available) {
    markSubstitutionIfNeeded(pot.target_soil_moisture_pct, target_soil, features.target_soil,
                             report);
  }
  finite &= encodeFinite(target_soil, features.target_soil, output, report);

  const float target_soil_temperature =
      pot.available ? pot.target_soil_temperature_c
                    : schema::kFeatureDefaults[schema::index(features.target_soil_temperature)];
  if (!pot.available) {
    markSubstitutionIfNeeded(pot.target_soil_temperature_c, target_soil_temperature,
                             features.target_soil_temperature, report);
  }
  finite &= encodeFinite(target_soil_temperature, features.target_soil_temperature, output, report);

  output.values[schema::index(features.irrigation_available)] =
      pot.irrigation.available ? 1.0f : 0.0f;
  const float flow = pot.irrigation.available ? pot.irrigation.flow_ml_s : 0.0f;
  const float pulse = pot.irrigation.available ? pot.irrigation.maximum_pulse_s : 0.0f;
  if (!pot.irrigation.available) {
    markSubstitutionIfNeeded(pot.irrigation.flow_ml_s, flow, features.irrigation_flow, report);
    markSubstitutionIfNeeded(pot.irrigation.maximum_pulse_s, pulse, features.irrigation_pulse,
                             report);
  }
  finite &= encodeFinite(flow, features.irrigation_flow, output, report);
  finite &= encodeFinite(pulse, features.irrigation_pulse, output, report);
  finite &=
      encodeFinite(pot.irrigation.minimum_interval_s, features.irrigation_interval, output, report);
  finite &= encodeFinite(static_cast<float>(pot.irrigation.control_type),
                         features.irrigation_control, output, report);

  output.values[schema::index(features.heat_mat_available)] = pot.heat_mat.available ? 1.0f : 0.0f;
  const float heat_mat_power = pot.heat_mat.available ? pot.heat_mat.max_power_w : 0.0f;
  if (!pot.heat_mat.available) {
    markSubstitutionIfNeeded(pot.heat_mat.max_power_w, heat_mat_power, features.heat_mat_max_power,
                             report);
  }
  finite &= encodeFinite(heat_mat_power, features.heat_mat_max_power, output, report);
  finite &= encodeFinite(static_cast<float>(pot.heat_mat.control_type), features.heat_mat_control,
                         output, report);
  finite &= encodeFinite(pot.previous_irrigation, features.previous_irrigation, output, report);
  finite &= encodeFinite(pot.previous_heat_mat, features.previous_heat_mat, output, report);
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

  for (std::size_t pot_index = 0; pot_index < kMaxPots; ++pot_index) {
    finite = encodeZone(input.pots[pot_index], kZoneFeatures[pot_index], output, report, finite);
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

  output.values[schema::index(FeatureIndex::NutrientHeaterAvailable)] =
      input.actuators.nutrient_heater.available ? 1.0f : 0.0f;
  const float nutrient_heater_power = input.actuators.nutrient_heater.available
                                          ? input.actuators.nutrient_heater.max_power_w
                                          : 0.0f;
  if (!input.actuators.nutrient_heater.available) {
    markSubstitutionIfNeeded(input.actuators.nutrient_heater.max_power_w, nutrient_heater_power,
                             FeatureIndex::NutrientHeaterMaxPowerW, report);
  }
  finite &=
      encodeFinite(nutrient_heater_power, FeatureIndex::NutrientHeaterMaxPowerW, output, report);
  finite &= encodeFinite(input.actuators.nutrient_heater.efficiency,
                         FeatureIndex::NutrientHeaterEfficiency, output, report);

  finite &= encodeFinite(input.targets.air_temperature_c, FeatureIndex::TargetAirTemperatureC,
                         output, report);
  finite &= encodeFinite(input.targets.air_humidity_pct, FeatureIndex::TargetAirHumidityPct, output,
                         report);
  finite &= encodeFinite(input.targets.co2_ppm, FeatureIndex::TargetCo2Ppm, output, report);
  finite &= encodeFinite(input.targets.nutrient_solution_temperature_c,
                         FeatureIndex::TargetNutrientSolutionTemperatureC, output, report);
  finite &= encodeFinite(input.previous.heater, FeatureIndex::PreviousHeater, output, report);
  finite &= encodeFinite(input.previous.fan, FeatureIndex::PreviousFan, output, report);
  finite &=
      encodeFinite(input.previous.humidifier, FeatureIndex::PreviousHumidifier, output, report);
  finite &=
      encodeFinite(input.previous.dehumidifier, FeatureIndex::PreviousDehumidifier, output, report);
  finite &= encodeFinite(input.previous.cooler, FeatureIndex::PreviousCooler, output, report);
  finite &= encodeFinite(input.previous.co2_doser, FeatureIndex::PreviousCo2Doser, output, report);
  finite &= encodeFinite(input.previous.nutrient_heater, FeatureIndex::PreviousNutrientHeater,
                         output, report);

  return finite ? EncoderStatus::Ok : EncoderStatus::NonFiniteInput;
}

} // namespace control
} // namespace growbox
