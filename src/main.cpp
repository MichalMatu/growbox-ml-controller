#ifndef GROWBOX_APP_CLIMATE_V6_FAKE
#define GROWBOX_APP_CLIMATE_V6_FAKE 0
#endif
#ifndef GROWBOX_APP_CLIMATE_V6_REAL_INPUTS
#define GROWBOX_APP_CLIMATE_V6_REAL_INPUTS 0
#endif
#ifndef GROWBOX_FIRMWARE_GIT_SHA
#define GROWBOX_FIRMWARE_GIT_SHA "unknown"
#endif

#include "climate/ClimateV6FakeRuntime.h"
#include "climate/ClimateV6RealInputRuntime.h"
#include "climate/runtime/Stage28eBreadcrumbs.h"
#include "climate/runtime/Stage28ePlatformDiagnostics.h"

#include <esp_core_dump.h>
#include <esp_err.h>

#include <cstddef>
#include <cstdint>
#include <cstdio>

namespace {

std::uint32_t g_runtime_entry_count = 0U;

const char* runtimeModeName() noexcept {
#if GROWBOX_APP_CLIMATE_V6_FAKE
  return "climate-v6-fake";
#elif GROWBOX_APP_CLIMATE_V6_REAL_INPUTS
  return "climate-v6-real-inputs";
#else
  return "legacy";
#endif
}

void emitCoreDumpBootDiagnostics() noexcept {
  std::size_t dump_address = 0U;
  std::size_t dump_size = 0U;
  const esp_err_t get_result = esp_core_dump_image_get(&dump_address, &dump_size);
  const bool present = get_result == ESP_OK && dump_size > 0U;
  const esp_err_t check_result = present ? esp_core_dump_image_check() : get_result;
  std::printf("stage28e_coredump present=%d valid=%d size=%lu get_err=%ld check_err=%ld\n",
              present, present && check_result == ESP_OK,
              static_cast<unsigned long>(dump_size), static_cast<long>(get_result),
              static_cast<long>(check_result));
}

void emitBreadcrumbBootDiagnostics() noexcept {
  using namespace growbox::app::climate_io::runtime;
  const Stage28eBreadcrumbState raw_previous = readStage28eBreadcrumb();
  const bool previous_valid = stage28eBreadcrumbValid(raw_previous);
  const Stage28eBreadcrumbState previous = previous_valid ? raw_previous : Stage28eBreadcrumbState{};
  std::printf(
      "stage28e_breadcrumb previous_valid=%d write_seq=%lu boot_seq=%lu boot_id=%08lx "
      "reset_reason=%ld last_log_seq=%lu last_log_uptime_ms=%llu last_log_module=%lu "
      "last_log_level=%lu fault_code=%lu fault_seq=%lu fault_uptime_ms=%llu "
      "arbiter_instance=%lu arbiter_constructions=%lu arbiter_transitions=%lu "
      "arbiter_dwell_holds=%lu arbiter_safety_overrides=%lu arbiter_continuity_faults=%lu\n",
      previous_valid, static_cast<unsigned long>(previous.write_sequence),
      static_cast<unsigned long>(previous.boot_sequence),
      static_cast<unsigned long>(previous.boot_id), static_cast<long>(previous.reset_reason),
      static_cast<unsigned long>(previous.last_log_sequence),
      static_cast<unsigned long long>(previous.last_log_uptime_ms),
      static_cast<unsigned long>(previous.last_log_module),
      static_cast<unsigned long>(previous.last_log_level),
      static_cast<unsigned long>(previous.last_fault_code),
      static_cast<unsigned long>(previous.last_fault_sequence),
      static_cast<unsigned long long>(previous.last_fault_uptime_ms),
      static_cast<unsigned long>(previous.arbiter_instance_id),
      static_cast<unsigned long>(previous.arbiter_construction_count),
      static_cast<unsigned long>(previous.arbiter_transition_count),
      static_cast<unsigned long>(previous.arbiter_dwell_hold_count),
      static_cast<unsigned long>(previous.arbiter_safety_override_count),
      static_cast<unsigned long>(previous.arbiter_continuity_fault_count));

  const BootIdentity& boot = bootIdentity(GROWBOX_FIRMWARE_GIT_SHA);
  beginStage28eBreadcrumb(boot.boot_id, boot.reset_reason);
}

void emitRuntimeLifecycleDiagnostics() noexcept {
  ++g_runtime_entry_count;
  std::printf("stage28e_runtime_lifecycle entry_count=%lu mode=%s\n",
              static_cast<unsigned long>(g_runtime_entry_count), runtimeModeName());
}

} // namespace

#if !GROWBOX_APP_CLIMATE_V6_FAKE && !GROWBOX_APP_CLIMATE_V6_REAL_INPUTS
#include <cJSON.h>
#include <driver/usb_serial_jtag.h>

#include <esp_idf_version.h>
#include <esp_timer.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include "EnvironmentController.h"
#include "EnvironmentTypes.h"
#include "ModelRuntime.h"
#include "demo/DummyEnvironmentSimulator.h"
#include "demo/SerialJsonProtocol.h"
#include "demo/protocol/DecisionWireCodec.h"
#include "demo/protocol/HeapDiagnostics.h"
#include "demo/protocol/JsonLineWriter.h"

#include <array>
#include <cstring>

#ifndef GROWBOX_BOARD_PROFILE
#define GROWBOX_BOARD_PROFILE "esp32s3-devkitc1-n16r8"
#endif

namespace {

using growbox::control::ControllerOutput;
using growbox::control::ControllerStatus;
using growbox::control::EnvironmentController;
using growbox::control::ModelRuntime;
using growbox::control::schema::OutputIndex;
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
  const auto heap = growbox::demo::wire::captureHeapSnapshot();
  cJSON_AddNumberToObject(document, "free_heap", heap.free_internal + heap.free_psram);
  cJSON_AddNumberToObject(document, "free_internal", heap.free_internal);
  cJSON_AddNumberToObject(document, "free_psram", heap.free_psram);
  cJSON_AddBoolToObject(document, "psram_enabled", heap.psram_enabled);
  growbox::demo::wire::emitJsonDocument(document);
}

void syncPreviousState(growbox::control::ControllerInput& input,
                       const growbox::control::SafeControlDecision& safe) noexcept {
  input.previous.heater = safe.heater;
  input.previous.fan = safe.fan;
  input.previous.humidifier = safe.humidifier;
  input.previous.dehumidifier = safe.dehumidifier;
  input.previous.cooler = safe.cooler;
  input.previous.co2_doser = safe.co2_doser;
  constexpr std::array<OutputIndex, growbox::control::kMaxPots> kZoneIrrigationOutputs{{
      OutputIndex::IrrigationPot1,
      OutputIndex::IrrigationPot2,
      OutputIndex::IrrigationPot3,
      OutputIndex::IrrigationPot4,
  }};
  for (std::size_t pot_index = 0U; pot_index < growbox::control::kMaxPots; ++pot_index) {
    input.pots[pot_index].previous_irrigation =
        growbox::control::safeOutputValue(safe, kZoneIrrigationOutputs[pot_index]);
  }
}

void runControllerStep() noexcept {
  ControllerOutput output{};
  const std::int64_t started_us = esp_timer_get_time();
  const ControllerStatus status = controller.process(simulator.input(), output);
  const std::int64_t elapsed_us = esp_timer_get_time() - started_us;
  output.diagnostics.inference_us = elapsed_us > 0 ? static_cast<std::uint32_t>(elapsed_us) : 0U;

  const DecisionEmitRequest request{&simulator.input(), &output, status, runtime.step};
  growbox::demo::wire::emitDecision(request);

  if (runtime.mode == DemoMode::ClosedLoop) {
    simulator.advance(output.safe, kSimulationStepSeconds);
  } else {
    auto& input = simulator.input();
    syncPreviousState(input, output.safe);
    input.monotonic_time_ms += static_cast<std::uint64_t>(kSimulationStepSeconds * 1000.0f);
  }
  ++runtime.step;
}

} // namespace
#endif

extern "C" void app_main() {
  emitCoreDumpBootDiagnostics();
  emitBreadcrumbBootDiagnostics();
  emitRuntimeLifecycleDiagnostics();
#if GROWBOX_APP_CLIMATE_V6_FAKE
  growbox::app::climate_io::runClimateV6FakeRuntime();
#elif GROWBOX_APP_CLIMATE_V6_REAL_INPUTS
  growbox::app::climate_io::runClimateV6RealInputRuntime();
#else
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
#endif
}
