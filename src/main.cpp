#include <Arduino.h>
#include <ArduinoJson.h>

#include "demo/DummyEnvironmentSimulator.h"
#include "EnvironmentController.h"
#include "EnvironmentSchema.h"
#include "ModelRuntime.h"
#include "SafetySupervisor.h"
#include "demo/SerialJsonProtocol.h"

#include <array>
#include <cstdint>

namespace {

using growbox::control::ControllerOutput;
using growbox::control::ControllerStatus;
using growbox::control::EnvironmentController;
using growbox::control::ModelRuntime;
using growbox::control::ModelStatus;
using growbox::control::SafetyReason;
using growbox::control::SafetySupervisor;
using growbox::demo::DemoMode;
using growbox::demo::DemoRuntimeState;
using growbox::demo::DummyEnvironmentSimulator;
using growbox::demo::SerialJsonProtocol;

constexpr std::uint32_t kSerialBaud = 115200U;
constexpr std::uint32_t kRealStepIntervalMs = 1000U;
constexpr float kSimulationStepSeconds = 10.0f;

DummyEnvironmentSimulator simulator;
EnvironmentController controller;
SerialJsonProtocol protocol;
DemoRuntimeState runtime;
std::uint32_t last_real_step_ms = 0U;

const char* controllerStatusCode(ControllerStatus status) noexcept {
  switch (status) {
    case ControllerStatus::Ok:
      return "ok";
    case ControllerStatus::EncoderError:
      return "encoder_error";
    case ControllerStatus::ModelError:
      return "model_error";
  }
  return "unknown";
}

const char* modelStatusCode(ModelStatus status) noexcept {
  switch (status) {
    case ModelStatus::Ok:
      return "ok";
    case ModelStatus::SchemaMismatch:
      return "schema_mismatch";
    case ModelStatus::ShapeMismatch:
      return "shape_mismatch";
    case ModelStatus::NonFiniteInput:
      return "non_finite_input";
    case ModelStatus::InferenceFailure:
      return "inference_failure";
    case ModelStatus::NonFiniteOutput:
      return "non_finite_output";
  }
  return "unknown";
}

const char* primarySafetyReason(std::uint32_t mask) noexcept {
  constexpr std::array<SafetyReason, 15> reasons{{
      SafetyReason::NonFiniteInput,
      SafetyReason::ModelFailure,
      SafetyReason::SchemaMismatch,
      SafetyReason::NonFiniteModelOutput,
      SafetyReason::OutputClamped,
      SafetyReason::TemperatureUnavailable,
      SafetyReason::ActuatorUnavailable,
      SafetyReason::OverTemperature,
      SafetyReason::TemperatureAlarmFan,
      SafetyReason::PumpPulseLimited,
      SafetyReason::PumpMinimumInterval,
      SafetyReason::BinaryThreshold,
      SafetyReason::BinaryMinimumOn,
      SafetyReason::BinaryMinimumOff,
      SafetyReason::InvalidCapability,
  }};
  for (const SafetyReason reason : reasons) {
    if ((mask & growbox::control::reasonBit(reason)) != 0U) {
      return SafetySupervisor::reasonCode(reason);
    }
  }
  return SafetySupervisor::reasonCode(SafetyReason::None);
}

void writeLine(JsonDocument& document) {
  serializeJson(document, Serial);
  Serial.write('\n');
}

void emitStartup() {
  JsonDocument document;
  document["type"] = "startup";
  document["schema_version"] = growbox::control::schema::kSchemaVersion;
  document["schema_hash"] = growbox::control::schema::kSchemaHash;
  document["model_version"] = ModelRuntime::modelVersion();
  document["model_schema_hash"] = ModelRuntime::modelSchemaHash();
  document["model_compatible"] = ModelRuntime::isCompatible();
  document["model_inputs"] = ModelRuntime::inputCount();
  document["model_outputs"] = ModelRuntime::outputCount();
  document["board_profile"] = GROWBOX_BOARD_PROFILE;
  document["gpio_control"] = false;
  document["real_step_interval_ms"] = kRealStepIntervalMs;
  document["simulation_step_s"] = kSimulationStepSeconds;
  document["seed"] = simulator.seed();
  document["free_heap"] = ESP.getFreeHeap();
  document["free_psram"] = ESP.getFreePsram();
  writeLine(document);
}

void emitDecision(const ControllerOutput& output, ControllerStatus status) {
  const auto& input = simulator.input();
  JsonDocument document;
  document["type"] = "decision";
  document["schema_version"] = growbox::control::schema::kSchemaVersion;
  document["schema_hash"] = growbox::control::schema::kSchemaHash;
  document["model_version"] = ModelRuntime::modelVersion();
  document["step"] = runtime.step;
  document["simulated_time_s"] = input.monotonic_time_ms / 1000U;

  JsonObject sensors = document["sensors"].to<JsonObject>();
  sensors["air_temperature_c"] = input.sensors.air_temperature_c;
  sensors["air_humidity_pct"] = input.sensors.air_humidity_pct;
  sensors["co2_ppm"] = input.sensors.co2_ppm;
  sensors["soil_moisture_pct"] = input.sensors.soil_moisture_pct;
  sensors["outside_temperature_c"] = input.sensors.outside_temperature_c;
  sensors["outside_humidity_pct"] = input.sensors.outside_humidity_pct;

  JsonObject validity = document["validity"].to<JsonObject>();
  validity["air_temperature_c"] = input.validity.air_temperature;
  validity["air_humidity_pct"] = input.validity.air_humidity;
  validity["co2_ppm"] = input.validity.co2;
  validity["soil_moisture_pct"] = input.validity.soil_moisture;
  validity["outside_temperature_c"] = input.validity.outside_temperature;
  validity["outside_humidity_pct"] = input.validity.outside_humidity;

  JsonObject targets = document["targets"].to<JsonObject>();
  targets["air_temperature_c"] = input.targets.air_temperature_c;
  targets["air_humidity_pct"] = input.targets.air_humidity_pct;
  targets["co2_ppm"] = input.targets.co2_ppm;
  targets["soil_moisture_pct"] = input.targets.soil_moisture_pct;

  JsonObject raw = document["raw_output"].to<JsonObject>();
  raw["heater"] = output.raw.heater;
  raw["fan"] = output.raw.fan;
  raw["humidifier"] = output.raw.humidifier;
  raw["irrigation"] = output.raw.irrigation;

  JsonObject safe = document["safe_output"].to<JsonObject>();
  safe["heater"] = output.safe.heater;
  safe["fan"] = output.safe.fan;
  safe["humidifier"] = output.safe.humidifier;
  safe["irrigation"] = output.safe.irrigation;
  safe["irrigation_pulse_s"] = output.safe.irrigation_pulse_s;

  JsonObject diagnostics = document["diagnostics"].to<JsonObject>();
  diagnostics["controller_status"] = controllerStatusCode(status);
  diagnostics["inference_status"] = modelStatusCode(output.diagnostics.model_status);
  diagnostics["inference_us"] = output.diagnostics.inference_us;
  diagnostics["safety_modified"] = output.diagnostics.safety.modified;
  diagnostics["safety_reason"] =
      primarySafetyReason(output.diagnostics.safety.reason_mask);
  diagnostics["safety_reason_mask"] = output.diagnostics.safety.reason_mask;
  JsonObject output_reasons = diagnostics["output_reason_masks"].to<JsonObject>();
  output_reasons["heater"] = output.diagnostics.safety.output_reason_masks[0];
  output_reasons["fan"] = output.diagnostics.safety.output_reason_masks[1];
  output_reasons["humidifier"] = output.diagnostics.safety.output_reason_masks[2];
  output_reasons["irrigation"] = output.diagnostics.safety.output_reason_masks[3];
  diagnostics["free_heap"] = ESP.getFreeHeap();
  diagnostics["free_psram"] = ESP.getFreePsram();
  writeLine(document);
}

void runControllerStep() {
  ControllerOutput output{};
  const std::uint32_t started_us = micros();
  const ControllerStatus status = controller.process(simulator.input(), output);
  output.diagnostics.inference_us = micros() - started_us;
  emitDecision(output, status);

  if (runtime.mode == DemoMode::ClosedLoop) {
    simulator.advance(output.safe, kSimulationStepSeconds);
  } else {
    auto& input = simulator.input();
    input.previous.heater = output.safe.heater;
    input.previous.fan = output.safe.fan;
    input.previous.humidifier = output.safe.humidifier;
    input.previous.irrigation = output.safe.irrigation;
    input.monotonic_time_ms += static_cast<std::uint64_t>(kSimulationStepSeconds * 1000.0f);
  }
  ++runtime.step;
}

}  // namespace

void setup() {
  Serial.begin(kSerialBaud);
  delay(250);
  emitStartup();
  last_real_step_ms = millis();
}

void loop() {
  protocol.poll(Serial, simulator, runtime);
  if (runtime.controller_reset_requested) {
    controller.resetSafetyState();
    runtime.controller_reset_requested = false;
  }

  const std::uint32_t now_ms = millis();
  const bool automatic_step = runtime.mode == DemoMode::ClosedLoop && !runtime.paused &&
                              now_ms - last_real_step_ms >= kRealStepIntervalMs;
  if (automatic_step || runtime.step_requested) {
    runtime.step_requested = false;
    last_real_step_ms = now_ms;
    runControllerStep();
  }
  delay(1);
}
