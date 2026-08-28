#!/usr/bin/env bash
set -euo pipefail

MODE="${1:?mode required}"
EXPECTED="${2:-}"

case "$MODE" in
  apply)
    test -n "$EXPECTED"
    git fetch origin mvp/environment-controller agent-control
    git reset --hard origin/mvp/environment-controller
    git clean -fd
    test "$(git rev-parse HEAD)" = "$EXPECTED"
    test -z "$(git status --porcelain)"

    cat > src/climate/ClimateV6FakeRuntime.h <<'EOF'
#pragma once

namespace growbox::app::climate_io {

[[noreturn]] void runClimateV6FakeRuntime() noexcept;

} // namespace growbox::app::climate_io
EOF

    cat > src/climate/ClimateV6FakeRuntime.cpp <<'EOF'
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
EOF

    .venv/bin/python - <<'PY'
from pathlib import Path

main = Path('src/main.cpp')
original = main.read_text(encoding='utf-8')
marker = 'extern "C" void app_main() {'
assert marker in original
assert 'GROWBOX_APP_CLIMATE_V6_FAKE' not in original
head, tail = original.split(marker, 1)
body = tail.strip()
assert body.endswith('}')
body = body[:-1].rstrip()
main.write_text(
    '#ifndef GROWBOX_APP_CLIMATE_V6_FAKE\n'
    '#define GROWBOX_APP_CLIMATE_V6_FAKE 0\n'
    '#endif\n\n'
    '#include "climate/ClimateV6FakeRuntime.h"\n\n'
    '#if !GROWBOX_APP_CLIMATE_V6_FAKE\n'
    + head.rstrip()
    + '\n#endif\n\n'
    'extern "C" void app_main() {\n'
    '#if GROWBOX_APP_CLIMATE_V6_FAKE\n'
    '  growbox::app::climate_io::runClimateV6FakeRuntime();\n'
    '#else\n'
    + body
    + '\n#endif\n'
    '}\n',
    encoding='utf-8',
)

cmake = Path('src/CMakeLists.txt')
text = cmake.read_text(encoding='utf-8')
source_anchor = '    "climate/ClimateApplication.cpp"\n'
assert source_anchor in text
assert 'ClimateV6FakeRuntime.cpp' not in text
text = text.replace(source_anchor, source_anchor + '    "climate/ClimateV6FakeRuntime.cpp"\n', 1)
mode_anchor = 'if(NOT DEFINED GROWBOX_BOARD_PROFILE)\n'
assert mode_anchor in text
mode_block = '''set(GROWBOX_APP_MODE "legacy" CACHE STRING "Growbox application runtime")
set_property(CACHE GROWBOX_APP_MODE PROPERTY STRINGS "legacy" "climate-v6-fake")
if(GROWBOX_APP_MODE STREQUAL "legacy")
  set(GROWBOX_APP_CLIMATE_V6_FAKE 0)
elseif(GROWBOX_APP_MODE STREQUAL "climate-v6-fake")
  set(GROWBOX_APP_CLIMATE_V6_FAKE 1)
else()
  message(FATAL_ERROR "Unsupported GROWBOX_APP_MODE: ${GROWBOX_APP_MODE}")
endif()

'''
text = text.replace(mode_anchor, mode_block + mode_anchor, 1)
defs = '''target_compile_definitions(
  ${COMPONENT_LIB}
  PRIVATE GROWBOX_BOARD_PROFILE="${GROWBOX_BOARD_PROFILE}"
)
'''
replacement = '''target_compile_definitions(
  ${COMPONENT_LIB}
  PRIVATE
    GROWBOX_BOARD_PROFILE="${GROWBOX_BOARD_PROFILE}"
    GROWBOX_APP_CLIMATE_V6_FAKE=${GROWBOX_APP_CLIMATE_V6_FAKE}
)
'''
assert defs in text
text = text.replace(defs, replacement, 1)
cmake.write_text(text, encoding='utf-8')

idf_gate = Path('scripts/idf_gate_build.sh')
text = idf_gate.read_text(encoding='utf-8')
profile_anchor = 'PROFILE="${IDF_GATE_PROFILE:-esp32s3-devkitc1-n8}"\n'
assert profile_anchor in text
assert 'IDF_GATE_APP_MODE' not in text
text = text.replace(profile_anchor, profile_anchor + 'APP_MODE="${IDF_GATE_APP_MODE:-legacy}"\n', 1)
text = text.replace(
    'echo "==> idf.py build (${PROFILE}, ${BUILD_DIR})"\n',
    'echo "==> idf.py build (${PROFILE}, ${BUILD_DIR}, app=${APP_MODE})"\n',
    1,
)
arg_anchor = '  -D "GROWBOX_BOARD_PROFILE=${PROFILE}" \\\n  build\n'
assert arg_anchor in text
text = text.replace(
    arg_anchor,
    '  -D "GROWBOX_BOARD_PROFILE=${PROFILE}" \\\n  -D "GROWBOX_APP_MODE=${APP_MODE}" \\\n  build\n',
    1,
)
idf_gate.write_text(text, encoding='utf-8')

status = Path('docs/CURRENT_STATUS.md')
text = status.read_text(encoding='utf-8')
anchor = 'Stage25A adds `ClimateApplication`, a deliberately small constructor-injected composition root around the existing input adapter, control loop and actuator adapter. Host tests now exercise the complete `ClimateSnapshotProvider -> ClimateInputAdapter -> ClimateControlLoop -> ClimateActuatorAdapter -> ClimateRoleDriver` path across multiple ticks, including stale/invalid/unavailable input, ML shadow isolation, rejected commands with OFF recovery, fault latching/reset, confirmed applied feedback and all six semantic actuator roles. Fake providers and drivers remain test-only implementations of the same public interfaces intended for future hardware.\n'
assert anchor in text
assert 'Stage25B adds an explicit build-time application boundary' not in text
insert = anchor + '\nStage25B adds an explicit build-time application boundary. `GROWBOX_APP_MODE` defaults to `legacy`, while `climate-v6-fake` selects a hardware-neutral climate-v6 runtime backed by a fixed fake snapshot provider and an accept-all fake role driver. The climate-v6 fake runtime emits startup/status identity (`application`, policy mode, input backend and output backend) and never touches GPIO or physical loads. Both application modes are required to compile in the ESP-IDF v5.5.4 gate.\n'
text = text.replace(anchor, insert, 1)
status.write_text(text, encoding='utf-8')

plan = Path('docs/CONTINUATION_PLAN.md')
text = plan.read_text(encoding='utf-8')
start = text.index('### Stage25B — application runtime boundary\n')
end = text.index('### Stage27 — hardware bring-up\n', start)
replacement = '''### Stage25B completed — explicit reversible application runtime boundary

`GROWBOX_APP_MODE` now defaults to `legacy`. The optional `climate-v6-fake` mode runs the proven
`ClimateApplication` path with a fixed fake snapshot provider and an accept-all fake role driver.
It reports application/policy/input/output identity over JSON serial status and has no GPIO or
physical actuator dependency. The ESP-IDF v5.5.4 gate compiles both modes.

### Stage25C — deterministic fake runtime

Replace the fixed smoke snapshot with a deterministic scenario provider that exercises changing
inside/outside measurements, target and schedule transitions, capabilities and long multi-tick
runs through exactly the same public provider/driver interfaces intended for hardware.

### Stage25D — climate-v6 observability and diagnostics

Expose versioned diagnostics for measurement value/validity/age, targets, schedule, capabilities,
Rule proposal, ML shadow proposal, final safe request, confirmed applied state, I/O/runtime status
and actuator-fault latch state. Keep diagnostics observational; they must not become a control path.

### Stage25E — fault-injection and soak virtual HIL

Extend virtual HIL with repeated stale/invalid/unavailable inputs, timeout boundaries, recovery,
capability changes, actuator rejection, OFF rejection, latch/reset and long deterministic runs.
Prove again that rejected commands never become confirmed/effective applied state.

### Stage26A — hardware-ready composite input layer

Introduce hardware-neutral component interfaces for inside environment, outside environment and
clock/schedule/config sources, then aggregate them into one `ClimateInputSnapshot`. Implement and
test only fake component sources at this stage. Do not select sensor libraries or buses yet.

### Stage26B — hardware-ready semantic output layer

Introduce configuration/mapping beneath `ClimateRoleDriver` for the six stable semantic actuator
roles. Keep endpoint implementations fake and normalized; test disabled capabilities, OFF,
partial rejection and deterministic role mapping. Do not add GPIO/PWM/relay/Shelly code yet.

### Stage26C — pre-hardware readiness gate

Run the complete host/schema/static/ESP-IDF gate, audit the climate-v6 fake path end to end and add
a hardware bring-up checklist. The checklist must leave unresolved BLE/RTC/pin/library choices
explicit for manual freeze before physical work.

'''
text = text[:start] + replacement + text[end:]
plan.write_text(text, encoding='utf-8')
PY

    .venv/bin/pre-commit run clang-format --files \
      src/main.cpp \
      src/climate/ClimateV6FakeRuntime.h \
      src/climate/ClimateV6FakeRuntime.cpp
    git diff --check
    grep -F 'set(GROWBOX_APP_MODE "legacy" CACHE STRING' src/CMakeLists.txt
    grep -F 'GROWBOX_APP_CLIMATE_V6_FAKE' src/main.cpp
    grep -F 'application_mode", "climate-v6-fake"' src/climate/ClimateV6FakeRuntime.cpp
    ! grep -E -i 'gpio_set|gpio_config|i2c_|scd4|nimble|ble_|ds3231|pcf8563|shelly|mqtt|modbus' \
      src/climate/ClimateV6FakeRuntime.cpp src/climate/ClimateV6FakeRuntime.h
    git status --short
    ;;

  focused)
    .venv/bin/pre-commit run --files \
      src/main.cpp \
      src/CMakeLists.txt \
      src/climate/ClimateV6FakeRuntime.h \
      src/climate/ClimateV6FakeRuntime.cpp \
      scripts/idf_gate_build.sh \
      docs/CURRENT_STATUS.md \
      docs/CONTINUATION_PLAN.md
    cmake -S test/host -B build/host-tests
    cmake --build build/host-tests --target climate_application_composition_tests --parallel
    ctest --test-dir build/host-tests -R '^climate_application_composition_tests$' --output-on-failure
    grep -F 'Stage25B adds an explicit build-time application boundary' docs/CURRENT_STATUS.md
    grep -F '### Stage25C — deterministic fake runtime' docs/CONTINUATION_PLAN.md
    git diff --check
    ;;

  full)
    test -n "$EXPECTED"
    git add -A
    .venv/bin/pre-commit run --all-files
    .venv/bin/python -m pytest -q -m 'not hardware'
    bash scripts/check_schema.sh
    cmake -S test/host -B build/host-tests
    cmake --build build/host-tests --parallel
    ctest --test-dir build/host-tests --output-on-failure
    bash scripts/run_clang_tidy_host.sh

    unset VIRTUAL_ENV CONDA_PREFIX PYTHONHOME || true
    export PATH='/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin'
    if [ ! -x "$HOME/.espressif/python_env/idf5.5_py3.14_env/bin/python" ]; then
      env -u VIRTUAL_ENV -u CONDA_PREFIX -u PYTHONHOME PATH='/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin' \
        bash "$HOME/esp/esp-idf/install.sh" esp32s3
    fi
    source "$HOME/esp/esp-idf/export.sh"
    idf.py --version | grep -F 'ESP-IDF v5.5.4'
    test "$(git -C "$HOME/esp/esp-idf" describe --tags --exact-match HEAD)" = 'v5.5.4'

    rm -rf build/idf-gate build/idf-climate-v6-fake
    bash scripts/idf_gate_build.sh
    grep -F 'GROWBOX_APP_MODE:STRING=legacy' build/idf-gate/CMakeCache.txt
    IDF_GATE_BUILD_DIR=build/idf-climate-v6-fake IDF_GATE_APP_MODE=climate-v6-fake \
      bash scripts/idf_gate_build.sh
    grep -F 'GROWBOX_APP_MODE:STRING=climate-v6-fake' build/idf-climate-v6-fake/CMakeCache.txt

    git diff --check
    git add -A
    git diff --cached --check
    git commit -m 'Add reversible climate v6 fake runtime boundary'
    git push origin HEAD:mvp/environment-controller
    test -z "$(git status --porcelain)"
    printf 'PUBLISHED_HEAD=%s\n' "$(git rev-parse HEAD)"
    ;;

  *)
    echo "Unknown mode: $MODE" >&2
    exit 2
    ;;
esac
