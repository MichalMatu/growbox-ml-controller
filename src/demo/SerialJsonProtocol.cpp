#include "SerialJsonProtocol.h"

#include "EnvironmentSchema.h"

#include <ArduinoJson.h>

#include <cmath>
#include <cstring>

namespace growbox {
namespace demo {

namespace {

using ArduinoJson::JsonDocument;
using ArduinoJson::JsonObjectConst;
using ArduinoJson::JsonVariantConst;
using control::schema::FeatureIndex;

bool readFiniteFloat(JsonObjectConst object, const char* key, float& destination) noexcept {
  const JsonVariantConst value = object[key];
  if (value.isNull() || !value.is<float>()) {
    return false;
  }
  const float parsed = value.as<float>();
  if (!std::isfinite(parsed)) {
    return false;
  }
  destination = parsed;
  return true;
}

bool readBool(JsonObjectConst object, const char* key, bool& destination) noexcept {
  const JsonVariantConst value = object[key];
  if (!value.is<bool>()) {
    return false;
  }
  destination = value.as<bool>();
  return true;
}

bool parseSensors(JsonObjectConst object, control::SensorState& sensors) noexcept {
  return readFiniteFloat(object, control::schema::wireKey(FeatureIndex::AirTemperatureC),
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

bool parseValidity(JsonObjectConst object, control::SensorValidity& validity) noexcept {
  return readBool(object, control::schema::wireKey(FeatureIndex::AirTemperatureValid),
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

bool parseEnvironment(JsonObjectConst object, control::EnvironmentConfig& config) noexcept {
  return readFiniteFloat(object, control::schema::wireKey(FeatureIndex::GrowboxVolumeM3),
                         config.growbox_volume_m3) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::ThermalMassJPerK),
                         config.thermal_mass_j_per_k) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::HeatLossWPerK),
                         config.heat_loss_w_per_k) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::AirLeakRateAch),
                         config.air_leak_rate_ach);
}

bool parseCultivation(JsonObjectConst object, control::CultivationConfig& config) noexcept {
  return readFiniteFloat(object, control::schema::wireKey(FeatureIndex::PotVolumeL),
                         config.pot_volume_l) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::SubstrateWaterCapacityMl),
                         config.substrate_water_capacity_ml) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::TranspirationFactor),
                         config.transpiration_factor);
}

bool parseTargets(JsonObjectConst object, control::ControlTargets& targets,
                  bool require_all) noexcept {
  bool parsed_any = false;
  auto read_optional = [&](const char* key, float& destination) {
    if (object[key].isNull()) {
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

bool parsePrevious(JsonObjectConst object, control::PreviousControlState& previous) noexcept {
  return readFiniteFloat(object, control::schema::wireKey(FeatureIndex::PreviousHeater),
                         previous.heater) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::PreviousFan),
                         previous.fan) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::PreviousHumidifier),
                         previous.humidifier) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::PreviousIrrigation),
                         previous.irrigation);
}

bool parseActuators(JsonObjectConst object, control::ActuatorCapabilities& actuators) noexcept {
  const JsonObjectConst heater = object[control::schema::kWireObjectHeater].as<JsonObjectConst>();
  const JsonObjectConst fan = object[control::schema::kWireObjectFan].as<JsonObjectConst>();
  const JsonObjectConst humidifier =
      object[control::schema::kWireObjectHumidifier].as<JsonObjectConst>();
  const JsonObjectConst irrigation =
      object[control::schema::kWireObjectIrrigation].as<JsonObjectConst>();
  if (heater.isNull() || fan.isNull() || humidifier.isNull() || irrigation.isNull()) {
    return false;
  }

  const char* control_type = heater[control::schema::wireKey(FeatureIndex::HeaterControlType)] | "";
  if (std::strcmp(control_type, "binary") == 0) {
    actuators.heater.control_type = control::ActuatorControlType::Binary;
  } else if (std::strcmp(control_type, "pwm") == 0) {
    actuators.heater.control_type = control::ActuatorControlType::Pwm;
  } else {
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

void serializeLine(Stream& stream, JsonDocument& document) noexcept {
  serializeJson(document, stream);
  stream.write('\n');
}

} // namespace

void SerialJsonProtocol::poll(Stream& stream, DummyEnvironmentSimulator& simulator,
                              DemoRuntimeState& runtime) noexcept {
  while (stream.available() > 0) {
    const int next = stream.read();
    if (next < 0) {
      return;
    }
    const char character = static_cast<char>(next);
    if (character == '\r') {
      continue;
    }
    if (character == '\n') {
      if (discarding_) {
        emitError(stream, "line_too_long", "input exceeds the bounded line buffer");
      } else if (length_ > 0U) {
        line_[length_] = '\0';
        processLine(stream, simulator, runtime);
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

void SerialJsonProtocol::processLine(Stream& stream, DummyEnvironmentSimulator& simulator,
                                     DemoRuntimeState& runtime) noexcept {
  JsonDocument document;
  const DeserializationError error = deserializeJson(document, line_, length_);
  if (error) {
    emitError(stream, "invalid_json", error.c_str());
    return;
  }
  const JsonObjectConst root = document.as<JsonObjectConst>();
  const char* command = root["command"] | "";
  if (command[0] == '\0') {
    emitError(stream, "missing_command", "command must be a non-empty string");
    return;
  }

  if (std::strcmp(command, "status") == 0) {
    emitStatus(stream, simulator, runtime);
    return;
  }
  if (std::strcmp(command, "reset") == 0) {
    simulator.reset(simulator.seed());
    runtime.step = 0U;
    runtime.step_requested = false;
    runtime.controller_reset_requested = true;
    emitAck(stream, command);
    return;
  }
  if (std::strcmp(command, "seed") == 0) {
    if (!root["value"].is<std::uint32_t>()) {
      emitError(stream, "invalid_seed", "value must be an unsigned integer");
      return;
    }
    simulator.setSeed(root["value"].as<std::uint32_t>());
    emitAck(stream, command);
    return;
  }
  if (std::strcmp(command, "pause") == 0) {
    runtime.paused = true;
    emitAck(stream, command);
    return;
  }
  if (std::strcmp(command, "resume") == 0) {
    runtime.paused = false;
    emitAck(stream, command);
    return;
  }
  if (std::strcmp(command, "mode") == 0) {
    const char* value = root["value"] | "";
    if (std::strcmp(value, "closed_loop") == 0) {
      runtime.mode = DemoMode::ClosedLoop;
    } else if (std::strcmp(value, "replay") == 0) {
      runtime.mode = DemoMode::Replay;
      runtime.paused = true;
    } else {
      emitError(stream, "invalid_mode", "value must be closed_loop or replay");
      return;
    }
    emitAck(stream, command);
    return;
  }
  if (std::strcmp(command, "target") == 0) {
    control::ControlTargets targets = simulator.input().targets;
    if (!parseTargets(root, targets, false)) {
      emitError(stream, "invalid_target", "provide at least one finite target field");
      return;
    }
    simulator.setTargets(targets);
    emitAck(stream, command);
    return;
  }
  if (std::strcmp(command, "step") == 0) {
    if (!root[control::schema::kWireRootSensors].isNull() ||
        !root[control::schema::kWireRootValidity].isNull()) {
      control::SensorState sensors = simulator.input().sensors;
      control::SensorValidity validity = simulator.input().validity;
      const JsonObjectConst sensors_json =
          root[control::schema::kWireRootSensors].as<JsonObjectConst>();
      const JsonObjectConst validity_json =
          root[control::schema::kWireRootValidity].as<JsonObjectConst>();
      if (sensors_json.isNull() || validity_json.isNull() || !parseSensors(sensors_json, sensors) ||
          !parseValidity(validity_json, validity)) {
        emitError(stream, "invalid_step", "sensors and validity must be complete");
        return;
      }
      simulator.setSensors(sensors, validity);
    }
    runtime.step_requested = true;
    return;
  }
  if (std::strcmp(command, "load_scenario") == 0) {
    control::ControllerInput scenario{};
    const JsonObjectConst sensors = root[control::schema::kWireRootSensors].as<JsonObjectConst>();
    const JsonObjectConst validity = root[control::schema::kWireRootValidity].as<JsonObjectConst>();
    const JsonObjectConst environment =
        root[control::schema::kWireRootEnvironment].as<JsonObjectConst>();
    const JsonObjectConst cultivation =
        root[control::schema::kWireRootCultivation].as<JsonObjectConst>();
    const JsonObjectConst actuators =
        root[control::schema::kWireRootActuators].as<JsonObjectConst>();
    const JsonObjectConst targets = root[control::schema::kWireRootTargets].as<JsonObjectConst>();
    const JsonObjectConst previous = root[control::schema::kWireRootPrevious].as<JsonObjectConst>();
    if (!root["seed"].is<std::uint32_t>() || sensors.isNull() || validity.isNull() ||
        environment.isNull() || cultivation.isNull() || actuators.isNull() || targets.isNull() ||
        previous.isNull() || !parseSensors(sensors, scenario.sensors) ||
        !parseValidity(validity, scenario.validity) ||
        !parseEnvironment(environment, scenario.environment) ||
        !parseCultivation(cultivation, scenario.cultivation) ||
        !parseActuators(actuators, scenario.actuators) ||
        !parseTargets(targets, scenario.targets, true) ||
        !parsePrevious(previous, scenario.previous)) {
      emitError(stream, "invalid_scenario", "scenario fields must be complete and finite");
      return;
    }
    simulator.load(scenario, root["seed"].as<std::uint32_t>());
    runtime.step = 0U;
    runtime.step_requested = false;
    runtime.controller_reset_requested = true;
    emitAck(stream, command);
    return;
  }

  emitError(stream, "unsupported_command", command);
}

void SerialJsonProtocol::emitError(Stream& stream, const char* code,
                                   const char* message) const noexcept {
  JsonDocument document;
  document["type"] = "error";
  document["schema_version"] = control::schema::kSchemaVersion;
  document["schema_hash"] = control::schema::kSchemaHash;
  document["code"] = code;
  document["message"] = message;
  serializeLine(stream, document);
}

void SerialJsonProtocol::emitAck(Stream& stream, const char* command) const noexcept {
  JsonDocument document;
  document["type"] = "ack";
  document["schema_version"] = control::schema::kSchemaVersion;
  document["schema_hash"] = control::schema::kSchemaHash;
  document["command"] = command;
  serializeLine(stream, document);
}

void SerialJsonProtocol::emitStatus(Stream& stream, const DummyEnvironmentSimulator& simulator,
                                    const DemoRuntimeState& runtime) const noexcept {
  JsonDocument document;
  document["type"] = "status";
  document["schema_version"] = control::schema::kSchemaVersion;
  document["schema_hash"] = control::schema::kSchemaHash;
  document["mode"] = runtime.mode == DemoMode::ClosedLoop ? "closed_loop" : "replay";
  document["paused"] = runtime.paused;
  document["step"] = runtime.step;
  document["seed"] = simulator.seed();
  document["simulated_time_s"] = simulator.input().monotonic_time_ms / 1000U;
  serializeLine(stream, document);
}

} // namespace demo
} // namespace growbox
