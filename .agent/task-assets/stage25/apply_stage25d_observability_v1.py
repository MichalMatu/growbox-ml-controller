from pathlib import Path


def write(path: str, content: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


write(
    "src/climate/ClimateDiagnostics.h",
    r'''#pragma once

#include "climate/ClimateIoAdapters.h"

#include <cstdint>

namespace growbox::app::climate_io {

inline constexpr std::uint32_t kClimateDiagnosticsSchemaVersion = 1U;

struct ClimateSnapshotObservation {
  bool attempted = false;
  bool available = false;
  std::uint64_t monotonic_ms = 0U;
  ClimateInputSnapshot snapshot{};
};

class ObservedClimateSnapshotProvider final : public ClimateSnapshotProvider {
public:
  explicit ObservedClimateSnapshotProvider(ClimateSnapshotProvider& provider) noexcept
      : provider_(provider) {}

  bool snapshot(std::uint64_t monotonic_ms, ClimateInputSnapshot& output) noexcept override;

  const ClimateSnapshotObservation& observation() const noexcept {
    return observation_;
  }

private:
  ClimateSnapshotProvider& provider_;
  ClimateSnapshotObservation observation_{};
};

struct ClimateDiagnostics {
  std::uint32_t schema_version = kClimateDiagnosticsSchemaVersion;
  std::uint64_t monotonic_ms = 0U;
  ClimateSnapshotObservation input{};
  ::growbox::climate::ClimatePolicyMode policy_mode = ::growbox::climate::ClimatePolicyMode::Rule;
  ::growbox::climate::ClimateRuntimeStatus runtime_status =
      ::growbox::climate::ClimateRuntimeStatus::Ok;
  ::growbox::climate::ClimateLoopIoStatus io_status = ::growbox::climate::ClimateLoopIoStatus::Ok;
  bool ml_evaluated = false;
  bool authoritative_ml = false;
  ::growbox::climate::ClimatePolicyEvaluation rule{};
  ::growbox::climate::ClimatePolicyEvaluation ml_shadow{};
  ::growbox::climate::ClimatePolicyRequest final_safe_request{};
  ::growbox::climate::PreviousClimateActions confirmed_applied{};
  bool input_sampled = false;
  bool command_applied = false;
  bool fail_safe_attempted = false;
  bool fail_safe_applied = false;
  bool actuator_fault_latched = false;
};

ClimateDiagnostics makeClimateDiagnostics(
    std::uint64_t monotonic_ms, const ClimateSnapshotObservation& input,
    const ::growbox::climate::ClimateLoopResult& result,
    const ::growbox::climate::ClimateRuntimeDecision& decision,
    const ::growbox::climate::PreviousClimateActions& confirmed_applied,
    bool actuator_fault_latched) noexcept;

} // namespace growbox::app::climate_io
''',
)

write(
    "src/climate/ClimateDiagnostics.cpp",
    r'''#include "climate/ClimateDiagnostics.h"

namespace growbox::app::climate_io {

bool ObservedClimateSnapshotProvider::snapshot(std::uint64_t monotonic_ms,
                                               ClimateInputSnapshot& output) noexcept {
  const bool available = provider_.snapshot(monotonic_ms, output);
  observation_ = {};
  observation_.attempted = true;
  observation_.available = available;
  observation_.monotonic_ms = monotonic_ms;
  if (available) {
    observation_.snapshot = output;
  }
  return available;
}

ClimateDiagnostics makeClimateDiagnostics(
    std::uint64_t monotonic_ms, const ClimateSnapshotObservation& input,
    const ::growbox::climate::ClimateLoopResult& result,
    const ::growbox::climate::ClimateRuntimeDecision& decision,
    const ::growbox::climate::PreviousClimateActions& confirmed_applied,
    bool actuator_fault_latched) noexcept {
  ClimateDiagnostics diagnostics{};
  diagnostics.monotonic_ms = monotonic_ms;
  diagnostics.input = input;
  diagnostics.policy_mode = decision.mode;
  diagnostics.runtime_status = result.runtime_status;
  diagnostics.io_status = result.io_status;
  diagnostics.ml_evaluated = decision.ml_evaluated;
  diagnostics.authoritative_ml = decision.authoritative_ml;
  diagnostics.rule = decision.rule;
  diagnostics.ml_shadow = decision.ml;
  diagnostics.final_safe_request = decision.applied;
  diagnostics.confirmed_applied = confirmed_applied;
  diagnostics.input_sampled = result.input_sampled;
  diagnostics.command_applied = result.command_applied;
  diagnostics.fail_safe_attempted = result.fail_safe_attempted;
  diagnostics.fail_safe_applied = result.fail_safe_applied;
  diagnostics.actuator_fault_latched = actuator_fault_latched;
  return diagnostics;
}

} // namespace growbox::app::climate_io
''',
)

write(
    "test/test_climate_diagnostics/test_main.cpp",
    r'''#include "climate/ClimateDiagnostics.h"

#include <cassert>
#include <cmath>
#include <cstdint>

using namespace growbox::app::climate_io;
using namespace growbox::climate;

namespace {

bool near(float left, float right, float tolerance = 1.0e-6F) {
  return std::fabs(left - right) <= tolerance;
}

ClimateInputSnapshot sampleSnapshot() {
  ClimateInputSnapshot snapshot{};
  snapshot.measurements.air_temperature_c = {23.5F, true, 7U};
  snapshot.measurements.relative_humidity_pct = {61.0F, true, 8U};
  snapshot.measurements.co2_ppm = {712.0F, true, 9U};
  snapshot.measurements.outside_temperature_c = {17.0F, true, 10U};
  snapshot.measurements.outside_humidity_pct = {52.0F, true, 11U};
  snapshot.humidity_control_mode = HumidityControlMode::Vpd;
  snapshot.targets.air_temperature_c = 24.5F;
  snapshot.targets.relative_humidity_pct = 62.0F;
  snapshot.targets.air_vpd_kpa = 1.1F;
  snapshot.targets.co2_enabled = true;
  snapshot.targets.co2_ppm = 980.0F;
  snapshot.schedule.light_level = 0.75F;
  snapshot.capabilities.heater = true;
  snapshot.capabilities.cooler = false;
  snapshot.capabilities.exhaust_fan = true;
  snapshot.capabilities.humidifier = true;
  snapshot.capabilities.dehumidifier = false;
  snapshot.capabilities.co2_doser = true;
  snapshot.sensor_timeout_ms = 31'000U;
  return snapshot;
}

class ProbeProvider final : public ClimateSnapshotProvider {
public:
  explicit ProbeProvider(bool available) : available_(available) {}

  bool snapshot(std::uint64_t monotonic_ms, ClimateInputSnapshot& output) noexcept override {
    ++calls;
    last_monotonic_ms = monotonic_ms;
    if (!available_) {
      return false;
    }
    output = sampleSnapshot();
    return true;
  }

  std::uint32_t calls = 0U;
  std::uint64_t last_monotonic_ms = 0U;

private:
  bool available_ = true;
};

void testObservedProviderIsTransparentAndSingleRead() {
  ProbeProvider source(true);
  ObservedClimateSnapshotProvider observed(source);
  ClimateInputSnapshot output{};

  assert(observed.snapshot(12'345U, output));
  assert(source.calls == 1U);
  assert(source.last_monotonic_ms == 12'345U);
  assert(near(output.measurements.air_temperature_c.value, 23.5F));

  const ClimateSnapshotObservation& observation = observed.observation();
  assert(observation.attempted);
  assert(observation.available);
  assert(observation.monotonic_ms == 12'345U);
  assert(near(observation.snapshot.measurements.relative_humidity_pct.value, 61.0F));
  assert(observation.snapshot.measurements.co2_ppm.age_ms == 9U);
  assert(observation.snapshot.humidity_control_mode == HumidityControlMode::Vpd);
  assert(!observation.snapshot.capabilities.cooler);
  assert(observation.snapshot.sensor_timeout_ms == 31'000U);
}

void testObservedProviderRecordsUnavailableWithoutInventingSnapshot() {
  ProbeProvider source(false);
  ObservedClimateSnapshotProvider observed(source);
  ClimateInputSnapshot output = sampleSnapshot();

  assert(!observed.snapshot(77U, output));
  assert(source.calls == 1U);
  const ClimateSnapshotObservation& observation = observed.observation();
  assert(observation.attempted);
  assert(!observation.available);
  assert(observation.monotonic_ms == 77U);
  assert(!observation.snapshot.measurements.air_temperature_c.valid);
}

void testDiagnosticsCopiesExistingControlEvidenceOnly() {
  ProbeProvider source(true);
  ObservedClimateSnapshotProvider observed(source);
  ClimateInputSnapshot output{};
  assert(observed.snapshot(2'000U, output));

  ClimateRuntimeDecision decision{};
  decision.mode = ClimatePolicyMode::MlShadow;
  decision.ml_evaluated = true;
  decision.authoritative_ml = false;
  decision.rule.raw.heater = 0.4F;
  decision.rule.arbitrated.heater = 0.3F;
  decision.rule.safe.heater = 0.2F;
  decision.rule.arbitration_interventions = OppositionHeaterCooler;
  decision.rule.safety_interventions = HighTemperature;
  decision.ml.raw.cooler = 0.8F;
  decision.ml.arbitrated.cooler = 0.7F;
  decision.ml.safe.cooler = 0.6F;
  decision.ml.arbitration_interventions = UnavailableHeater;
  decision.ml.safety_interventions = HighHumidity;
  decision.applied.exhaust_fan = 0.55F;

  ClimateLoopResult result{};
  result.io_status = ClimateLoopIoStatus::ActuatorApplyFailed;
  result.runtime_status = ClimateRuntimeStatus::Ok;
  result.input_sampled = true;
  result.command_applied = false;
  result.fail_safe_attempted = true;
  result.fail_safe_applied = true;

  PreviousClimateActions confirmed{};
  confirmed.heater = 0.1F;
  confirmed.exhaust_fan = 0.25F;

  const ClimateDiagnostics diagnostics = makeClimateDiagnostics(
      2'000U, observed.observation(), result, decision, confirmed, true);

  assert(diagnostics.schema_version == kClimateDiagnosticsSchemaVersion);
  assert(diagnostics.monotonic_ms == 2'000U);
  assert(diagnostics.input.available);
  assert(diagnostics.policy_mode == ClimatePolicyMode::MlShadow);
  assert(diagnostics.runtime_status == ClimateRuntimeStatus::Ok);
  assert(diagnostics.io_status == ClimateLoopIoStatus::ActuatorApplyFailed);
  assert(diagnostics.ml_evaluated);
  assert(!diagnostics.authoritative_ml);
  assert(near(diagnostics.rule.raw.heater, 0.4F));
  assert(near(diagnostics.rule.arbitrated.heater, 0.3F));
  assert(near(diagnostics.rule.safe.heater, 0.2F));
  assert(diagnostics.rule.arbitration_interventions == OppositionHeaterCooler);
  assert(diagnostics.rule.safety_interventions == HighTemperature);
  assert(near(diagnostics.ml_shadow.raw.cooler, 0.8F));
  assert(near(diagnostics.ml_shadow.arbitrated.cooler, 0.7F));
  assert(near(diagnostics.ml_shadow.safe.cooler, 0.6F));
  assert(near(diagnostics.final_safe_request.exhaust_fan, 0.55F));
  assert(near(diagnostics.confirmed_applied.heater, 0.1F));
  assert(near(diagnostics.confirmed_applied.exhaust_fan, 0.25F));
  assert(diagnostics.input_sampled);
  assert(!diagnostics.command_applied);
  assert(diagnostics.fail_safe_attempted);
  assert(diagnostics.fail_safe_applied);
  assert(diagnostics.actuator_fault_latched);
}

} // namespace

int main() {
  testObservedProviderIsTransparentAndSingleRead();
  testObservedProviderRecordsUnavailableWithoutInventingSnapshot();
  testDiagnosticsCopiesExistingControlEvidenceOnly();
  return 0;
}
''',
)

write(
    "src/climate/ClimateV6FakeRuntime.cpp",
    r'''#include "climate/ClimateV6FakeRuntime.h"

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
  cJSON_AddNumberToObject(node, "arbitration_interventions",
                          evaluation.arbitration_interventions);
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
  cJSON_AddNumberToObject(node, "sensor_timeout_ms", static_cast<double>(snapshot.sensor_timeout_ms));
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
  cJSON_AddNumberToObject(document, "diagnostics_schema_version",
                          kClimateDiagnosticsSchemaVersion);
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
  cJSON_AddBoolToObject(document, "actuator_fault_latched",
                        diagnostics.actuator_fault_latched);

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
''',
)

src_cmake = Path("src/CMakeLists.txt")
text = src_cmake.read_text(encoding="utf-8")
anchor = '    "climate/ClimateDeterministicFake.cpp"\n'
assert anchor in text
assert 'ClimateDiagnostics.cpp' not in text
text = text.replace(anchor, anchor + '    "climate/ClimateDiagnostics.cpp"\n', 1)
src_cmake.write_text(text, encoding="utf-8")

host_cmake = Path("test/host/CMakeLists.txt")
text = host_cmake.read_text(encoding="utf-8")
assert "climate_diagnostics_tests" not in text
insert_before = "if(UNIX)\n"
assert insert_before in text
block = r'''
add_executable(
  climate_diagnostics_tests
  "${PROJECT_ROOT}/test/test_climate_diagnostics/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/ClimateDiagnostics.cpp"
)
target_include_directories(
  climate_diagnostics_tests
  PRIVATE
    "${PROJECT_ROOT}/src"
    "${PROJECT_ROOT}/lib/environment_control/src"
)
target_compile_features(climate_diagnostics_tests PRIVATE cxx_std_17)
target_compile_options(climate_diagnostics_tests PRIVATE -Wall -Wextra -Wpedantic)

'''
text = text.replace(insert_before, block + insert_before, 1)
link_anchor = "  target_link_libraries(climate_deterministic_fake_runtime_tests PRIVATE m)\n"
assert link_anchor in text
text = text.replace(
    link_anchor,
    link_anchor + "  target_link_libraries(climate_diagnostics_tests PRIVATE m)\n",
    1,
)
test_anchor = "add_test(NAME climate_deterministic_fake_runtime_tests COMMAND climate_deterministic_fake_runtime_tests)\n"
assert test_anchor in text
text = text.replace(
    test_anchor,
    test_anchor + "add_test(NAME climate_diagnostics_tests COMMAND climate_diagnostics_tests)\n",
    1,
)
host_cmake.write_text(text, encoding="utf-8")

tidy = Path("scripts/run_clang_tidy_host.sh")
text = tidy.read_text(encoding="utf-8")
anchor = "  src/climate/ClimateApplication.cpp\n"
assert anchor in text
assert "src/climate/ClimateDiagnostics.cpp" not in text
text = text.replace(anchor, anchor + "  src/climate/ClimateDiagnostics.cpp\n", 1)
tidy.write_text(text, encoding="utf-8")

status = Path("docs/CURRENT_STATUS.md")
text = status.read_text(encoding="utf-8")
anchor = "Stage25C replaces the fixed smoke snapshot with `DeterministicClimateScenarioProvider`, a hardware-neutral provider whose output is a pure function of monotonic time. Its 240-tick cycle varies inside/outside T/RH/CO2, day/night targets and light schedule plus actuator capabilities. Host tests prove timestamp determinism, cycle periodicity and a 1,200-tick full `ClimateApplication` run with fake outputs. Fault injection remains intentionally reserved for Stage25E.\n"
assert anchor in text
assert "Stage25D adds versioned climate-v6 diagnostics" not in text
paragraph = (
    anchor
    + "\nStage25D adds versioned climate-v6 diagnostics without adding a control path. "
      "`ObservedClimateSnapshotProvider` transparently decorates any `ClimateSnapshotProvider` and records exactly the single sample attempt consumed by the controller. "
      "After each tick, diagnostics copy measurement value/validity/age, targets, schedule, capabilities, Rule and ML-shadow evaluations, final safe request, confirmed applied actions, I/O/runtime status and actuator-fault state from existing runtime evidence. "
      "The fake ESP-IDF runtime emits this as `climate_runtime_diagnostics` schema version 1; diagnostics never write policy, runtime or actuator state.\n"
)
text = text.replace(anchor, paragraph, 1)
status.write_text(text, encoding="utf-8")

plan = Path("docs/CONTINUATION_PLAN.md")
text = plan.read_text(encoding="utf-8")
old = '''### Stage25D — climate-v6 observability and diagnostics

Expose versioned diagnostics for measurement value/validity/age, targets, schedule, capabilities,
Rule proposal, ML shadow proposal, final safe request, confirmed applied state, I/O/runtime status
and actuator-fault latch state. Keep diagnostics observational; they must not become a control path.
'''
assert old in text
new = '''### Stage25D completed — climate-v6 observability and diagnostics

Versioned schema-v1 diagnostics now observe the exact snapshot attempt consumed by the controller,
including measurement value/validity/age, targets, schedule and capabilities. They also copy Rule
and ML-shadow evaluations, the final safe request, confirmed applied state, I/O/runtime status and
actuator-fault latch state after each tick. The observer is a transparent provider decorator and
diagnostics remain read-only: they do not feed policy, runtime state or actuator writes.
'''
text = text.replace(old, new, 1)
plan.write_text(text, encoding="utf-8")
