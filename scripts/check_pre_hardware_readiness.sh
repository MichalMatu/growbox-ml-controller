#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

require_fixed() {
  local file="$1"
  local text="$2"
  if ! grep -Fq -- "$text" "$file"; then
    echo "pre-hardware readiness: missing '$text' in $file" >&2
    exit 1
  fi
}

# The reversible runtime boundary must remain explicit and legacy must remain the default.
require_fixed src/CMakeLists.txt 'set(GROWBOX_APP_MODE "legacy" CACHE STRING "Growbox application runtime")'
require_fixed src/CMakeLists.txt 'set_property(CACHE GROWBOX_APP_MODE PROPERTY STRINGS "legacy" "climate-v6-fake")'

# The embedded proof path remains fake-only and Rule-authoritative.
require_fixed src/climate/ClimateV6FakeRuntime.cpp 'config.mode = ::growbox::climate::ClimatePolicyMode::Rule;'
require_fixed src/climate/ClimateV6FakeRuntime.cpp '"input_backend", "fake"'
require_fixed src/climate/ClimateV6FakeRuntime.cpp '"output_backend", "fake"'
require_fixed src/climate/ClimateV6FakeRuntime.cpp '"gpio_control", false'

# Hardware-neutral seams required before physical bring-up.
require_fixed src/climate/ClimateIoAdapters.h 'class ClimateSnapshotProvider'
require_fixed src/climate/ClimateIoAdapters.h 'class ClimateRoleDriver'
require_fixed src/climate/ClimateCompositeInput.h 'class CompositeClimateSnapshotProvider final : public ClimateSnapshotProvider'
require_fixed src/climate/ClimateSemanticOutput.h 'class ClimateOutputEndpoint'
require_fixed src/climate/ClimateSemanticOutput.h 'class MappedClimateRoleDriver final : public ClimateRoleDriver'
require_fixed src/climate/ClimateDiagnostics.h 'class ObservedClimateSnapshotProvider final : public ClimateSnapshotProvider'

# The key host gates must remain registered in the common host suite.
for test_name in \
  climate_control_loop_tests \
  climate_application_composition_tests \
  climate_deterministic_fake_runtime_tests \
  climate_diagnostics_tests \
  climate_fault_soak_tests \
  climate_composite_input_tests \
  climate_semantic_output_tests; do
  require_fixed test/host/CMakeLists.txt "add_test(NAME ${test_name} COMMAND ${test_name})"
done

# The neutral application seams must not silently acquire concrete hardware/backend dependencies.
neutral_files=(
  src/climate/ClimateIoAdapters.h
  src/climate/ClimateIoAdapters.cpp
  src/climate/ClimateCompositeInput.h
  src/climate/ClimateCompositeInput.cpp
  src/climate/ClimateSemanticOutput.h
  src/climate/ClimateSemanticOutput.cpp
)
forbidden='(#include[[:space:]]*[<"]driver/(gpio|i2c|ledc|spi)|#include[[:space:]]*[<"].*(nimble|esp_bt|mqtt|modbus)|SCD4[01]|DS3231|PCF8563|Shelly)'
if grep -Ein "$forbidden" "${neutral_files[@]}"; then
  echo "pre-hardware readiness: concrete hardware/backend dependency leaked into neutral seam" >&2
  exit 1
fi

# Stage27 must not begin until the unresolved physical choices are manually frozen.
require_fixed docs/HARDWARE_BRINGUP_CHECKLIST.md 'SCD41 driver/library: UNRESOLVED'
require_fixed docs/HARDWARE_BRINGUP_CHECKLIST.md 'outside BLE sensor/model: UNRESOLVED'
require_fixed docs/HARDWARE_BRINGUP_CHECKLIST.md 'RTC part: UNRESOLVED'
require_fixed docs/HARDWARE_BRINGUP_CHECKLIST.md 'physical actuator backend/pins: UNRESOLVED'
require_fixed docs/HARDWARE_BRINGUP_CHECKLIST.md 'Passing Stage26C is software evidence only; it is not hardware validation.'

echo "pre-hardware readiness audit: PASS"
