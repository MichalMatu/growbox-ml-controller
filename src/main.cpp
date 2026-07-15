#include <cJSON.h>
#include <driver/usb_serial_jtag.h>
#include <esp_err.h>
#include <esp_heap_caps.h>
#include <esp_idf_version.h>
#include <esp_timer.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include "EnvironmentController.h"
#include "EnvironmentSchema.h"
#include "ModelRuntime.h"
#include "demo/DummyEnvironmentSimulator.h"
#include "demo/SerialJsonProtocol.h"
#include "demo/protocol/DecisionWireCodec.h"
#include "demo/protocol/JsonLineWriter.h"

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
using growbox::demo::DemoMode;
using growbox::demo::DemoRuntimeState;
using growbox::demo::DummyEnvironmentSimulator;
using growbox::demo::SerialJsonProtocol;
using growbox::demo::wire::DecisionEmitRequest;

constexpr std::uint64_t kRealStepIntervalMs = 1000U;
constexpr float kSimulationStepSeconds = 10.0f;

DummyEnvironmentSimulator simulator;
EnvironmentController controller;
SerialJsonProtocol protocol;
DemoRuntimeState runtime;
std::uint64_t last_real_step_ms = 0U;

std::uint64_t monotonicMilliseconds() noexcept {
  return static_cast<std::uint64_t>(esp_timer_get_time()) / 1000U;
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
  growbox::demo::wire::emitJsonDocument(document);
}

void runControllerStep() noexcept {
  ControllerOutput output{};
  const std::int64_t started_us = esp_timer_get_time();
  const ControllerStatus status = controller.process(simulator.input(), output);
  const std::int64_t elapsed_us = esp_timer_get_time() - started_us;
  output.diagnostics.inference_us =
      elapsed_us > 0 ? static_cast<std::uint32_t>(elapsed_us) : 0U;

  const DecisionEmitRequest request{&simulator.input(), &output, status, runtime.step};
  growbox::demo::wire::emitDecision(request);

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
  ESP_ERROR_CHECK(protocol.begin());
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