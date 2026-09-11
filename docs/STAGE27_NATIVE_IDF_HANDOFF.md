# Stage27 native ESP-IDF handoff

Date: 2026-08-29
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Software-only Stage26C baseline before this handoff: `bbf8684d2817f630ddca08837ddc8860a28eb660`

This document freezes the decisions made immediately before moving the work to a new ChatGPT conversation. It is the primary Stage27 bootstrap together with `AGENTS.md`, `docs/CURRENT_STATUS.md`, `docs/CONTINUATION_PLAN.md`, and `docs/HARDWARE_BRINGUP_CHECKLIST.md`.

## Frozen direction

### Framework

The hardware implementation must remain **100% native ESP-IDF**.

- ESP-IDF v5.5.4 remains the firmware baseline.
- Do not add Arduino-ESP32 as an ESP-IDF component.
- Do not migrate the project to PlatformIO/Arduino.
- Arduino/PlatformIO repositories may be used as hardware/protocol references, but Arduino runtime APIs must not leak into the growbox implementation.
- Small framework-independent algorithms, packet decoders, register definitions, constants, pin maps and hardware behavior may be adapted when useful, after checking their assumptions.

This is a deliberate product decision. If a preferred board would require a large Arduino compatibility layer, prefer a simpler board rather than mixing frameworks.

### Preferred board and fallback

Preferred platform for the first native bring-up:

- Elecrow CrowPanel 2.9-inch e-paper ESP32-S3 used by `MichalMatu/esp32s3_LiteGraph`;
- the user's existing custom HAT may be reused if its board wiring/output mapping remains useful;
- e-paper and buttons are valuable diagnostics/UI features but are **not required for the first climate-controller MVP**.

Fallback platform:

- a plain inexpensive ESP32-S3 development board;
- later add a cheap display and rotary encoder only if they provide enough value.

Decision rule:

1. Keep CrowPanel when its exact 2.9-inch board, display controller, power/init sequence, buttons and required peripherals can be supported cleanly with native ESP-IDF using official/vendor/native driver sources or a small maintainable native port.
2. If the CrowPanel path depends on a substantial Arduino-only display/board stack or becomes the dominant implementation risk, abandon that board for the first MVP and use a plain ESP32-S3 devboard.
3. Do not add Arduino merely to preserve the e-paper screen or buttons.
4. Sensors/control correctness outrank display convenience.

### First real input set

The intended Stage27 input bundle is:

- inside: Sensirion SCD41 — air temperature, relative humidity and CO2;
- outside: BLE temperature/RH sensor — exact model/protocol must be frozen after source audit; existing Xiaomi/PVVX/BTHome-compatible code is a strong reference candidate;
- wall clock: DS3231 with backup battery.

The controller core must continue seeing these devices only through the existing hardware-neutral interfaces beneath `CompositeClimateSnapshotProvider`.

### Outputs during input bring-up

All outputs stay fake/locked while real inputs are introduced.

Do not energize physical growbox loads in the first Stage27 implementation task. Physical output/HAT support is a later gate after real-input freshness, validity, diagnostics and fail-closed behavior are proven on hardware.

Rule remains authoritative. ML remains `MlShadow` only for real-hardware data collection until explicitly re-qualified from real traces.

## Reference repositories

Use the following repositories as **evidence/reference sources**, not as framework dependencies.

### LiteGraph

Repository: `MichalMatu/esp32s3_LiteGraph`
Reference branch: `main`
Reference SHA observed at this handoff: `d9ac2e96812e5ce0a188016994a89bdd9b9edfaf`

Why it matters:

- it runs on the user's actual ESP32-S3/CrowPanel/HAT setup;
- it contains proven board wiring/pin behavior and working integrations;
- it is modular enough to identify hardware boundaries;
- it may contain useful SCD41/BLE/RTC/e-paper/button/HAT behavior, protocol parsing, constants or tests.

Constraint: LiteGraph is Arduino/PlatformIO-based. Do not copy framework-coupled `Wire`, Arduino GPIO/task/timing, setup/loop or Arduino library ownership into growbox. Extract behavior and reusable pure logic only when that is simpler than using a native ESP-IDF implementation.

### MatrixHub

Repository: `MichalMatu/MatrixHub`
Reference branch: `develop`
Reference SHA observed at this handoff: `fd5df96c768cdaab647d3589775e1e838e2d2db3`

Use MatrixHub as a secondary reference when it has a newer/cleaner implementation of BLE, DS3231, board behavior or other relevant hardware than LiteGraph.

## Stage27 must start with a native-feasibility audit

Do **not** begin by porting Arduino code. The next chat should first perform a precise source audit and write down what can be implemented natively and what should be dropped.

Research order:

1. Identify the exact Elecrow CrowPanel 2.9-inch ESP32-S3/e-paper hardware revision used by LiteGraph.
2. Find official Elecrow source, schematic, pin map, e-paper controller identity, power/init requirements, buttons, flash/PSRAM configuration and any official native ESP-IDF example for that exact model or directly compatible controller.
3. Find the best maintained native ESP-IDF SCD4x/SCD41 driver/component compatible with IDF 5.5.4; compare it with the behavior already proven in LiteGraph.
4. Find/assess a native ESP-IDF DS3231 implementation. Preserve oscillator-stop/lost-power validity semantics; a syntactically readable but untrusted RTC time must not be treated as valid.
5. Use native ESP-IDF NimBLE for BLE scanning. Audit LiteGraph/MatrixHub only for advertisement filtering, Xiaomi/PVVX/BTHome parsing and real packet examples/tests that can be adapted without Arduino dependencies.
6. Determine whether SCD41 and DS3231 can share one native ESP-IDF I2C bus cleanly on the selected board/HAT.
7. Audit CrowPanel e-paper/buttons separately from the sensor bundle. If they create disproportionate native-port work, mark them deferred and select the bare ESP32-S3 fallback.
8. Produce an explicit KEEP / ADAPT / REIMPLEMENT / DEFER / DROP table before writing real hardware code.

The audit must distinguish:

- official vendor/native ESP-IDF evidence;
- reusable pure logic from the user's donor repositories;
- Arduino-specific code that should not move;
- assumptions that require physical confirmation.

## Required native input semantics

### SCD41

A failed read must never be converted into a plausible numeric value such as zero.

Track at least:

- availability;
- validity;
- last successful measurement time;
- temperature;
- RH;
- CO2.

Only a valid accepted measurement refreshes measurement freshness. The existing runtime decides fail-closed behavior from validity/age.

### BLE outside sensor

Keep scanning, protocol decoding and climate-source adaptation separable.

Recommended shape:

`ESP-IDF NimBLE scanner -> advertisement -> protocol decoder -> sensor state -> outside climate source`

Requirements:

- select the configured sensor deterministically by stable identity (MAC/device id as appropriate), never simply the strongest nearby compatible advertisement;
- distinguish `last packet seen` from `last valid T/RH measurement`;
- malformed/partial advertisements must not refresh climate freshness;
- RSSI/battery/protocol/decode errors may be diagnostics but are not climate freshness themselves;
- preserve captured real advertisement payloads as host-test fixtures where possible.

### DS3231

Use native ESP-IDF I2C access/driver/component.

Requirements:

- backed-up clock is the selected RTC direction;
- expose availability separately from trusted validity;
- oscillator-stop/lost-power state must make time invalid until intentionally synchronized/set;
- do not silently accept a default/garbage date as valid schedule time.

### Shared I2C ownership

Prefer one explicit ESP-IDF I2C bus owner for SCD41 + DS3231 when hardware wiring permits it. Individual device adapters must not independently recreate/reinitialize the same bus.

## Stage27 implementation order after the audit

### Stage27A — native platform/input feasibility freeze

Documentation/research outcome only:

- exact board decision: CrowPanel or bare ESP32-S3;
- exact e-paper/buttons decision: implement now or defer;
- exact native SCD41 driver/component;
- exact native BLE stack + protocol/model;
- exact native DS3231 implementation;
- bus/pin/power assumptions documented;
- no Arduino runtime dependency.

### Stage27B — real input bundle, fake outputs

Implement the selected native platform and all three input classes through the existing neutral interfaces:

- SCD41 inside source;
- BLE outside source;
- DS3231 clock source;
- `CompositeClimateSnapshotProvider` composition;
- bounded diagnostics;
- outputs remain fake/locked.

Add host tests for pure decoders/mapping/freshness wherever possible and compile using the real ESP-IDF v5.5.4 gate.

### Stage27C — physical input validation

Requires the user/device hardware.

Validate:

- device discovery/identity;
- realistic readings;
- freshness/age progression;
- unplug/unavailable/invalid cases;
- BLE absence and malformed packet behavior;
- RTC lost-power/untrusted-time behavior;
- no panic/reset loop;
- Rule-authoritative runtime with fake outputs.

Only after this evidence should physical outputs be considered.

## Hybrid GitHub + Local Agent workflow

This section freezes the updated project workflow for future chats.

The planner is allowed to change source files **directly through GitHub** when that is the fastest and clearest method, then use `local-agent` as the real local compiler/test executor. Direct GitHub editing and local-agent execution are complementary; neither removes the evidence rules.

### Source-edit path A — direct GitHub commit

Prefer direct GitHub writes for:

- documentation/handoff updates;
- small isolated code changes where the exact replacement is clear;
- small configuration/build metadata changes;
- changes that are easier to review as an immediate remote commit than to encode as a task patch.

Before a direct write:

1. inspect fresh `.agent/status/daemon.json` on `agent-control`;
2. do not write concurrently with an active local-agent task touching the same work branch;
3. fetch the current remote `mvp/environment-controller` HEAD;
4. write only to the work/source branch, never product code to `agent-control`;
5. retain the returned commit SHA as the expected source revision.

A direct GitHub code commit is **not considered verified merely because GitHub accepted it**. Verify the exact committed SHA through relevant CI when it covers the required checks. When Mac tooling, device access or missing CI coverage requires local execution, queue a new immutable verification task that checks the exact SHA and runs the appropriate focused and required full gates.

### Source-edit path B — local-agent performs the edit

Prefer local-agent editing when:

- many files must be changed atomically;
- shell/code-generation/refactoring tools are useful;
- local inspection is required to construct the change;
- the change is tightly coupled to local compile/test iteration;
- direct GitHub editing would create many awkward commits.

Use a new unique task id and `workflow_policy: efficient-verification-v1` for non-trivial code changes.

### Hybrid path

A fast normal sequence may be:

1. planner audits GitHub/source and fresh daemon state;
2. planner commits a bounded change directly to `mvp/environment-controller`;
3. planner records the exact new remote SHA;
4. planner checks relevant CI for that exact SHA, or queues one local task that verifies that SHA and runs the required focused/full checks when local execution is needed;
5. planner follows the exact run/task digest/attempt;
6. planner reads the terminal result before continuing;
7. if verification finds a defect, either make another bounded direct GitHub fix or queue a new edit task, but always use a new local-agent task id;
8. after source changes following a failed full gate, rerun focused verification first and then one final full gate.

Never edit remotely while local-agent is concurrently producing a commit on the same branch. The one-task-at-a-time rule still applies to executor tasks, and source concurrency must also be avoided.

### Evidence order remains unchanged

1. terminal result for exact task id/digest;
2. active run for exact attempt when still running;
3. daemon status;
4. exact target source/commit/diff/tests;
5. planner analysis.

`expected_head` is not implemented. Assert expected source SHA explicitly in task commands/stages.

For docs-only direct commits with no executable/configuration impact, a firmware build is not automatically required; still verify the remote branch/file content after the write. For code/build/config changes, relevant exact-commit CI or local execution evidence is required before claiming the change works. Hardware claims still require device evidence.

## Fresh-chat bootstrap

In the new ChatGPT conversation:

1. Read `AGENTS.md`.
2. Read this file completely.
3. Read `docs/CURRENT_STATUS.md`, `docs/HARDWARE_BRINGUP_CHECKLIST.md` and the relevant architecture/interface files.
4. Fetch fresh `agent-control:.agent/status/daemon.json` and do not rely on the handoff's daemon state.
5. Fetch fresh remote HEAD of `mvp/environment-controller`.
6. Inspect the latest terminal local-agent result if a newer task exists.
7. Do **not** reopen completed Stage25/26 work.
8. Start with the Stage27A native ESP-IDF feasibility/source audit described above.
9. Search official/current sources before implementing hardware; current vendor/component availability is time-sensitive.
10. Present the user with a concise KEEP / ADAPT / REIMPLEMENT / DEFER / DROP conclusion, including whether CrowPanel survives the native-only requirement.
11. Only then create the first hardware implementation task/change.

## User preferences relevant to this stage

- communicate with the user in Polish;
- keep code, commit messages, task JSON and repository documentation in English;
- prefer concrete implementation progress over repeated generic audits;
- ESP32-S3 PSRAM is available and may be used sensibly; do not impose artificially tiny DRAM buffers when PSRAM is appropriate;
- preserve modular boundaries and avoid unnecessary rewrites of proven logic;
- however, do not preserve Arduino merely to reuse code — native ESP-IDF is the frozen framework decision;
- if CrowPanel native support is not worth the complexity, simplify hardware instead of complicating software.
