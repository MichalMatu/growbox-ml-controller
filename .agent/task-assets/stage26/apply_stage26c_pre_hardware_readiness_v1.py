from pathlib import Path


def write(path: str, content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


write(
    "scripts/check_pre_hardware_readiness.sh",
    r'''#!/usr/bin/env bash
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
''',
)

write(
    "docs/HARDWARE_BRINGUP_CHECKLIST.md",
    r'''# Hardware Bring-up Checklist

Status: Stage26C software readiness gate. Physical hardware work starts only in Stage27.

Passing Stage26C is software evidence only; it is not hardware validation.

## Frozen software boundary before hardware work

The controller architecture is ready for concrete hardware adapters without changing the climate
core:

- `CompositeClimateSnapshotProvider` aggregates hardware-neutral inside, outside, clock and
  schedule/config sources into the existing `ClimateInputSnapshot`;
- `ClimateApplication` keeps the strict input -> processing -> output composition;
- `MappedClimateRoleDriver` maps six stable semantic actuator roles to normalized endpoint writes;
- `ClimateControlLoop` remains the owner of confirmed applied state, OFF recovery and actuator fault
  latching;
- diagnostics observe the exact consumed input and resulting runtime/output evidence without feeding
  control state;
- Rule remains authoritative. `MlActive` is not qualified for real actuation.

## Manual freeze required before Stage27

Do not implement physical drivers until each item below is resolved deliberately.

- SCD41 driver/library: UNRESOLVED — freeze the ESP-IDF-compatible library/driver, I2C controller,
  address handling, pins, sampling cadence and error/freshness mapping. The SCD41 sensor itself is
  already the planned inside T/RH/CO2 device.
- outside BLE sensor/model: UNRESOLVED — freeze the exact sensor, advertisement format/decoder, BLE
  stack, scan cadence, reconnect/absence behavior and freshness/age mapping.
- RTC part: UNRESOLVED — freeze the backed-up RTC part, library/driver, bus/address/pins, backup-power
  implementation and synchronization policy. Candidate class remains DS3231 or PCF8563; neither is
  selected by Stage26C.
- physical actuator backend/pins: UNRESOLVED — freeze relay/MOSFET/PWM or other endpoint technology,
  endpoint-to-role mapping, pins, active polarity, electrical ratings and physical safe-OFF behavior.
- power/ground/protection: UNRESOLVED — confirm common ground, supply headroom, inductive-load
  protection where applicable and safe power-up/power-loss states before connecting loads.

Record the selected values in repository documentation before adding each concrete backend. Do not
hide these choices inside driver code.

## Stage27 bring-up order

1. Connect and implement real inputs while keeping all outputs fake.
2. Verify SCD41, outside BLE and RTC availability, measurement validity, age/freshness and schedule
   transitions through diagnostics before any physical load can be energized.
3. Exercise invalid, stale and unavailable real-input cases and confirm the existing fail-closed
   behavior matches host/HIL evidence.
4. Add the physical output endpoint beneath `MappedClimateRoleDriver`, initially in Rule mode only.
5. Bring up one semantic actuator role at a time and verify endpoint mapping, normalized level,
   explicit OFF, rejection handling, fail-safe OFF and the actuator fault latch.
6. Verify that rejected physical writes never advance confirmed/effective applied state.
7. Run ML only as `MlShadow` while collecting real traces. Do not enable `MlActive` from simulator or
   fake-runtime evidence.
8. Re-qualify active ML from real data before considering real actuation authority.

## Evidence required during physical bring-up

For every real input/output backend, retain evidence for:

- exact source revision and hardware configuration;
- detected device/part identity where available;
- bounded startup and diagnostics logs;
- normal readings/writes plus stale/unavailable/rejection cases;
- confirmed safe OFF behavior;
- no panic/reset loop during the bounded validation window;
- Rule-authoritative operation before any ML shadow collection.

A successful ESP-IDF build, host test or fake-runtime run is not a substitute for these physical
checks.
''',
)

continuation_path = Path("docs/CONTINUATION_PLAN.md")
continuation = continuation_path.read_text(encoding="utf-8")
old_continuation = '''### Stage26C — pre-hardware readiness gate

Run the complete host/schema/static/ESP-IDF gate, audit the climate-v6 fake path end to end and add
a hardware bring-up checklist. The checklist must leave unresolved BLE/RTC/pin/library choices
explicit for manual freeze before physical work.
'''
new_continuation = '''### Stage26C completed — pre-hardware readiness gate

The software-side readiness gate now audits the reversible app boundary, Rule-authoritative fake
runtime, hardware-neutral input/output seams, diagnostics and the key host/HIL registrations. The
complete host/schema/static gate plus both ESP-IDF v5.5.4 application modes are required before
publication. `docs/HARDWARE_BRINGUP_CHECKLIST.md` records the Stage27 order and deliberately leaves
SCD41 library/bus/pins, outside BLE model/protocol, RTC part and physical actuator backend/pins as
manual freeze items. Passing Stage26C is not hardware validation.
'''
assert old_continuation in continuation
continuation_path.write_text(continuation.replace(old_continuation, new_continuation, 1), encoding="utf-8")

status_path = Path("docs/CURRENT_STATUS.md")
status = status_path.read_text(encoding="utf-8")
status = status.replace("Date: 2026-08-28", "Date: 2026-08-29", 1)
stage26b = '''Stage26B adds a hardware-neutral semantic output mapping beneath `ClimateRoleDriver`. `MappedClimateRoleDriver` maps the six stable roles to configured endpoint identifiers and forwards only finite normalized levels. Enabled mappings propagate explicit OFF writes; disabled/unmapped roles accept OFF without I/O and reject nonzero commands. Host fakes prove deterministic mapping and partial rejection without adding a physical output backend.
'''
stage26c = '''
Stage26C closes the software-only pre-hardware gate. `scripts/check_pre_hardware_readiness.sh` audits the reversible legacy/climate-v6-fake boundary, Rule-authoritative fake runtime, neutral composite-input and semantic-output seams, diagnostics and the key host/HIL registrations. The release gate also requires the full non-hardware Python/schema/host/clang-tidy suite and both ESP-IDF v5.5.4 app modes. `docs/HARDWARE_BRINGUP_CHECKLIST.md` leaves SCD41 library/bus/pins, outside BLE model/protocol, RTC part and physical actuator backend/pins explicitly unresolved for manual freeze before Stage27. Simulator/fake PASS remains software evidence, not hardware validation.
'''
assert stage26b in status
status = status.replace(stage26b, stage26b + stage26c, 1)
old_next = '''1. Prove the strict IPO composition with interchangeable fake Input/Output implementations using
   the same public interfaces intended for future hardware.
2. Keep the legacy demo intact while proving the new climate-v6 application composition path.
3. Add concrete SCD41 / BLE / RTC providers only after parts and libraries are frozen.
4. Add concrete semantic actuator-role drivers.
5. Bring up real hardware in Rule mode first.
6. Run ML only in `MlShadow` while collecting real traces.
7. Re-qualify ML from real data before considering active ML actuation.
'''
new_next = '''1. Manually freeze the unresolved physical choices in `docs/HARDWARE_BRINGUP_CHECKLIST.md`.
2. Start Stage27 with real inputs plus fake outputs and verify freshness/error/schedule diagnostics.
3. Add real outputs only after the input path is proven, and operate them in Rule mode first.
4. Run ML only in `MlShadow` while collecting real traces.
5. Re-qualify ML from real data before considering active ML actuation.
'''
assert old_next in status
status_path.write_text(status.replace(old_next, new_next, 1), encoding="utf-8")
