#include "climate/ClimateV6FakeRuntime.h"

#include "climate/ClimateApplication.h"
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

constexpr std::uint32_t kTickIntervalMs = 1'000U;
constexpr std::uint64_t kSensorTimeoutMs = 30'000U;

class FixedFakeSnapshotProvider final : public ClimateSnapshotProvider {
public:
  bool snapshot(std::uint64_t, ClimateInputSnapshot& output) noexcept override {
    output = {};
    output.measurements.air_temperature_c = {23.0F, true, 0U};
    output.measurements.relative_humidity_pct = {60.0F, true, 0U};
    output.measurements.co2_ppm = {500.0F, true, 0U};
    output.measurements.outside_temperature_c = {18.0F, true, 0U};
    output.measurements.outside_humidity_pct = {50.0F, true, 0U};
    output.targets.air_temperature_c = 24.0F;
    output.targets.relative_humidity_pct = 60.0F;
    output.targets.air_vpd_kpa = 1.2F;
    output.targets.co2_enabled = true;
    output.targets.co2_ppm = 950.0F;
    output.schedule.light_level = 0.6F;
    output.capabilities.heater = true;
    output.capabilities.cooler = true;
    output.capabilities.exhaust_fan = true;
    output.capabilities.humidifier = true;
    output.capabilities.dehumidifier = true;
    output.capabilities.co2_doser = true;
    output.sensor_timeout_ms = kSensorTimeoutMs;
    return true;
  }
};

class AcceptAllFakeRoleDriver final : public ClimateRoleDriver {
public:
  bool apply(ClimateActuatorRole, float, std::uint64_t) noexcept override {
    return true;
  }
};

::growbox::climate::ClimateRuntimeConfig ruleRuntimeConfig() noexcept {
  ::growbox::climate::ClimateRuntimeConfig config{};
  config.mode = ::growbox::climate::ClimatePolicyMode::Rule;
  config.sensor_timeout_ms = kSensorTimeoutMs;
  config.timestep_s = static_cast<float>(kTickIntervalMs) / 1000.0F;
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
  cJSON_AddNumberToObject(document, "tick_interval_ms", kTickIntervalMs);
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

  FixedFakeSnapshotProvider provider;
  AcceptAllFakeRoleDriver driver;
  ::growbox::climate::ClimateRuntimeController runtime(nullptr, ruleRuntimeConfig());
  ClimateApplication application(runtime, provider, driver);

  emitStartup();
  while (true) {
    const std::uint64_t now_ms = monotonicMilliseconds();
    ::growbox::climate::ClimateRuntimeDecision decision{};
    const ::growbox::climate::ClimateLoopResult result = application.tick(now_ms, decision);
    emitStatus(now_ms, result, decision, application.actuatorFaultLatched());
    vTaskDelay(pdMS_TO_TICKS(kTickIntervalMs));
  }
}

} // namespace growbox::app::climate_io
