#include "climate/ClimateV6FakeRuntime.h"

#include "climate/ClimateApplication.h"
#include "climate/ClimateDeterministicFake.h"
#include "demo/protocol/JsonLineWriter.h"

#include <cJSON.h>
#include <driver/usb_serial_jtag.h>
#include <esp_err.h>
#include <esp_timer.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include <cstdint>

namespace growbox::app::climate_io {
namespace {

class AcceptAllFakeRoleDriver final : public ClimateRoleDriver {
public:
  bool apply(ClimateActuatorRole, float, std::uint64_t) noexcept override {
    return true;
  }
};

::growbox::climate::ClimateRuntimeConfig ruleRuntimeConfig() noexcept {
  ::growbox::climate::ClimateRuntimeConfig config{};
  config.mode = ::growbox::climate::ClimatePolicyMode::Rule;
  config.sensor_timeout_ms = ::growbox::climate::kDefaultSensorTimeoutMs;
  config.timestep_s =
      static_cast<float>(DeterministicClimateScenarioProvider::kTickIntervalMs) / 1000.0F;
  return config;
}

std::uint64_t monotonicMilliseconds() noexcept {
  return static_cast<std::uint64_t>(esp_timer_get_time()) / 1000U;
}

const char* policyModeName(::growbox::climate::ClimatePolicyMode mode) noexcept {
  switch (mode) {
  case ::growbox::climate::ClimatePolicyMode::Rule:
    return "rule";
  case ::growbox::climate::ClimatePolicyMode::MlShadow:
    return "ml-shadow";
  case ::growbox::climate::ClimatePolicyMode::MlActive:
    return "ml-active";
  }
  return "unknown";
}

const char* ioStatusName(::growbox::climate::ClimateLoopIoStatus status) noexcept {
  switch (status) {
  case ::growbox::climate::ClimateLoopIoStatus::Ok:
    return "ok";
  case ::growbox::climate::ClimateLoopIoStatus::InputUnavailable:
    return "input-unavailable";
  case ::growbox::climate::ClimateLoopIoStatus::ActuatorApplyFailed:
    return "actuator-apply-failed";
  case ::growbox::climate::ClimateLoopIoStatus::ActuatorFaultLatched:
    return "actuator-fault-latched";
  }
  return "unknown";
}

const char* runtimeStatusName(::growbox::climate::ClimateRuntimeStatus status) noexcept {
  switch (status) {
  case ::growbox::climate::ClimateRuntimeStatus::Ok:
    return "ok";
  case ::growbox::climate::ClimateRuntimeStatus::MlProviderMissing:
    return "ml-provider-missing";
  case ::growbox::climate::ClimateRuntimeStatus::MlInferenceFailed:
    return "ml-inference-failed";
  case ::growbox::climate::ClimateRuntimeStatus::MlActiveNotAllowed:
    return "ml-active-not-allowed";
  }
  return "unknown";
}

void beginJsonOutput() noexcept {
  if (usb_serial_jtag_is_driver_installed()) {
    return;
  }
  usb_serial_jtag_driver_config_t config = USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();
  config.tx_buffer_size = 4096U;
  config.rx_buffer_size = 256U;
  ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&config));
}

void emitStartup() noexcept {
  cJSON* document = cJSON_CreateObject();
  if (document == nullptr) {
    return;
  }
  cJSON_AddStringToObject(document, "type", "climate_runtime_startup");
  cJSON_AddStringToObject(document, "application", "climate-v6");
  cJSON_AddStringToObject(document, "application_mode", "climate-v6-fake");
  cJSON_AddStringToObject(document, "policy_mode", "rule");
  cJSON_AddStringToObject(document, "input_backend", "fake");
  cJSON_AddStringToObject(document, "output_backend", "fake");
  cJSON_AddBoolToObject(document, "gpio_control", false);
  cJSON_AddNumberToObject(document, "tick_interval_ms",
                          DeterministicClimateScenarioProvider::kTickIntervalMs);
  cJSON_AddStringToObject(document, "scenario", "deterministic-240-tick-v1");
  ::growbox::demo::wire::emitJsonDocument(document);
}

void emitStatus(std::uint64_t monotonic_ms, const ::growbox::climate::ClimateLoopResult& result,
                const ::growbox::climate::ClimateRuntimeDecision& decision,
                bool actuator_fault_latched) noexcept {
  cJSON* document = cJSON_CreateObject();
  if (document == nullptr) {
    return;
  }
  cJSON_AddStringToObject(document, "type", "climate_runtime_status");
  cJSON_AddStringToObject(document, "application", "climate-v6");
  cJSON_AddStringToObject(document, "application_mode", "climate-v6-fake");
  cJSON_AddStringToObject(document, "policy_mode", policyModeName(decision.mode));
  cJSON_AddStringToObject(document, "input_backend", "fake");
  cJSON_AddStringToObject(document, "output_backend", "fake");
  cJSON_AddNumberToObject(document, "monotonic_ms", static_cast<double>(monotonic_ms));
  cJSON_AddStringToObject(document, "io_status", ioStatusName(result.io_status));
  cJSON_AddStringToObject(document, "runtime_status", runtimeStatusName(result.runtime_status));
  cJSON_AddBoolToObject(document, "input_sampled", result.input_sampled);
  cJSON_AddBoolToObject(document, "command_applied", result.command_applied);
  cJSON_AddBoolToObject(document, "actuator_fault_latched", actuator_fault_latched);
  ::growbox::demo::wire::emitJsonDocument(document);
}

} // namespace

[[noreturn]] void runClimateV6FakeRuntime() noexcept {
  beginJsonOutput();

  DeterministicClimateScenarioProvider provider;
  AcceptAllFakeRoleDriver driver;
  ::growbox::climate::ClimateRuntimeController runtime(nullptr, ruleRuntimeConfig());
  ClimateApplication application(runtime, provider, driver);

  emitStartup();
  while (true) {
    const std::uint64_t now_ms = monotonicMilliseconds();
    ::growbox::climate::ClimateRuntimeDecision decision{};
    const ::growbox::climate::ClimateLoopResult result = application.tick(now_ms, decision);
    emitStatus(now_ms, result, decision, application.actuatorFaultLatched());
    vTaskDelay(pdMS_TO_TICKS(DeterministicClimateScenarioProvider::kTickIntervalMs));
  }
}

} // namespace growbox::app::climate_io
