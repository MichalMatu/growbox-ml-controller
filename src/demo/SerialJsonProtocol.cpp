#include "SerialJsonProtocol.h"

#include "EnvironmentSchema.h"

#include <cJSON.h>
#include <driver/usb_serial_jtag.h>

#include <cmath>
#include <cstring>
#include <limits>

namespace growbox {
namespace demo {
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

bool readBool(const cJSON* object, const char* key, bool& destination) noexcept {
  const cJSON* value = item(object, key);
  if (!cJSON_IsBool(value)) {
    return false;
  }
  destination = cJSON_IsTrue(value);
  return true;
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
                         sensors.outside_humidity_pct);
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
                  validity.outside_humidity);
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

const char* controlTypeName(control::ActuatorControlType type) noexcept {
  return type == control::ActuatorControlType::Pwm ? "pwm" : "binary";
}

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

}  // namespace

esp_err_t SerialJsonProtocol::begin() noexcept {
  if (!usb_serial_jtag_is_driver_installed()) {
    usb_serial_jtag_driver_config_t config = USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();
    config.tx_buffer_size = 4096U;
    config.rx_buffer_size = 4096U;
    const esp_err_t error = usb_serial_jtag_driver_install(&config);
    if (error != ESP_OK) {
      return error;
    }
  }

  std::uint8_t discard[128]{};
  while (usb_serial_jtag_read_bytes(discard, sizeof(discard), 0) > 0) {
  }
  return ESP_OK;
}

void SerialJsonProtocol::poll(DummyEnvironmentSimulator& simulator,
                              DemoRuntimeState& runtime) noexcept {
  std::uint8_t buffer[128]{};
  const int received = usb_serial_jtag_read_bytes(buffer, sizeof(buffer), 0);
  if (received <= 0) {
    return;
  }

  for (int index = 0; index < received; ++index) {
    const char character = static_cast<char>(buffer[index]);
    if (character == '\r') {
      continue;
    }
    if (character == '\n') {
      if (discarding_) {
        emitError("line_too_long", "input exceeds the bounded line buffer");
      } else if (length_ > 0U) {
        line_[length_] = '\0';
        processLine(simulator, runtime);
      }
      length_ = 0U;
      discarding_ = false;
      continue;
    }
    if (discarding_) {
      continue;
    }
    if (length_ >= kMaximumLineBytes) {
      discarding_ = true;
      length_ = 0U;
      continue;
    }
    line_[length_++] = character;
  }
}

void SerialJsonProtocol::processLine(DummyEnvironmentSimulator& simulator,
                                     DemoRuntimeState& runtime) noexcept {
  cJSON* root = cJSON_ParseWithLength(line_, length_);
  if (!cJSON_IsObject(root)) {
    cJSON_Delete(root);
    emitError("invalid_json", "input must be a valid JSON object");
    return;
  }

  const char* command = readString(root, "command");
  if (command == nullptr || command[0] == '\0') {
    cJSON_Delete(root);
    emitError("missing_command", "command must be a non-empty string");
    return;
  }

  if (std::strcmp(command, "status") == 0) {
    emitStatus(simulator, runtime);
    cJSON_Delete(root);
    return;
  }
  if (std::strcmp(command, "reset") == 0) {
    simulator.reset(simulator.seed());
    runtime.step = 0U;
    runtime.step_requested = false;
    runtime.controller_reset_requested = true;
    emitAck(command);
    cJSON_Delete(root);
    return;
  }
  if (std::strcmp(command, "seed") == 0) {
    std::uint32_t seed = 0U;
    if (!readUnsigned(root, "value", seed)) {
      cJSON_Delete(root);
      emitError("invalid_seed", "value must be an unsigned integer");
      return;
    }
    simulator.setSeed(seed);
    emitAck(command);
    cJSON_Delete(root);
    return;
  }
  if (std::strcmp(command, "pause") == 0) {
    runtime.paused = true;
    emitAck(command);
    cJSON_Delete(root);
    return;
  }
  if (std::strcmp(command, "resume") == 0) {
    runtime.paused = false;
    emitAck(command);
    cJSON_Delete(root);
    return;
  }
  if (std::strcmp(command, "mode") == 0) {
    const char* value = readString(root, "value");
    if (value != nullptr && std::strcmp(value, "closed_loop") == 0) {
      runtime.mode = DemoMode::ClosedLoop;
    } else if (value != nullptr && std::strcmp(value, "replay") == 0) {
      runtime.mode = DemoMode::Replay;
      runtime.paused = true;
    } else {
      cJSON_Delete(root);
      emitError("invalid_mode", "value must be closed_loop or replay");
      return;
    }
    emitAck(command);
    cJSON_Delete(root);
    return;
  }
  if (std::strcmp(command, "target") == 0) {
    control::ControlTargets targets = simulator.input().targets;
    if (!parseTargets(root, targets, false)) {
      cJSON_Delete(root);
      emitError("invalid_target", "provide at least one finite target field");
      return;
    }
    simulator.setTargets(targets);
    emitAck(command);
    cJSON_Delete(root);
    return;
  }
  if (std::strcmp(command, "step") == 0) {
    const cJSON* sensors_json = item(root, control::schema::kWireRootSensors);
    const cJSON* validity_json = item(root, control::schema::kWireRootValidity);
    const cJSON* actuators_json = objectItem(root, control::schema::kWireRootActuators);
    const bool has_sensors = sensors_json != nullptr && !cJSON_IsNull(sensors_json);
    const bool has_validity = validity_json != nullptr && !cJSON_IsNull(validity_json);
    const bool has_actuators = actuators_json != nullptr && !cJSON_IsNull(actuators_json);
    if (has_sensors || has_validity) {
      control::SensorState sensors = simulator.input().sensors;
      control::SensorValidity validity = simulator.input().validity;
      if (!parseSensors(sensors_json, sensors) || !parseValidity(validity_json, validity)) {
        cJSON_Delete(root);
        emitError("invalid_step", "sensors and validity must be complete");
        return;
      }
      simulator.setSensors(sensors, validity);
    }
    if (has_actuators) {
      control::ActuatorCapabilities actuators{};
      if (!parseActuators(actuators_json, actuators)) {
        cJSON_Delete(root);
        emitError("invalid_step", "actuators must be complete and finite");
        return;
      }
      simulator.setActuators(actuators);
      runtime.controller_reset_requested = true;
    }
    runtime.step_requested = true;
    cJSON_Delete(root);
    return;
  }
  if (std::strcmp(command, "load_scenario") == 0) {
    control::ControllerInput scenario{};
    std::uint32_t seed = 0U;
    const cJSON* sensors = objectItem(root, control::schema::kWireRootSensors);
    const cJSON* validity = objectItem(root, control::schema::kWireRootValidity);
    const cJSON* environment = objectItem(root, control::schema::kWireRootEnvironment);
    const cJSON* cultivation = objectItem(root, control::schema::kWireRootCultivation);
    const cJSON* actuators = objectItem(root, control::schema::kWireRootActuators);
    const cJSON* targets = objectItem(root, control::schema::kWireRootTargets);
    const cJSON* previous = objectItem(root, control::schema::kWireRootPrevious);
    if (!readUnsigned(root, "seed", seed) || !parseSensors(sensors, scenario.sensors) ||
        !parseValidity(validity, scenario.validity) ||
        !parseEnvironment(environment, scenario.environment) ||
        !parseCultivation(cultivation, scenario.cultivation) ||
        !parseActuators(actuators, scenario.actuators) ||
        !parseTargets(targets, scenario.targets, true) ||
        !parsePrevious(previous, scenario.previous)) {
      cJSON_Delete(root);
      emitError("invalid_scenario", "scenario fields must be complete and finite");
      return;
    }
    simulator.load(scenario, seed);
    runtime.step = 0U;
    runtime.step_requested = false;
    runtime.controller_reset_requested = true;
    emitAck(command);
    cJSON_Delete(root);
    return;
  }

  char unsupported[kMaximumLineBytes + 1U]{};
  std::strncpy(unsupported, command, kMaximumLineBytes);
  cJSON_Delete(root);
  emitError("unsupported_command", unsupported);
}

void SerialJsonProtocol::emitError(const char* code, const char* message) const noexcept {
  cJSON* document = cJSON_CreateObject();
  if (document == nullptr) {
    return;
  }
  cJSON_AddStringToObject(document, "type", "error");
  cJSON_AddNumberToObject(document, "schema_version", control::schema::kSchemaVersion);
  cJSON_AddStringToObject(document, "schema_hash", control::schema::kSchemaHash);
  cJSON_AddStringToObject(document, "code", code != nullptr ? code : "unknown_error");
  cJSON_AddStringToObject(document, "message", message != nullptr ? message : "");
  writeJson(document);
}

void SerialJsonProtocol::emitAck(const char* command) const noexcept {
  cJSON* document = cJSON_CreateObject();
  if (document == nullptr) {
    return;
  }
  cJSON_AddStringToObject(document, "type", "ack");
  cJSON_AddNumberToObject(document, "schema_version", control::schema::kSchemaVersion);
  cJSON_AddStringToObject(document, "schema_hash", control::schema::kSchemaHash);
  cJSON_AddStringToObject(document, "command", command != nullptr ? command : "");
  writeJson(document);
}

void SerialJsonProtocol::emitStatus(const DummyEnvironmentSimulator& simulator,
                                    const DemoRuntimeState& runtime) const noexcept {
  cJSON* document = cJSON_CreateObject();
  if (document == nullptr) {
    return;
  }
  cJSON_AddStringToObject(document, "type", "status");
  cJSON_AddNumberToObject(document, "schema_version", control::schema::kSchemaVersion);
  cJSON_AddStringToObject(document, "schema_hash", control::schema::kSchemaHash);
  cJSON_AddStringToObject(document, "mode",
                          runtime.mode == DemoMode::ClosedLoop ? "closed_loop" : "replay");
  cJSON_AddBoolToObject(document, "paused", runtime.paused);
  cJSON_AddNumberToObject(document, "step", runtime.step);
  cJSON_AddNumberToObject(document, "seed", simulator.seed());
  cJSON_AddNumberToObject(document, "simulated_time_s",
                          simulator.input().monotonic_time_ms / 1000U);
  cJSON* scenario = cJSON_AddObjectToObject(document, "scenario");
  addScenarioSnapshot(scenario, simulator.input());
  writeJson(document);
}

void SerialJsonProtocol::writeJson(cJSON* document) const noexcept {
  if (document == nullptr) {
    return;
  }
  char* encoded = cJSON_PrintUnformatted(document);
  if (encoded != nullptr) {
    usb_serial_jtag_write_bytes(encoded, std::strlen(encoded), 0);
    usb_serial_jtag_write_bytes("\n", 1U, 0);
    cJSON_free(encoded);
  }
  cJSON_Delete(document);
}

}  // namespace demo
}  // namespace growbox
