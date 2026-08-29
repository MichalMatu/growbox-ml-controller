# Hardware Bring-up Checklist

Status: Stage26C software readiness gate passed. Stage27 begins with a native-ESP-IDF feasibility freeze before physical hardware work.

Passing Stage26C is software evidence only; it is not hardware validation.

## Frozen software boundary before hardware work

The controller architecture is ready for concrete hardware adapters without changing the climate core:

- `CompositeClimateSnapshotProvider` aggregates hardware-neutral inside, outside, clock and schedule/config sources into the existing `ClimateInputSnapshot`;
- `ClimateApplication` keeps the strict input -> processing -> output composition;
- `MappedClimateRoleDriver` maps six stable semantic actuator roles to normalized endpoint writes;
- `ClimateControlLoop` remains the owner of confirmed applied state, OFF recovery and actuator fault latching;
- diagnostics observe the exact consumed input and resulting runtime/output evidence without feeding control state;
- Rule remains authoritative. `MlActive` is not qualified for real actuation.

## Frozen framework/platform policy

### Framework — FROZEN

Hardware implementation must remain **100% native ESP-IDF v5.5.4**.

- Do not add Arduino-ESP32 as an ESP-IDF component.
- Do not move the project to PlatformIO/Arduino.
- Arduino/PlatformIO projects may be reference/donor sources only.
- Reuse framework-independent protocol decoders, register definitions, constants, pin maps and tested behavior when useful, but keep board/runtime ownership native ESP-IDF.

### Preferred board — CONDITIONAL

Preferred first platform is the Elecrow CrowPanel 2.9-inch e-paper ESP32-S3 already used by the user's `esp32s3_LiteGraph` hardware and custom HAT.

Keep it only if the exact board/display/buttons/power sequence can be supported cleanly in native ESP-IDF using official/vendor/native driver sources or a small maintainable native port.

### Fallback board — FROZEN

If CrowPanel support depends on a substantial Arduino-only stack or becomes disproportionate engineering risk, use a plain inexpensive ESP32-S3 devboard.

A display and rotary encoder may be added later. E-paper/buttons are not MVP blockers and must not force Arduino into the project.

## Stage27 input choices

### Inside sensor — PART FROZEN, DRIVER PENDING AUDIT

- part: Sensirion SCD41;
- measurements: air temperature, RH and CO2;
- implementation: native ESP-IDF only;
- exact maintained SCD4x/SCD41 component/driver: pending Stage27A source audit;
- failed reads must remain unavailable/invalid, never synthetic zero values;
- only accepted valid measurements refresh climate freshness.

### Outside BLE sensor — PROTOCOL/MODEL PENDING AUDIT

- purpose: outside temperature/RH;
- BLE stack: native ESP-IDF NimBLE;
- exact sensor/model and advertisement format: pending Stage27A audit;
- existing Xiaomi/PVVX/BTHome code in LiteGraph/MatrixHub is a strong reference candidate;
- select the configured sensor deterministically by stable identity;
- distinguish packet-seen time from last valid climate-measurement time;
- malformed/foreign/partial advertisements must not refresh climate freshness.

### RTC — PART FROZEN, DRIVER PENDING AUDIT

- part: DS3231 with backup battery;
- implementation: native ESP-IDF I2C only;
- exact component/driver: pending Stage27A audit;
- oscillator-stop/lost-power/untrusted time must be surfaced as invalid time until intentionally set/synchronized;
- a readable default/garbage date must not be treated as valid schedule time.

### I2C ownership — DIRECTION FROZEN

Prefer one explicit native ESP-IDF I2C bus owner for SCD41 + DS3231 when the selected board/HAT wiring allows it. Individual device adapters must not independently recreate or repeatedly initialize the same bus.

## Reference/donor repositories

Use as evidence/reference, not runtime dependencies:

- `MichalMatu/esp32s3_LiteGraph`, branch `main`, handoff reference SHA `d9ac2e96812e5ce0a188016994a89bdd9b9edfaf`;
- `MichalMatu/MatrixHub`, branch `develop`, handoff reference SHA `fd5df96c768cdaab647d3589775e1e838e2d2db3`.

LiteGraph is especially useful for proven CrowPanel/HAT wiring and working sensor/BLE/RTC behavior, but it is Arduino/PlatformIO-based. Extract behavior/pure logic rather than importing Arduino ownership.

## Stage27A — native feasibility freeze before implementation

Before writing the hardware bundle, document all of the following:

- exact CrowPanel 2.9 hardware revision and e-paper controller;
- official Elecrow schematic/pin map/power sequence/buttons/PSRAM/flash configuration;
- availability and quality of native ESP-IDF CrowPanel/e-paper examples/drivers;
- exact native SCD41 driver/component;
- exact outside BLE sensor/model/protocol/decoder;
- exact native DS3231 implementation;
- actual I2C controller/pins/address assumptions;
- whether e-paper/buttons are implemented now or deferred;
- final platform choice: CrowPanel or bare ESP32-S3.

Classify each relevant subsystem as `KEEP`, `ADAPT`, `REIMPLEMENT`, `DEFER` or `DROP`.

Do not port Arduino code before this audit is complete.

## Outputs — intentionally not enabled during first input bring-up

Physical actuator backend/pins are still deferred.

- First real-hardware stage uses real inputs + fake/locked outputs.
- Do not energize growbox loads while validating SCD41/BLE/DS3231.
- The custom HAT output mapping may later be reused if compatible with the selected platform, but it must be verified independently.
- Physical relay/MOSFET/PWM mapping, polarity, ratings, safe-OFF behavior, power/ground and protection remain mandatory before real output enablement.

## Stage27 bring-up order

1. Complete Stage27A native feasibility/source audit and freeze exact native choices.
2. Implement SCD41, outside BLE and DS3231 through the existing hardware-neutral input seams while keeping outputs fake/locked.
3. Verify availability, measurement validity, age/freshness and schedule transitions through diagnostics before any physical load can be energized.
4. Exercise invalid, stale and unavailable real-input cases and confirm the existing fail-closed behavior matches host/HIL evidence.
5. Physically verify CrowPanel/e-paper/buttons only if they were retained by Stage27A; they must not block sensor validation.
6. Add the physical output endpoint beneath `MappedClimateRoleDriver`, initially in Rule mode only.
7. Bring up one semantic actuator role at a time and verify endpoint mapping, normalized level, explicit OFF, rejection handling, fail-safe OFF and the actuator fault latch.
8. Verify that rejected physical writes never advance confirmed/effective applied state.
9. Run ML only as `MlShadow` while collecting real traces. Do not enable `MlActive` from simulator/fake-runtime evidence.
10. Re-qualify active ML from real data before considering real actuation authority.

## Evidence required during physical bring-up

For every real input/output backend, retain evidence for:

- exact source revision and hardware configuration;
- detected device/part identity where available;
- bounded startup and diagnostics logs;
- normal readings/writes plus stale/unavailable/rejection cases;
- trusted/untrusted RTC behavior;
- confirmed safe OFF behavior before physical output work;
- no panic/reset loop during the bounded validation window;
- Rule-authoritative operation before any ML shadow collection.

A successful ESP-IDF build, host test or fake-runtime run is not a substitute for these physical checks.

See `docs/STAGE27_NATIVE_IDF_HANDOFF.md` for the fresh-chat bootstrap and hybrid GitHub + Local Agent workflow.
