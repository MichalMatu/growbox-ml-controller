#include <cJSON.h>
#include <driver/uart.h>
#include <esp_err.h>
#include <esp_heap_caps.h>
#include <esp_idf_version.h>
#include <esp_timer.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include "EnvironmentController.h"
#include "EnvironmentSchema.h"
#include "ModelRuntime.h"
#include "SafetySupervisor.h"
#include "demo/DummyEnvironmentSimulator.h"
#include "demo/SerialJsonProtocol.h"

#include <array>
#include <cstdint>
#include <cstring>

#ifndef GROWBOX_BOARD_PROFILE
#define GROWBOX_BOARD_PROFILE "esp32s3-devkitc1-n8"
#endif

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

constexpr uart_port_t kSerialPort = UART_NUM_0;
constexpr int kSerialBaud = 115200;
constexpr std::uint64_t kRealStepIntervalMs = 1000U;
constexpr float kSimulationStepSeconds = 10.0f;

DummyEnvironmentSimulator simulator;
EnvironmentController controller;
SerialJsonProtocol protocol{kSerialPort};
DemoRuntimeState runtime;
std::uint64_t last_real_step_ms = 0U;

std::uint64_t monotonicMilliseconds() noexcept {
  return static_cast<std::uint64_t>(esp_timer_get_time()) / 1000U;
}

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

void writeLine(cJSON* document) noexcept {
  if (document == nullptr) {
    return;
  }
  char* encoded = cJSON_PrintUnformatted(document);
  if (encoded != nullptr) {
    uart_write_bytes(kSerialPort, encoded, std::strlen(encoded));
    uart_write_bytes(kSerialPort, "\n", 1U);
    cJSON_free(encoded);
  }
  cJSON_Delete(document);
}

void emitStartup() noexcept {
  cJSON* document = cJSON_CreateObject();
  if (document == nullptr) {
    return;
  }
  cJSON_AddStringToObject(document, "type", "startup");
  cJSON_AddStringToObject(document, "framework", "esp-idf");
  cJSON_AddStringToObject(document, "idf_version", IDF_VER);
  cJSON_AddNumberToObject(document, "schema_version", growbox::control::schema::kSchemaVersion);
  cJSON_AddStringToObject(document, "schema_hash", growbox::control::schema::kSchemaHash);
  cJSON_AddStringToObject(document, "model_version", ModelRuntime::modelVersion());
  cJSON_AddStringToObject(document, "model_schema_hash", ModelRuntime::modelSchemaHash());
  cJSON_AddBoolToObject(document, "model_compatible", ModelRuntime::isCompatible());
  cJSON_AddNumberToObject(document, "model_inputs", ModelRuntime::inputCount());
  cJSON_AddNumberToObject(document, "model_outputs", ModelRuntime::outputCount());
  cJSON_AddStringToObject(document, "board_profile", GROWBOX_BOARD_PROFILE);
  cJSON_AddBoolToObject(document, "gpio_control", false);
  cJSON_AddNumberToObject(document, "real_step_interval_ms", kRealStepIntervalMs);
  cJSON_AddNumberToObject(document, "simulation_step_s", kSimulationStepSeconds);
  cJSON_AddNumberToObject(document, "seed", simulator.seed());
  cJSON_AddNumberToObject(document, "free_heap", heap_caps_get_free_size(MALLOC_CAP_8BIT));
  cJSON_AddNumberToObject(document, "free_psram", heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
  writeLine(document);
}

void emitDecision(const ControllerOutput& output, ControllerStatus status) noexcept {
  const auto& input = simulator.input();
  cJSON* document = cJSON_CreateObject();
  if (document == nullptr) {
    return;
  }

  cJSON_AddStringToObject(document, "type", "decision");
  cJSON_AddNumberToObject(document, "schema_version", growbox::control::schema::kSchemaVersion);
  cJSON_AddStringToObject(document, "schema_hash", growbox::control::schema::kSchemaHash);
  cJSON_AddStringToObject(document, "model_version", ModelRuntime::modelVersion());
  cJSON_AddNumberToObject(document, "step", runtime.step);
  cJSON_AddNumberToObject(document, "simulated_time_s", input.monotonic_time_ms / 1000U);

  cJSON* sensors = cJSON_AddObjectToObject(document, "sensors");
  cJSON_AddNumberToObject(sensors, "air_temperature_c", input.sensors.air_temperature_c);
  cJSON_AddNumberToObject(sensors, "air_humidity_pct", input.sensors.air_humidity_pct);
  cJSON_AddNumberToObject(sensors, "co2_ppm", input.sensors.co2_ppm);
  cJSON_AddNumberToObject(sensors, "soil_moisture_pct", input.sensors.soil_moisture_pct);
  cJSON_AddNumberToObject(sensors, "outside_temperature_c", input.sensors.outside_temperature_c);
  cJSON_AddNumberToObject(sensors, "outside_humidity_pct", input.sensors.outside_humidity_pct);

  cJSON* validity = cJSON_AddObjectToObject(document, "validity");
  cJSON_AddBoolToObject(validity, "air_temperature_c", input.validity.air_temperature);
  cJSON_AddBoolToObject(validity, "air_humidity_pct", input.validity.air_humidity);
  cJSON_AddBoolToObject(validity, "co2_ppm", input.validity.co2);
  cJSON_AddBoolToObject(validity, "soil_moisture_pct", input.validity.soil_moisture);
  cJSON_AddBoolToObject(validity, "outside_temperature_c", input.validity.outside_temperature);
  cJSON_AddBoolToObject(validity, "outside_humidity_pct", input.validity.outside_humidity);

  cJSON* targets = cJSON_AddObjectToObject(document, "targets");
  cJSON_AddNumberToObject(targets, "air_temperature_c", input.targets.air_temperature_c);
  cJSON_AddNumberToObject(targets, "air_humidity_pct", input.targets.air_humidity_pct);
  cJSON_AddNumberToObject(targets, "co2_ppm", input.targets.co2_ppm);
  cJSON_AddNumberToObject(targets, "soil_moisture_pct", input.targets.soil_moisture_pct);

  cJSON* raw = cJSON_AddObjectToObject(document, "raw_output");
  cJSON_AddNumberToObject(raw, "heater", output.raw.heater);
  cJSON_AddNumberToObject(raw, "fan", output.raw.fan);
  cJSON_AddNumberToObject(raw, "humidifier", output.raw.humidifier);
  cJSON_AddNumberToObject(raw, "irrigation", output.raw.irrigation);

  cJSON* safe = cJSON_AddObjectToObject(document, "safe_output");
  cJSON_AddNumberToObject(safe, "heater", output.safe.heater);
  cJSON_AddNumberToObject(safe, "fan", output.safe.fan);
  cJSON_AddNumberToObject(safe, "humidifier", output.safe.humidifier);
  cJSON_AddNumberToObject(safe, "irrigation", output.safe.irrigation);
  cJSON_AddNumberToObject(safe, "irrigation_pulse_s", output.safe.irrigation_pulse_s);

  cJSON* diagnostics = cJSON_AddObjectToObject(document, "diagnostics");
  cJSON_AddStringToObject(diagnostics, "controller_status", controllerStatusCode(status));
  cJSON_AddStringToObject(diagnostics, "inference_status",
                          modelStatusCode(output.diagnostics.model_status));
  cJSON_AddNumberToObject(diagnostics, "inference_us", output.diagnostics.inference_us);
  cJSON_AddBoolToObject(diagnostics, "safety_modified", output.diagnostics.safety.modified);
  cJSON_AddStringToObject(diagnostics, "safety_reason",
                          primarySafetyReason(output.diagnostics.safety.reason_mask));
  cJSON_AddNumberToObject(diagnostics, "safety_reason_mask",
                          output.diagnostics.safety.reason_mask);
  cJSON* output_reasons = cJSON_AddObjectToObject(diagnostics, "output_reason_masks");
  cJSON_AddNumberToObject(output_reasons, "heater",
                          output.diagnostics.safety.output_reason_masks[0]);
  cJSON_AddNumberToObject(output_reasons, "fan",
                          output.diagnostics.safety.output_reason_masks[1]);
  cJSON_AddNumberToObject(output_reasons, "humidifier",
                          output.diagnostics.safety.output_reason_masks[2]);
  cJSON_AddNumberToObject(output_reasons, "irrigation",
                          output.diagnostics.safety.output_reason_masks[3]);
  cJSON_AddNumberToObject(diagnostics, "free_heap", heap_caps_get_free_size(MALLOC_CAP_8BIT));
  cJSON_AddNumberToObject(diagnostics, "free_psram", heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
  writeLine(document);
}

void runControllerStep() noexcept {
  ControllerOutput output{};
  const std::int64_t started_us = esp_timer_get_time();
  const ControllerStatus status = controller.process(simulator.input(), output);
  const std::int64_t elapsed_us = esp_timer_get_time() - started_us;
  output.diagnostics.inference_us =
      elapsed_us > 0 ? static_cast<std::uint32_t>(elapsed_us) : 0U;
  emitDecision(output, status);

  if (runtime.mode == DemoMode::ClosedLoop) {
    simulator.advance(output.safe, kSimulationStepSeconds);
  } else {
    auto& input = simulator.input();
    input.previous.heater = output.safe.heater;
    input.previous.fan = output.safe.fan;
    input.previous.humidifier = output.safe.humidifier;
    input.previous.irrigation = output.safe.irrigation;
    input.monotonic_time_ms +=
        static_cast<std::uint64_t>(kSimulationStepSeconds * 1000.0f);
  }
  ++runtime.step;
}

}  // namespace

extern "C" void app_main() {
  ESP_ERROR_CHECK(protocol.begin(kSerialBaud));
  vTaskDelay(pdMS_TO_TICKS(250));
  emitStartup();
  last_real_step_ms = monotonicMilliseconds();

  while (true) {
    protocol.poll(simulator, runtime);
    if (runtime.controller_reset_requested) {
      controller.resetSafetyState();
      runtime.controller_reset_requested = false;
    }

    const std::uint64_t now_ms = monotonicMilliseconds();
    const bool automatic_step = runtime.mode == DemoMode::ClosedLoop && !runtime.paused &&
                                now_ms - last_real_step_ms >= kRealStepIntervalMs;
    if (automatic_step || runtime.step_requested) {
      runtime.step_requested = false;
      last_real_step_ms = now_ms;
      runControllerStep();
    }
    vTaskDelay(1);
  }
}
