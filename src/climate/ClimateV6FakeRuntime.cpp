#include "climate/ClimateV6FakeRuntime.h"

#include "climate/ClimateApplication.h"
#include "climate/ClimateDeterministicFake.h"
#include "climate/ClimateDiagnostics.h"
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

const char* humidityModeName(::growbox::climate::HumidityControlMode mode) noexcept {
  switch (mode) {
  case ::growbox::climate::HumidityControlMode::Rh:
    return "rh";
  case ::growbox::climate::HumidityControlMode::Vpd:
    return "vpd";
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

void addMeasuredValue(cJSON* parent, const char* name,
                      const ::growbox::climate::MeasuredValue& measured) noexcept {
  cJSON* node = cJSON_AddObjectToObject(parent, name);
  if (node == nullptr) {
    return;
  }
  cJSON_AddNumberToObject(node, "value", measured.value);
  cJSON_AddBoolToObject(node, "valid", measured.valid);
  cJSON_AddNumberToObject(node, "age_ms", static_cast<double>(measured.age_ms));
}

void addPolicyRequest(cJSON* parent, const char* name,
                      const ::growbox::climate::ClimatePolicyRequest& request) noexcept {
  cJSON* node = cJSON_AddObjectToObject(parent, name);
  if (node == nullptr) {
    return;
  }
  cJSON_AddNumberToObject(node, "heater", request.heater);
  cJSON_AddNumberToObject(node, "cooler", request.cooler);
  cJSON_AddNumberToObject(node, "exhaust_fan", request.exhaust_fan);
  cJSON_AddNumberToObject(node, "humidifier", request.humidifier);
  cJSON_AddNumberToObject(node, "dehumidifier", request.dehumidifier);
  cJSON_AddNumberToObject(node, "co2_doser", request.co2_doser);
}

void addPreviousActions(cJSON* parent, const char* name,
                        const ::growbox::climate::PreviousClimateActions& actions) noexcept {
  cJSON* node = cJSON_AddObjectToObject(parent, name);
  if (node == nullptr) {
    return;
  }
  cJSON_AddNumberToObject(node, "heater", actions.heater);
  cJSON_AddNumberToObject(node, "cooler", actions.cooler);
  cJSON_AddNumberToObject(node, "exhaust_fan", actions.exhaust_fan);
  cJSON_AddNumberToObject(node, "humidifier", actions.humidifier);
  cJSON_AddNumberToObject(node, "dehumidifier", actions.dehumidifier);
  cJSON_AddNumberToObject(node, "co2_doser", actions.co2_doser);
}

void addPolicyEvaluation(cJSON* parent, const char* name,
                         const ::growbox::climate::ClimatePolicyEvaluation& evaluation) noexcept {
  cJSON* node = cJSON_AddObjectToObject(parent, name);
  if (node == nullptr) {
    return;
  }
  addPolicyRequest(node, "raw", evaluation.raw);
  addPolicyRequest(node, "arbitrated", evaluation.arbitrated);
  addPolicyRequest(node, "safe", evaluation.safe);
  cJSON_AddNumberToObject(node, "arbitration_interventions", evaluation.arbitration_interventions);
  cJSON_AddNumberToObject(node, "safety_interventions", evaluation.safety_interventions);
}

void addCapabilities(cJSON* parent, const ::growbox::climate::ClimateCapabilities& capabilities) {
  cJSON* node = cJSON_AddObjectToObject(parent, "capabilities");
  if (node == nullptr) {
    return;
  }
  cJSON_AddBoolToObject(node, "heater", capabilities.heater);
  cJSON_AddBoolToObject(node, "cooler", capabilities.cooler);
  cJSON_AddBoolToObject(node, "exhaust_fan", capabilities.exhaust_fan);
  cJSON_AddBoolToObject(node, "humidifier", capabilities.humidifier);
  cJSON_AddBoolToObject(node, "dehumidifier", capabilities.dehumidifier);
  cJSON_AddBoolToObject(node, "co2_doser", capabilities.co2_doser);
}

void addInput(cJSON* parent, const ClimateSnapshotObservation& input) noexcept {
  cJSON* node = cJSON_AddObjectToObject(parent, "input");
  if (node == nullptr) {
    return;
  }
  cJSON_AddBoolToObject(node, "attempted", input.attempted);
  cJSON_AddBoolToObject(node, "available", input.available);
  cJSON_AddNumberToObject(node, "sample_monotonic_ms", static_cast<double>(input.monotonic_ms));
  if (!input.available) {
    return;
  }

  const ClimateInputSnapshot& snapshot = input.snapshot;
  cJSON_AddNumberToObject(node, "sensor_timeout_ms",
                          static_cast<double>(snapshot.sensor_timeout_ms));
  cJSON_AddStringToObject(node, "humidity_control_mode",
                          humidityModeName(snapshot.humidity_control_mode));

  cJSON* measurements = cJSON_AddObjectToObject(node, "measurements");
  if (measurements != nullptr) {
    addMeasuredValue(measurements, "air_temperature_c", snapshot.measurements.air_temperature_c);
    addMeasuredValue(measurements, "relative_humidity_pct",
                     snapshot.measurements.relative_humidity_pct);
    addMeasuredValue(measurements, "co2_ppm", snapshot.measurements.co2_ppm);
    addMeasuredValue(measurements, "outside_temperature_c",
                     snapshot.measurements.outside_temperature_c);
    addMeasuredValue(measurements, "outside_humidity_pct",
                     snapshot.measurements.outside_humidity_pct);
  }

  cJSON* targets = cJSON_AddObjectToObject(node, "targets");
  if (targets != nullptr) {
    cJSON_AddNumberToObject(targets, "air_temperature_c", snapshot.targets.air_temperature_c);
    cJSON_AddNumberToObject(targets, "relative_humidity_pct",
                            snapshot.targets.relative_humidity_pct);
    cJSON_AddNumberToObject(targets, "air_vpd_kpa", snapshot.targets.air_vpd_kpa);
    cJSON_AddBoolToObject(targets, "co2_enabled", snapshot.targets.co2_enabled);
    cJSON_AddNumberToObject(targets, "co2_ppm", snapshot.targets.co2_ppm);
  }

  cJSON* schedule = cJSON_AddObjectToObject(node, "schedule");
  if (schedule != nullptr) {
    cJSON_AddNumberToObject(schedule, "light_level", snapshot.schedule.light_level);
  }
  addCapabilities(node, snapshot.capabilities);
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
  cJSON_AddNumberToObject(document, "diagnostics_schema_version", kClimateDiagnosticsSchemaVersion);
  ::growbox::demo::wire::emitJsonDocument(document);
}

void emitDiagnostics(const ClimateDiagnostics& diagnostics) noexcept {
  cJSON* document = cJSON_CreateObject();
  if (document == nullptr) {
    return;
  }
  cJSON_AddStringToObject(document, "type", "climate_runtime_diagnostics");
  cJSON_AddNumberToObject(document, "diagnostics_schema_version", diagnostics.schema_version);
  cJSON_AddStringToObject(document, "application", "climate-v6");
  cJSON_AddStringToObject(document, "application_mode", "climate-v6-fake");
  cJSON_AddStringToObject(document, "input_backend", "fake");
  cJSON_AddStringToObject(document, "output_backend", "fake");
  cJSON_AddNumberToObject(document, "monotonic_ms", static_cast<double>(diagnostics.monotonic_ms));
  cJSON_AddStringToObject(document, "policy_mode", policyModeName(diagnostics.policy_mode));
  cJSON_AddStringToObject(document, "io_status", ioStatusName(diagnostics.io_status));
  cJSON_AddStringToObject(document, "runtime_status",
                          runtimeStatusName(diagnostics.runtime_status));
  cJSON_AddBoolToObject(document, "input_sampled", diagnostics.input_sampled);
  cJSON_AddBoolToObject(document, "command_applied", diagnostics.command_applied);
  cJSON_AddBoolToObject(document, "fail_safe_attempted", diagnostics.fail_safe_attempted);
  cJSON_AddBoolToObject(document, "fail_safe_applied", diagnostics.fail_safe_applied);
  cJSON_AddBoolToObject(document, "actuator_fault_latched", diagnostics.actuator_fault_latched);

  addInput(document, diagnostics.input);

  cJSON* policy = cJSON_AddObjectToObject(document, "policy");
  if (policy != nullptr) {
    cJSON_AddBoolToObject(policy, "ml_evaluated", diagnostics.ml_evaluated);
    cJSON_AddBoolToObject(policy, "authoritative_ml", diagnostics.authoritative_ml);
    addPolicyEvaluation(policy, "rule", diagnostics.rule);
    addPolicyEvaluation(policy, "ml_shadow", diagnostics.ml_shadow);
    addPolicyRequest(policy, "final_safe_request", diagnostics.final_safe_request);
  }
  addPreviousActions(document, "confirmed_applied", diagnostics.confirmed_applied);
  ::growbox::demo::wire::emitJsonDocument(document);
}

} // namespace

[[noreturn]] void runClimateV6FakeRuntime() noexcept {
  beginJsonOutput();

  DeterministicClimateScenarioProvider source_provider;
  ObservedClimateSnapshotProvider provider(source_provider);
  AcceptAllFakeRoleDriver driver;
  ::growbox::climate::ClimateRuntimeController runtime(nullptr, ruleRuntimeConfig());
  ClimateApplication application(runtime, provider, driver);

  emitStartup();
  while (true) {
    const std::uint64_t now_ms = monotonicMilliseconds();
    ::growbox::climate::ClimateRuntimeDecision decision{};
    const ::growbox::climate::ClimateLoopResult result = application.tick(now_ms, decision);
    const ClimateDiagnostics diagnostics =
        makeClimateDiagnostics(now_ms, provider.observation(), result, decision,
                               application.previousApplied(), application.actuatorFaultLatched());
    emitDiagnostics(diagnostics);
    vTaskDelay(pdMS_TO_TICKS(DeterministicClimateScenarioProvider::kTickIntervalMs));
  }
}

} // namespace growbox::app::climate_io
