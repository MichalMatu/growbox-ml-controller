#include "ScenarioWireCodec.h"

#include "EnvironmentSchema.h"

#include <cJSON.h>

#include <cmath>
#include <cstring>
#include <limits>

namespace growbox {
namespace demo {
namespace wire {
namespace {

using control::schema::FeatureIndex;

const cJSON* item(const cJSON* object, const char* key) noexcept {
  return cJSON_IsObject(object) ? cJSON_GetObjectItemCaseSensitive(object, key) : nullptr;
}

const cJSON* objectItem(const cJSON* object, const char* key) noexcept {
  const cJSON* value = item(object, key);
  return cJSON_IsObject(value) ? value : nullptr;
}

bool readFiniteFloat(const cJSON* object, const char* key, float& destination) noexcept {
  const cJSON* value = item(object, key);
  if (!cJSON_IsNumber(value) || !std::isfinite(value->valuedouble) ||
      std::fabs(value->valuedouble) > std::numeric_limits<float>::max()) {
    return false;
  }
  const float parsed = static_cast<float>(value->valuedouble);
  if (!std::isfinite(parsed)) {
    return false;
  }
  destination = parsed;
  return true;
}

bool readOptionalFiniteFloat(const cJSON* object, const char* key, float& destination) noexcept {
  const cJSON* value = item(object, key);
  if (value == nullptr || cJSON_IsNull(value)) {
    return true;
  }
  return readFiniteFloat(object, key, destination);
}

bool readBool(const cJSON* object, const char* key, bool& destination) noexcept {
  const cJSON* value = item(object, key);
  if (!cJSON_IsBool(value)) {
    return false;
  }
  destination = cJSON_IsTrue(value);
  return true;
}

bool readOptionalBool(const cJSON* object, const char* key, bool& destination) noexcept {
  const cJSON* value = item(object, key);
  if (value == nullptr || cJSON_IsNull(value)) {
    return true;
  }
  return readBool(object, key, destination);
}

bool readUnsigned(const cJSON* object, const char* key, std::uint32_t& destination) noexcept {
  const cJSON* value = item(object, key);
  if (!cJSON_IsNumber(value) || !std::isfinite(value->valuedouble) || value->valuedouble < 0.0 ||
      value->valuedouble > static_cast<double>(std::numeric_limits<std::uint32_t>::max()) ||
      std::floor(value->valuedouble) != value->valuedouble) {
    return false;
  }
  destination = static_cast<std::uint32_t>(value->valuedouble);
  return true;
}

const char* readString(const cJSON* object, const char* key) noexcept {
  const cJSON* value = item(object, key);
  return cJSON_IsString(value) && value->valuestring != nullptr ? value->valuestring : nullptr;
}

bool parseSensors(const cJSON* object, control::SensorState& sensors) noexcept {
  return object != nullptr &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::AirTemperatureC),
                         sensors.air_temperature_c) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::AirHumidityPct),
                         sensors.air_humidity_pct) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::Co2Ppm), sensors.co2_ppm) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::SoilMoisturePct),
                         sensors.soil_moisture_pct) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::OutsideTemperatureC),
                         sensors.outside_temperature_c) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::OutsideHumidityPct),
                         sensors.outside_humidity_pct) &&
         readOptionalFiniteFloat(object, "outside_co2_ppm", sensors.outside_co2_ppm);
}

bool parseValidity(const cJSON* object, control::SensorValidity& validity) noexcept {
  return object != nullptr &&
         readBool(object, control::schema::wireKey(FeatureIndex::AirTemperatureValid),
                  validity.air_temperature) &&
         readBool(object, control::schema::wireKey(FeatureIndex::AirHumidityValid),
                  validity.air_humidity) &&
         readBool(object, control::schema::wireKey(FeatureIndex::Co2Valid), validity.co2) &&
         readBool(object, control::schema::wireKey(FeatureIndex::SoilMoistureValid),
                  validity.soil_moisture) &&
         readBool(object, control::schema::wireKey(FeatureIndex::OutsideTemperatureValid),
                  validity.outside_temperature) &&
         readBool(object, control::schema::wireKey(FeatureIndex::OutsideHumidityValid),
                  validity.outside_humidity) &&
         readOptionalBool(object, "outside_co2_ppm", validity.outside_co2);
}

bool parseEnvironment(const cJSON* object, control::EnvironmentConfig& config) noexcept {
  return object != nullptr &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::GrowboxVolumeM3),
                         config.growbox_volume_m3) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::ThermalMassJPerK),
                         config.thermal_mass_j_per_k) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::HeatLossWPerK),
                         config.heat_loss_w_per_k) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::AirLeakRateAch),
                         config.air_leak_rate_ach);
}

bool parseCultivation(const cJSON* object, control::CultivationConfig& config) noexcept {
  return object != nullptr &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::PotVolumeL),
                         config.pot_volume_l) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::SubstrateWaterCapacityMl),
                         config.substrate_water_capacity_ml) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::TranspirationFactor),
                         config.transpiration_factor);
}

bool parseTargets(const cJSON* object, control::ControlTargets& targets, bool require_all) noexcept {
  if (object == nullptr) {
    return false;
  }

  bool parsed_any = false;
  auto read_optional = [&](const char* key, float& destination) {
    const cJSON* value = item(object, key);
    if (value == nullptr || cJSON_IsNull(value)) {
      return !require_all;
    }
    parsed_any = true;
    return readFiniteFloat(object, key, destination);
  };

  const bool valid =
      read_optional(control::schema::wireKey(FeatureIndex::TargetAirTemperatureC),
                    targets.air_temperature_c) &&
      read_optional(control::schema::wireKey(FeatureIndex::TargetAirHumidityPct),
                    targets.air_humidity_pct) &&
      read_optional(control::schema::wireKey(FeatureIndex::TargetCo2Ppm), targets.co2_ppm) &&
      read_optional(control::schema::wireKey(FeatureIndex::TargetSoilMoisturePct),
                    targets.soil_moisture_pct);
  return valid && (require_all || parsed_any);
}

bool parsePrevious(const cJSON* object, control::PreviousControlState& previous) noexcept {
  return object != nullptr &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::PreviousHeater),
                         previous.heater) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::PreviousFan), previous.fan) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::PreviousHumidifier),
                         previous.humidifier) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::PreviousIrrigation),
                         previous.irrigation);
}

bool parseSafety(const cJSON* object, control::SafetyConfig& safety) noexcept {
  if (object == nullptr || cJSON_IsNull(object)) {
    return true;
  }
  return readOptionalFiniteFloat(object, "maximum_air_temperature_c",
                                 safety.maximum_air_temperature_c) &&
         readOptionalFiniteFloat(object, "alarm_air_temperature_c",
                                 safety.alarm_air_temperature_c) &&
         readOptionalFiniteFloat(object, "alarm_minimum_fan", safety.alarm_minimum_fan) &&
         readOptionalFiniteFloat(object, "binary_threshold", safety.binary_threshold) &&
         readOptionalFiniteFloat(object, "heater_minimum_on_s", safety.heater_minimum_on_s) &&
         readOptionalFiniteFloat(object, "heater_minimum_off_s", safety.heater_minimum_off_s) &&
         readOptionalFiniteFloat(object, "humidifier_minimum_on_s",
                                 safety.humidifier_minimum_on_s) &&
         readOptionalFiniteFloat(object, "humidifier_minimum_off_s",
                                 safety.humidifier_minimum_off_s);
}

const char* controlTypeName(control::ActuatorControlType type) noexcept {
  return type == control::ActuatorControlType::Pwm ? "pwm" : "binary";
}

bool parseControlType(const char* control_type,
                      control::ActuatorControlType& destination) noexcept {
  if (control_type != nullptr && std::strcmp(control_type, "binary") == 0) {
    destination = control::ActuatorControlType::Binary;
    return true;
  }
  if (control_type != nullptr && std::strcmp(control_type, "pwm") == 0) {
    destination = control::ActuatorControlType::Pwm;
    return true;
  }
  return false;
}

bool parseActuators(const cJSON* object, control::ActuatorCapabilities& actuators) noexcept {
  if (object == nullptr) {
    return false;
  }

  const cJSON* heater = objectItem(object, control::schema::kWireObjectHeater);
  const cJSON* fan = objectItem(object, control::schema::kWireObjectFan);
  const cJSON* humidifier = objectItem(object, control::schema::kWireObjectHumidifier);
  const cJSON* irrigation = objectItem(object, control::schema::kWireObjectIrrigation);
  if (heater == nullptr || fan == nullptr || humidifier == nullptr || irrigation == nullptr) {
    return false;
  }

  if (!parseControlType(readString(heater, control::schema::wireKey(FeatureIndex::HeaterControlType)),
                       actuators.heater.control_type) ||
      !parseControlType(readString(fan, control::schema::wireKey(FeatureIndex::FanControlType)),
                        actuators.fan.control_type) ||
      !parseControlType(
          readString(humidifier, control::schema::wireKey(FeatureIndex::HumidifierControlType)),
          actuators.humidifier.control_type) ||
      !parseControlType(
          readString(irrigation, control::schema::wireKey(FeatureIndex::IrrigationControlType)),
          actuators.irrigation_pump.control_type)) {
    return false;
  }

  return readBool(heater, control::schema::wireKey(FeatureIndex::HeaterAvailable),
                  actuators.heater.available) &&
         readFiniteFloat(heater, control::schema::wireKey(FeatureIndex::HeaterMaxPowerW),
                         actuators.heater.max_power_w) &&
         readFiniteFloat(heater, control::schema::wireKey(FeatureIndex::HeaterEfficiency),
                         actuators.heater.efficiency) &&
         readBool(fan, control::schema::wireKey(FeatureIndex::FanAvailable),
                  actuators.fan.available) &&
         readFiniteFloat(fan, control::schema::wireKey(FeatureIndex::FanMaxAirflowM3H),
                         actuators.fan.max_airflow_m3_h) &&
         readFiniteFloat(fan, control::schema::wireKey(FeatureIndex::FanMinimumCommand),
                         actuators.fan.minimum_command) &&
         readBool(humidifier, control::schema::wireKey(FeatureIndex::HumidifierAvailable),
                  actuators.humidifier.available) &&
         readFiniteFloat(humidifier, control::schema::wireKey(FeatureIndex::HumidifierMaxOutputGH),
                         actuators.humidifier.max_output_g_h) &&
         readBool(irrigation, control::schema::wireKey(FeatureIndex::IrrigationAvailable),
                  actuators.irrigation_pump.available) &&
         readFiniteFloat(irrigation, control::schema::wireKey(FeatureIndex::IrrigationFlowMlS),
                         actuators.irrigation_pump.flow_ml_s) &&
         readFiniteFloat(irrigation,
                         control::schema::wireKey(FeatureIndex::IrrigationMaximumPulseS),
                         actuators.irrigation_pump.maximum_pulse_s) &&
         readFiniteFloat(irrigation,
                         control::schema::wireKey(FeatureIndex::IrrigationMinimumIntervalS),
                         actuators.irrigation_pump.minimum_interval_s);
}

void addActuatorAvailability(cJSON* document,
                             const control::ActuatorCapabilities& actuators) noexcept {
  if (document == nullptr) {
    return;
  }
  cJSON* actuators_json = cJSON_AddObjectToObject(document, "actuators");
  cJSON* heater_json = cJSON_AddObjectToObject(actuators_json, "heater");
  cJSON_AddBoolToObject(heater_json, "available", actuators.heater.available);
  cJSON* fan_json = cJSON_AddObjectToObject(actuators_json, "fan");
  cJSON_AddBoolToObject(fan_json, "available", actuators.fan.available);
  cJSON* humidifier_json = cJSON_AddObjectToObject(actuators_json, "humidifier");
  cJSON_AddBoolToObject(humidifier_json, "available", actuators.humidifier.available);
  cJSON* irrigation_json = cJSON_AddObjectToObject(actuators_json, "irrigation");
  cJSON_AddBoolToObject(irrigation_json, "available", actuators.irrigation_pump.available);
}

}  // namespace

void addScenarioSnapshot(cJSON* document, const control::ControllerInput& input) noexcept {
  if (document == nullptr) {
    return;
  }

  cJSON* sensors = cJSON_AddObjectToObject(document, control::schema::kWireRootSensors);
  cJSON_AddNumberToObject(sensors, control::schema::wireKey(FeatureIndex::AirTemperatureC),
                          input.sensors.air_temperature_c);
  cJSON_AddNumberToObject(sensors, control::schema::wireKey(FeatureIndex::AirHumidityPct),
                          input.sensors.air_humidity_pct);
  cJSON_AddNumberToObject(sensors, control::schema::wireKey(FeatureIndex::Co2Ppm),
                          input.sensors.co2_ppm);
  cJSON_AddNumberToObject(sensors, control::schema::wireKey(FeatureIndex::SoilMoisturePct),
                          input.sensors.soil_moisture_pct);
  cJSON_AddNumberToObject(sensors, control::schema::wireKey(FeatureIndex::OutsideTemperatureC),
                          input.sensors.outside_temperature_c);
  cJSON_AddNumberToObject(sensors, control::schema::wireKey(FeatureIndex::OutsideHumidityPct),
                          input.sensors.outside_humidity_pct);
  cJSON_AddNumberToObject(sensors, "outside_co2_ppm", input.sensors.outside_co2_ppm);

  cJSON* validity = cJSON_AddObjectToObject(document, control::schema::kWireRootValidity);
  cJSON_AddBoolToObject(validity, control::schema::wireKey(FeatureIndex::AirTemperatureValid),
                        input.validity.air_temperature);
  cJSON_AddBoolToObject(validity, control::schema::wireKey(FeatureIndex::AirHumidityValid),
                        input.validity.air_humidity);
  cJSON_AddBoolToObject(validity, control::schema::wireKey(FeatureIndex::Co2Valid), input.validity.co2);
  cJSON_AddBoolToObject(validity, control::schema::wireKey(FeatureIndex::SoilMoistureValid),
                        input.validity.soil_moisture);
  cJSON_AddBoolToObject(validity, control::schema::wireKey(FeatureIndex::OutsideTemperatureValid),
                        input.validity.outside_temperature);
  cJSON_AddBoolToObject(validity, control::schema::wireKey(FeatureIndex::OutsideHumidityValid),
                        input.validity.outside_humidity);
  cJSON_AddBoolToObject(validity, "outside_co2_ppm", input.validity.outside_co2);

  cJSON* environment = cJSON_AddObjectToObject(document, control::schema::kWireRootEnvironment);
  cJSON_AddNumberToObject(environment, control::schema::wireKey(FeatureIndex::GrowboxVolumeM3),
                          input.environment.growbox_volume_m3);
  cJSON_AddNumberToObject(environment, control::schema::wireKey(FeatureIndex::ThermalMassJPerK),
                          input.environment.thermal_mass_j_per_k);
  cJSON_AddNumberToObject(environment, control::schema::wireKey(FeatureIndex::HeatLossWPerK),
                          input.environment.heat_loss_w_per_k);
  cJSON_AddNumberToObject(environment, control::schema::wireKey(FeatureIndex::AirLeakRateAch),
                          input.environment.air_leak_rate_ach);

  cJSON* cultivation = cJSON_AddObjectToObject(document, control::schema::kWireRootCultivation);
  cJSON_AddNumberToObject(cultivation, control::schema::wireKey(FeatureIndex::PotVolumeL),
                          input.cultivation.pot_volume_l);
  cJSON_AddNumberToObject(cultivation,
                          control::schema::wireKey(FeatureIndex::SubstrateWaterCapacityMl),
                          input.cultivation.substrate_water_capacity_ml);
  cJSON_AddNumberToObject(cultivation, control::schema::wireKey(FeatureIndex::TranspirationFactor),
                          input.cultivation.transpiration_factor);

  cJSON* actuators = cJSON_AddObjectToObject(document, control::schema::kWireRootActuators);
  cJSON* heater = cJSON_AddObjectToObject(actuators, control::schema::kWireObjectHeater);
  cJSON_AddBoolToObject(heater, control::schema::wireKey(FeatureIndex::HeaterAvailable),
                        input.actuators.heater.available);
  cJSON_AddNumberToObject(heater, control::schema::wireKey(FeatureIndex::HeaterMaxPowerW),
                          input.actuators.heater.max_power_w);
  cJSON_AddNumberToObject(heater, control::schema::wireKey(FeatureIndex::HeaterEfficiency),
                          input.actuators.heater.efficiency);
  cJSON_AddStringToObject(heater, control::schema::wireKey(FeatureIndex::HeaterControlType),
                          controlTypeName(input.actuators.heater.control_type));

  cJSON* fan = cJSON_AddObjectToObject(actuators, control::schema::kWireObjectFan);
  cJSON_AddBoolToObject(fan, control::schema::wireKey(FeatureIndex::FanAvailable),
                        input.actuators.fan.available);
  cJSON_AddNumberToObject(fan, control::schema::wireKey(FeatureIndex::FanMaxAirflowM3H),
                          input.actuators.fan.max_airflow_m3_h);
  cJSON_AddNumberToObject(fan, control::schema::wireKey(FeatureIndex::FanMinimumCommand),
                          input.actuators.fan.minimum_command);
  cJSON_AddStringToObject(fan, control::schema::wireKey(FeatureIndex::FanControlType),
                          controlTypeName(input.actuators.fan.control_type));

  cJSON* humidifier = cJSON_AddObjectToObject(actuators, control::schema::kWireObjectHumidifier);
  cJSON_AddBoolToObject(humidifier, control::schema::wireKey(FeatureIndex::HumidifierAvailable),
                        input.actuators.humidifier.available);
  cJSON_AddNumberToObject(humidifier, control::schema::wireKey(FeatureIndex::HumidifierMaxOutputGH),
                          input.actuators.humidifier.max_output_g_h);
  cJSON_AddStringToObject(humidifier, control::schema::wireKey(FeatureIndex::HumidifierControlType),
                          controlTypeName(input.actuators.humidifier.control_type));

  cJSON* irrigation = cJSON_AddObjectToObject(actuators, control::schema::kWireObjectIrrigation);
  cJSON_AddBoolToObject(irrigation, control::schema::wireKey(FeatureIndex::IrrigationAvailable),
                        input.actuators.irrigation_pump.available);
  cJSON_AddNumberToObject(irrigation, control::schema::wireKey(FeatureIndex::IrrigationFlowMlS),
                          input.actuators.irrigation_pump.flow_ml_s);
  cJSON_AddNumberToObject(irrigation, control::schema::wireKey(FeatureIndex::IrrigationMaximumPulseS),
                          input.actuators.irrigation_pump.maximum_pulse_s);
  cJSON_AddNumberToObject(irrigation,
                          control::schema::wireKey(FeatureIndex::IrrigationMinimumIntervalS),
                          input.actuators.irrigation_pump.minimum_interval_s);
  cJSON_AddStringToObject(irrigation, control::schema::wireKey(FeatureIndex::IrrigationControlType),
                          controlTypeName(input.actuators.irrigation_pump.control_type));

  cJSON* targets = cJSON_AddObjectToObject(document, control::schema::kWireRootTargets);
  cJSON_AddNumberToObject(targets, control::schema::wireKey(FeatureIndex::TargetAirTemperatureC),
                          input.targets.air_temperature_c);
  cJSON_AddNumberToObject(targets, control::schema::wireKey(FeatureIndex::TargetAirHumidityPct),
                          input.targets.air_humidity_pct);
  cJSON_AddNumberToObject(targets, control::schema::wireKey(FeatureIndex::TargetCo2Ppm),
                          input.targets.co2_ppm);
  cJSON_AddNumberToObject(targets, control::schema::wireKey(FeatureIndex::TargetSoilMoisturePct),
                          input.targets.soil_moisture_pct);

  cJSON* previous = cJSON_AddObjectToObject(document, control::schema::kWireRootPrevious);
  cJSON_AddNumberToObject(previous, control::schema::wireKey(FeatureIndex::PreviousHeater),
                          input.previous.heater);
  cJSON_AddNumberToObject(previous, control::schema::wireKey(FeatureIndex::PreviousFan),
                          input.previous.fan);
  cJSON_AddNumberToObject(previous, control::schema::wireKey(FeatureIndex::PreviousHumidifier),
                          input.previous.humidifier);
  cJSON_AddNumberToObject(previous, control::schema::wireKey(FeatureIndex::PreviousIrrigation),
                          input.previous.irrigation);

  cJSON* safety = cJSON_AddObjectToObject(document, "safety");
  cJSON_AddNumberToObject(safety, "maximum_air_temperature_c",
                          input.safety.maximum_air_temperature_c);
  cJSON_AddNumberToObject(safety, "alarm_air_temperature_c", input.safety.alarm_air_temperature_c);
  cJSON_AddNumberToObject(safety, "alarm_minimum_fan", input.safety.alarm_minimum_fan);
  cJSON_AddNumberToObject(safety, "binary_threshold", input.safety.binary_threshold);
  cJSON_AddNumberToObject(safety, "heater_minimum_on_s", input.safety.heater_minimum_on_s);
  cJSON_AddNumberToObject(safety, "heater_minimum_off_s", input.safety.heater_minimum_off_s);
  cJSON_AddNumberToObject(safety, "humidifier_minimum_on_s", input.safety.humidifier_minimum_on_s);
  cJSON_AddNumberToObject(safety, "humidifier_minimum_off_s", input.safety.humidifier_minimum_off_s);
}

void addDecisionContext(cJSON* document, const control::ControllerInput& input) noexcept {
  if (document == nullptr) {
    return;
  }

  cJSON* sensors = cJSON_AddObjectToObject(document, "sensors");
  cJSON_AddNumberToObject(sensors, "air_temperature_c", input.sensors.air_temperature_c);
  cJSON_AddNumberToObject(sensors, "air_humidity_pct", input.sensors.air_humidity_pct);
  cJSON_AddNumberToObject(sensors, "co2_ppm", input.sensors.co2_ppm);
  cJSON_AddNumberToObject(sensors, "soil_moisture_pct", input.sensors.soil_moisture_pct);
  cJSON_AddNumberToObject(sensors, "outside_temperature_c", input.sensors.outside_temperature_c);
  cJSON_AddNumberToObject(sensors, "outside_humidity_pct", input.sensors.outside_humidity_pct);
  cJSON_AddNumberToObject(sensors, "outside_co2_ppm", input.sensors.outside_co2_ppm);

  cJSON* validity = cJSON_AddObjectToObject(document, "validity");
  cJSON_AddBoolToObject(validity, "air_temperature_c", input.validity.air_temperature);
  cJSON_AddBoolToObject(validity, "air_humidity_pct", input.validity.air_humidity);
  cJSON_AddBoolToObject(validity, "co2_ppm", input.validity.co2);
  cJSON_AddBoolToObject(validity, "soil_moisture_pct", input.validity.soil_moisture);
  cJSON_AddBoolToObject(validity, "outside_temperature_c", input.validity.outside_temperature);
  cJSON_AddBoolToObject(validity, "outside_humidity_pct", input.validity.outside_humidity);
  cJSON_AddBoolToObject(validity, "outside_co2_ppm", input.validity.outside_co2);

  cJSON* targets = cJSON_AddObjectToObject(document, "targets");
  cJSON_AddNumberToObject(targets, "air_temperature_c", input.targets.air_temperature_c);
  cJSON_AddNumberToObject(targets, "air_humidity_pct", input.targets.air_humidity_pct);
  cJSON_AddNumberToObject(targets, "co2_ppm", input.targets.co2_ppm);
  cJSON_AddNumberToObject(targets, "soil_moisture_pct", input.targets.soil_moisture_pct);

  addActuatorAvailability(document, input.actuators);
}

bool parseLoadScenario(const cJSON* root, control::ControllerInput& scenario,
                       std::uint32_t& seed) noexcept {
  const cJSON* sensors = objectItem(root, control::schema::kWireRootSensors);
  const cJSON* validity = objectItem(root, control::schema::kWireRootValidity);
  const cJSON* environment = objectItem(root, control::schema::kWireRootEnvironment);
  const cJSON* cultivation = objectItem(root, control::schema::kWireRootCultivation);
  const cJSON* actuators = objectItem(root, control::schema::kWireRootActuators);
  const cJSON* targets = objectItem(root, control::schema::kWireRootTargets);
  const cJSON* previous = objectItem(root, control::schema::kWireRootPrevious);
  const cJSON* safety = item(root, "safety");
  return readUnsigned(root, "seed", seed) && parseSensors(sensors, scenario.sensors) &&
         parseValidity(validity, scenario.validity) &&
         parseEnvironment(environment, scenario.environment) &&
         parseCultivation(cultivation, scenario.cultivation) &&
         parseActuators(actuators, scenario.actuators) &&
         parseTargets(targets, scenario.targets, true) &&
         parsePrevious(previous, scenario.previous) && parseSafety(safety, scenario.safety);
}

bool parseStepOverrides(const cJSON* root, control::SensorState& sensors,
                        control::SensorValidity& validity,
                        control::ActuatorCapabilities& actuators, bool& has_sensors,
                        bool& has_validity, bool& has_actuators) noexcept {
  const cJSON* sensors_json = item(root, control::schema::kWireRootSensors);
  const cJSON* validity_json = item(root, control::schema::kWireRootValidity);
  const cJSON* actuators_json = objectItem(root, control::schema::kWireRootActuators);
  has_sensors = sensors_json != nullptr && !cJSON_IsNull(sensors_json);
  has_validity = validity_json != nullptr && !cJSON_IsNull(validity_json);
  has_actuators = actuators_json != nullptr && !cJSON_IsNull(actuators_json);
  if (has_sensors && !parseSensors(sensors_json, sensors)) {
    return false;
  }
  if (has_validity && !parseValidity(validity_json, validity)) {
    return false;
  }
  if (has_actuators && !parseActuators(actuators_json, actuators)) {
    return false;
  }
  return true;
}

bool parseTargetPatch(const cJSON* root, control::ControlTargets& targets) noexcept {
  return parseTargets(root, targets, false);
}

bool parseSeedValue(const cJSON* root, std::uint32_t& seed) noexcept {
  return readUnsigned(root, "value", seed);
}

cJSON* buildScenarioDocument(const control::ControllerInput& input,
                             std::uint32_t seed) noexcept {
  cJSON* document = cJSON_CreateObject();
  if (document == nullptr) {
    return nullptr;
  }
  cJSON_AddStringToObject(document, "type", "scenario");
  cJSON_AddNumberToObject(document, "schema_version", control::schema::kSchemaVersion);
  cJSON_AddStringToObject(document, "schema_hash", control::schema::kSchemaHash);
  cJSON_AddNumberToObject(document, "seed", seed);
  cJSON* scenario = cJSON_AddObjectToObject(document, "scenario");
  addScenarioSnapshot(scenario, input);
  return document;
}

}  // namespace wire
}  // namespace demo
}  // namespace growbox