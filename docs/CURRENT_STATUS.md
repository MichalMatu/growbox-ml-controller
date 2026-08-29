# Current controller status

Date: 2026-08-29
Development branch: `mvp/environment-controller`
Fresh-chat bootstrap: `docs/CONTINUATION_PLAN.md`
Stage27 handoff: `docs/STAGE27_NATIVE_IDF_HANDOFF.md`

This is the short source of truth for the current climate-controller product path. Historical
simulator, browser-contract and repository-convergence documents remain for reproducibility, but
they must not be read as the current climate runtime architecture.

## Authoritative climate path

Climate-v6 is the active migration target for new controller work:

- schema v6 / contract `climate-mvp-v1`;
- 44 runtime-observable input features;
- 6 semantic ML-controlled outputs: heater, cooler, exhaust fan, humidifier, dehumidifier and CO2 doser;
- bounded model shape `44 -> 32 -> 32 -> 6` retained for compatibility/research;
- Rule remains the authoritative runtime policy;
- `MlShadow` evaluates ML without changing the applied command;
- `MlActive` is an explicit research opt-in and is not qualified for real growbox actuation;
- deterministic arbitration and safety remain authoritative over every policy proposal;
- effective-actuator state advances only from the final applied semantic command.

The scientific rationale and rejected alternatives are frozen in `docs/ML_DECISION_REPORT.md`.

## Software-only controller work completed through Stage26C

The C++ climate-v6 runtime and hardware-neutral seams are complete through the pre-hardware gate.
Important completed pieces include:

- `ClimateFeatureEncoder` and `ClimateRuntimeController` with Rule / ML_SHADOW / ML_ACTIVE modes;
- trend and effective-actuator state estimation;
- Python/C++ golden parity;
- validated trace schema, streaming NDJSON recording, deterministic replay and counterfactual ML;
- `ClimateControlLoop` with fail-closed input handling, best-effort OFF on actuator rejection and an actuator fault latch;
- deterministic fake runtime and long virtual-HIL fault/soak coverage;
- versioned read-only climate diagnostics;
- `ClimateApplication` as the constructor-injected composition root;
- `CompositeClimateSnapshotProvider` with separate inside/outside/clock/config interfaces;
- `MappedClimateRoleDriver` beneath the six stable semantic actuator roles;
- `scripts/check_pre_hardware_readiness.sh` plus full ESP-IDF v5.5.4 dual-app-mode gate.

The last software-only pre-hardware publication before the Stage27 handoff was:

`bbf8684d2817f630ddca08837ddc8860a28eb660` — `Add pre-hardware readiness gate`.

The Stage27 handoff documentation is newer than that baseline and intentionally freezes the next hardware direction without yet claiming hardware validation.

## Hardware-neutral I/O seam remains authoritative

`src/climate/ClimateIoAdapters.*` is the application-side boundary for concrete hardware work.

- `ClimateSnapshotProvider` supplies runtime-observable measurements/configuration.
- `CompositeClimateSnapshotProvider` aggregates inside, outside, wall-clock and schedule/config sources.
- `ClimateInputAdapter` maps the snapshot into the existing processing path.
- `ClimateRoleDriver` accepts normalized semantic role commands.
- `MappedClimateRoleDriver` maps semantic roles to configured endpoint identifiers.
- `ClimateControlLoop` owns confirmed previous actions, OFF recovery and the actuator fault latch.
- Hardware providers/drivers must not duplicate policy, trend state or confirmed applied state.

The climate core must remain independent of SCD41, BLE, RTC, GPIO, e-paper, relay/PWM or board-specific details.

## Frozen Stage27 framework/platform direction

The hardware implementation is now frozen to **100% native ESP-IDF**.

- ESP-IDF v5.5.4 remains the baseline.
- Do not add Arduino-ESP32 as a component.
- Do not migrate to PlatformIO/Arduino.
- `MichalMatu/esp32s3_LiteGraph` and `MichalMatu/MatrixHub` are donor/reference repositories only.
- Reusable pure protocol/decoder/register/pin-map logic may be adapted, but Arduino runtime ownership must not move into growbox.

Preferred board:

- Elecrow CrowPanel 2.9-inch e-paper ESP32-S3 used by LiteGraph, together with the user's existing HAT, **only if** the exact board/display/buttons can be supported cleanly in native ESP-IDF.

Fallback:

- plain inexpensive ESP32-S3 devboard;
- display/rotary encoder may be added later and are not MVP blockers.

If native CrowPanel support becomes disproportionately complex or requires an Arduino compatibility layer, simplify the hardware and use the devboard rather than complicating the firmware.

See `docs/STAGE27_NATIVE_IDF_HANDOFF.md` for the exact decision gate and source-audit plan.

## First Stage27 real input set

Current selected direction:

- inside: Sensirion SCD41 for air temperature, RH and CO2;
- outside: BLE temperature/RH sensor, exact model/protocol to be frozen by the native source audit; Xiaomi/PVVX/BTHome code in the user's existing projects is a strong reference;
- system time: DS3231 with backup battery;
- outputs: remain fake/locked during first real-input bring-up.

SCD41 + DS3231 should preferably share one explicitly owned native ESP-IDF I2C bus when board wiring permits it. BLE should use native ESP-IDF NimBLE. RTC lost-power/oscillator-stop state must be represented as invalid time rather than silently accepted.

## Stage27 begins with research, not an Arduino port

The next action is a native-feasibility/source audit before implementation:

1. identify the exact CrowPanel 2.9 board/display controller/revision used by LiteGraph;
2. inspect official Elecrow sources/schematic/pin map and native ESP-IDF examples where available;
3. select a maintained native ESP-IDF SCD41/SCD4x driver compatible with IDF 5.5.4;
4. select/implement native DS3231 access with trusted-time validity semantics;
5. select native ESP-IDF NimBLE plus the exact outside sensor/protocol decoder;
6. compare the donor repositories only for proven hardware behavior and reusable pure logic;
7. classify each part as KEEP / ADAPT / REIMPLEMENT / DEFER / DROP;
8. decide CrowPanel versus bare ESP32-S3 before writing the real hardware bundle.

E-paper/buttons are useful but may be deferred. Sensor/control correctness is the priority.

## Physical bring-up order

After the native feasibility freeze:

1. implement all selected real inputs while keeping outputs fake/locked;
2. verify SCD41/BLE/DS3231 availability, validity, age/freshness and diagnostics;
3. physically exercise stale/invalid/unavailable/lost-time behavior and confirm fail-closed semantics;
4. only then add a physical output endpoint beneath `MappedClimateRoleDriver`, initially Rule-authoritative;
5. bring up one semantic actuator role at a time;
6. collect real traces with ML only in `MlShadow`;
7. re-qualify ML from real data before considering active ML actuation.

A successful build or fake-runtime test is not physical hardware evidence.

## Local Agent workflow update

Future chats may use a hybrid workflow:

- make a small clear change directly on the GitHub work branch when that is faster;
- then use local-agent to synchronize to the exact resulting SHA and perform real local compile/test/verification;
- for broad/refactoring/local-iteration work, let local-agent perform the edit itself;
- never make direct branch edits concurrently with an active local-agent task touching that branch;
- never treat a direct GitHub code commit as verified until local-agent evidence confirms the relevant tests/build;
- docs-only direct commits do not automatically require a firmware build when they have no executable/config impact.

The complete project-specific procedure is frozen in `docs/STAGE27_NATIVE_IDF_HANDOFF.md`. Canonical executor/evidence rules remain in `MichalMatu/local-agent/docs/AUTONOMOUS_CHAT_LOOP.md` and `docs/OPERATIONS.md`.

## Next steps

1. Read `docs/STAGE27_NATIVE_IDF_HANDOFF.md` in the next chat.
2. Fetch fresh daemon state and the current remote work-branch HEAD.
3. Perform the Stage27 native source/feasibility audit; do not reopen completed Stage25/26 work.
4. Freeze exact native board/driver/protocol choices in repository docs.
5. Implement the real SCD41 + BLE + DS3231 input bundle with fake outputs.
6. Validate on physical hardware before enabling real actuator outputs.
