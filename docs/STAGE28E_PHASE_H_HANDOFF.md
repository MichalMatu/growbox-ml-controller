# Stage28E Phase H continuation handoff

Updated: 2026-09-07
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Local Agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`

## Exact identities

- Formal Phase G exit gate: `7ddb995d1f6cd190fa110f21f0d8dc0eabc61d26`
- Phase H qualified production runtime/tooling source identity: `5a4830db9d10e8cb73d4c617b09122f0844ad899`
- Pre-closed-tent-preparation branch HEAD: `9042559b2d052b2e1942c0a61220bd9b7e74c97f`
- Correct Growbox serial port: `/dev/cu.usbserial-1130`
- Never touch: `/dev/cu.usbserial-10`

Later scripts/docs-only commits are qualification tooling revisions, not automatically a new firmware qualification. Before the next hardware run, the software preflight must prove that no production C/C++ source changed relative to the known pre-preparation branch state.

## Current Stage28E state

A through G are formally complete. H is the only remaining Stage28E phase.

H must prove one bounded normal physical path:

`natural AH/rule request -> binary arbiter OFF->ON -> RF TX -> physical fan`

and then unconditionally restore/prove RF-disabled `fake-locked`.

H is **not complete yet**.

## Current physical experiment boundary

The grow tent was manually closed by the operator at:

- local: `2026-09-07T14:16:42+02:00`;
- UTC: `2026-09-07T12:16:42Z`.

The marker is persisted on the control branch as:

`.agent/task-assets/20260907-stage28e-h-manual-close-marker.json`

The tent now stays closed. No subsequent qualification may require the operator to open or close it.

## Latest H attempt: v5

Task:

`.agent/tasks/20260907-stage28e-h-v5-fast-close.json`

Result:

`.agent/results/20260907-stage28e-h-v5-fast-close.json`

Formal outcome: **primary FAIL, recovery/final PASS**.

The primary observer failed with:

`clean safety-clear fan-OFF open-tent baseline not observed`

This failure is an obsolete test-harness assumption for the current experiment state, not evidence of a production controller/RF failure.

Useful end-of-real-run evidence included:

- firmware/source identity `5a4830db9d10e8cb73d4c617b09122f0844ad899`;
- `outputs=real-bounded`;
- `rf_ready=1`;
- `fan_known=1`, `fan_on=1`;
- `requested_fan≈0.278`;
- `applied_fan=1.000`;
- `safety_latched=0`;
- `force_fan=0`;
- `safety_reason=0`;
- `arbiter_transitions=11`;
- `arbiter_dwell_holds=318` in the retained terminal sample;
- `arbiter_safety_overrides=0`;
- `tx=15`;
- `tx_errors=0`;
- TP357 about `23.20 C / 65.00% RH`;
- Xiaomi/intake about `23.22 C / 57.76% RH`;
- SCD41 CO2 about `823 ppm`.

This is positive controller/RF/physical-state evidence, but it is not a formal H PASS because the observer did not establish the required valid closed-tent normal OFF baseline and then bind the next natural OFF->ON transition to that baseline.

Recovery after v5 succeeded:

- manual RF recovery RC `0`;
- final verifier RC `0`;
- final `outputs=fake-locked`;
- final `rf_ready=0`;
- Shelly master ON;
- final Shelly power about `27.3 W`.

The board was left safe.

## H v6 result and parser root cause

Task:

`.agent/tasks/20260907-stage28e-h-v6-closed-autonomous.json`

Formal outcome: **primary FAIL, recovery/final PASS**.

The primary observer again reported:

`stable safety-clear physical fan-OFF closed-tent baseline not observed`

The raw retained Mac log disproves that physical interpretation. A read-only audit found:

- `24` clean safety-clear physical fan-OFF windows;
- representative OFF windows lasted about `114-145 s`;
- maximum clean OFF duration observed: `145.03 s`;
- runtime ended the real-bounded observation at `arbiter_transitions=46`, `tx=50`, `tx_errors=0`;
- recovery/final completed successfully and final RF-disabled `fake-locked` was proved.

The actual root cause was an observer parser bug. Production emits output-state telemetry through ESP-IDF logging, for example:

`I (...) climate_stage27: stage28d_output ...`

The v6 observer required `line.startswith("stage28d_output ")`. Audit of the exact v6 log found:

- lines containing `stage28d_output `: `576`;
- lines starting with `stage28d_output `: `0`;
- ESP-IDF-prefixed `climate_stage27: stage28d_output ` lines: `576`.

Therefore the observer ignored 100% of arbiter/output-state samples and could never acquire its OFF baseline even though the production controller repeatedly produced valid OFF and ON states. This is a qualification-tooling false negative, not evidence of a controller, arbiter, RF or physical-output failure.

The RC observer is corrected to recognize the `stage28d_output ` marker anywhere in the serial line while preserving the same KV parsing and acceptance criteria. The preflight must regression-test both raw and ESP-IDF-prefixed forms before the next hardware H run.

## Closed-tent observer — release candidate

Repository path:

`scripts/stage28e_phase_h_closed_tent.py`

This is the observer for the next bounded H qualification.

### What it does

It is read/observe-only with respect to the controller/actuators:

- never injects a controller request;
- never writes actuator commands;
- never asks the operator to open/close the tent;
- sends only service-console `status` and `sensors` read requests;
- independently polls the Shelly switch status/power endpoint.

It first requires a stabilized runtime identity:

- exact `--sha` match;
- `outputs=real-bounded`;
- `rf_ready=1`;
- uptime at least 5 seconds.

After that baseline, any ESP-ROM restart marker, runtime lifecycle re-entry or boot-id change is a stop condition.

### Closed-tent normal OFF baseline

The observer requires at least three qualifying output samples spanning at least 10 seconds with:

- `safety_latched=0`;
- `force_fan=0`;
- `safety_reason=0`;
- `fan_known=1`;
- `fan_on=0`;
- `applied_fan<0.01`;
- `tx_errors=0`.

`requested_fan` is deliberately **not** constrained during this baseline. The binary arbiter can legally keep the fan OFF while a request above the ON threshold is waiting for minimum-OFF dwell. Requiring `requested_fan<0.10` caused the earlier false-negative setup problem.

### Natural request and transition

From the physical fan-OFF state the observer requires:

- natural `requested_fan>=0.10`;
- then `fan_known=1`, `fan_on=1`, `applied_fan>=0.99`;
- safety still clear and no force override;
- arbiter transition count greater than at request capture;
- RF TX count greater than at request capture;
- `tx_errors=0`.

No safety-forced fan transition counts as H evidence.

### Independent Shelly support

Because Shelly measures combined controlled-load power rather than fan-only power, the observer rejects a proof if lamp or humidifier state changes between the captured fan request and fan transition. The physical-power proof window then remains open until eight post-transition Shelly samples are collected and at least one subsequent `stage28d_output` sample confirms that lamp/humidifier state is still unchanged. Any confounder change before that proof window is sealed fails the run. Later load changes during the remaining environmental-response window do not rewrite the already sealed fan-power evidence.

With lamp/humidifier stable through that proof window, the observer requires:

- Shelly master remains ON;
- pre-transition power evidence exists;
- post-transition power evidence exists;
- median total-power delta is at least `+1.0 W`.

This is supporting physical evidence. RF TX completion remains transport evidence, not direct load acknowledgement.

### Environmental evidence

The observer consumes `soak_v=2` samples and records:

- TP357 inside T/RH;
- Xiaomi intake T/RH;
- SCD41 T/RH/CO2;
- derived TP357 absolute humidity;
- pre/post temperature slope;
- pre/post absolute-humidity slope;
- pre/post CO2 slope.

Default post-transition observation window: `600 s`.

Default overall observation timeout: `7200 s`.

The formal PASS does not require a particular sign for every environmental slope; those values are retained for effect characterization. The formal path proof is controller request -> arbiter -> RF -> independently supported physical fan transition.

### Temperature guard

Default observer guard:

`TP357 >=27.5 C -> abort observer with RC 42`

The production thermal safety trip remains `>=28 C`. The observer intentionally stops below that threshold because H is a normal-controller proof, not a thermal-safety test.

## Natural controller logic relevant to H

Authoritative controller source:

`lib/environment_control/src/climate/ClimateRuntimeController.cpp`

Schedule source:

`src/climate/runtime/Stage27ScheduleProfile.cpp`

Day profile (`06:00 <= local hour < 22:00`):

- target T `24.5 C`;
- target RH `58%`.

Night profile:

- target T `21.5 C`;
- target RH `65%`.

Binary fan arbiter:

- ON request threshold `0.10`;
- OFF request threshold `0.03`;
- minimum ON dwell `120000 ms`;
- minimum OFF dwell `120000 ms`.

For humidity ventilation, inside RH must exceed target RH + 2 percentage points and intake air must be materially drier in absolute-humidity terms. The useful drying gap begins above about `0.5 g/m3`.

For temperature ventilation when inside is hot and intake is cooler, a practical trigger is approximately an inside-to-intake temperature gap above `2 C`.

Do not manipulate conditions to intentionally hit thermal safety. Natural tent dynamics are sufficient; the bounded observer can wait for a valid cycle.

## RF main-stack policy

The RF-enabled production path previously exposed a real main-task stack overflow at 12 KiB. The qualified policy is:

- RF disabled/fake build: `CONFIG_ESP_MAIN_TASK_STACK_SIZE=12288`;
- RF enabled build: `CONFIG_ESP_MAIN_TASK_STACK_SIZE=16384`.

Do not shrink the RF-enabled stack before or during H.

## Architecture audit before handoff

The production runtime was inspected specifically for responsibility separation before the overnight qualification.

### `runClimateV6RealInputRuntime()`

File:

`src/climate/ClimateV6RealInputRuntime.cpp`

Current file size is about `23 KB`.

The runtime function currently coordinates too many concerns:

- I2C hardware startup/probes;
- SCD41, DS3231 and BLE initialization;
- telemetry storage initialization;
- RF diagnostics initialization;
- real-output binding validation and fail-closed safe-state arming;
- service-console construction;
- input/schedule/application wiring;
- binary arbiter/output-driver wiring;
- lamp safety and thermal-test integration;
- scheduler/control cycle;
- output/fail-safe handling;
- telemetry/platform diagnostics.

This is a genuine god-function risk.

### `Stage28ServiceConsole`

Files:

- `src/climate/runtime/Stage28ServiceConsole.cpp` — about `32 KB`;
- `src/climate/runtime/Stage28ServiceConsole.h`.

The implementation combines:

- UART driver ownership/initialization;
- RX buffering, line editing and echo;
- command parser/dispatcher;
- help/prompt rendering;
- runtime/heap/task-stack/timing diagnostics;
- sensor reporting;
- RF listing/transmit/receive commands;
- RTC write command;
- SD logger status/list/read/selftest;
- Base64/CRC/read-file helpers.

This is a genuine broad-responsibility service object.

### Decision before H

**Do not refactor either production area before formal H.**

Reason: H should qualify the already-measured production runtime, not a freshly reorganized binary. Structural cleanup immediately before the overnight physical proof would trade known behavioral/stack evidence for unnecessary uncertainty.

The current RC therefore changes only qualification tooling/documentation and deliberately leaves production C/C++ untouched.

### Post-H extraction order

After formal H PASS:

1. `runClimateV6RealInputRuntime()`:
   - bootstrap;
   - scheduler/cycle;
   - output/fail-safe;
   - telemetry/diagnostics coordination.
2. `Stage28ServiceConsole`:
   - UART transport + framing;
   - parser/dispatcher;
   - status diagnostics;
   - sensor commands;
   - RF commands;
   - RTC commands;
   - storage commands.

Each extraction should be behavior-preserving, one coherent responsibility at a time, with focused host tests. Do not mix extraction with actuator semantics, AH thresholds, allocator changes or stack shrinking.

## Software-only preflight required before overnight hardware

Before queueing the next real-output task, Local Agent must verify the exact current work-branch HEAD with `resources: []` and `allow_write=false`.

Required checks:

1. fresh remote HEAD equals the expected RC SHA;
2. local tree clean;
3. `git show --check` / `git diff --check` clean;
4. diff from pre-preparation HEAD `9042559b2d052b2e1942c0a61220bd9b7e74c97f` contains only intended `scripts/`/`docs/` files;
5. no `.c/.cc/.cpp/.h/.hpp` production source changed;
6. `python3 -m py_compile scripts/stage28e_phase_h_closed_tent.py`;
7. `python3 scripts/stage28e_phase_h_closed_tent.py --help`;
8. established focused/native host tests pass;
9. established ESP-IDF firmware build passes without flashing;
10. final local tree clean.

Do not call the RC ready for the overnight run before this task has a terminal PASS result.

## Required overnight task wrapper

The next hardware task must be a new immutable task id and contain exactly:

`"agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5"`

Hardware resource:

`"resources": ["board:growbox-s3"]`

Port:

`/dev/cu.usbserial-1130`

The wrapper should:

1. verify exact expected work-branch RC HEAD and qualified production source identity policy;
2. verify/reuse or rebuild the RF-enabled real image with 16 KiB main stack;
3. verify recovery RF image and RF-disabled final fake image;
4. flash real-bounded;
5. run `scripts/stage28e_phase_h_closed_tent.py` with a bounded timeout and `--closure-utc 2026-09-07T12:16:42Z`;
6. capture primary RC without allowing it to skip recovery;
7. flash recovery RF image and run `scripts/stage28e_phase_h_e2e.py recovery`;
8. flash final RF-disabled fake image and run `scripts/stage28e_phase_h_e2e.py final`;
9. fail hard if either recovery or final verification fails;
10. only report formal H PASS if the primary closed-tent observer passed and recovery/final also passed.

A reasonable observer window is `--timeout 7200 --post-seconds 600`. A longer overnight observation may be used only if it remains bounded and the temperature/safety stop conditions stay active.

This is authorization for a bounded qualification only, not continuous unattended real-output production operation.

## Serial-open reset rule

Read:

`docs/ESP32_S3_SERIAL_PORT_RESET.md`

Mandatory order:

`open serial -> tolerate/record port-open reset -> wait for boot stabilization -> request fresh status -> establish post-open baseline -> begin bounded observation`

Any reset/session/lifecycle change after the stabilized baseline is a stop condition.

## Local Agent identity and workflow

- repository: `MichalMatu/growbox-ml-controller`;
- repository id: `growbox-ml-controller`;
- control branch: `agent-control`;
- work branch: `mvp/environment-controller`;
- agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`.

Rules:

- hard repository binding is fail-closed;
- never inspect/queue/execute another repository from this conversation;
- direct GitHub edits are suitable for bounded exact code/docs changes;
- Local Agent is used for Mac commands, builds/tests and devices;
- task IDs and payloads are immutable;
- `expected_head` is unsupported, so exact SHA checks belong inside the task;
- `resources: []` for software-only work;
- `resources: ["board:growbox-s3"]` for serial/flash/device work;
- read terminal `.agent/results/<task-id>.json` before reporting PASS.

## Stop conditions

Stop H and preserve evidence on:

- TP357 reaches observer guard (`>=27.5 C` by default);
- unexplained reset/session/lifecycle change after baseline;
- cumulative counter regression without legitimate wrap;
- coredump/Guru Meditation;
- heap integrity failure;
- critical stack margin;
- unbounded loop/watchdog behavior;
- safety behavior change;
- RF TX error;
- Shelly master OFF;
- lamp/humidifier state changes that confound the fan-only Shelly proof;
- inability to restore safe outputs/final `fake-locked`.

## Fresh-chat bootstrap

Open the next conversation with the same Growbox repository binding. Let Chat Bridge provide a new `LA_CHAT`; do not copy an old chat id.

Use this instruction:

> Continue Growbox Stage28E Phase H only in `MichalMatu/growbox-ml-controller`. First read `AGENTS.md`, `docs/STAGE28E_PHASE_H_HANDOFF.md`, `docs/CURRENT_STATUS.md`, `docs/CONTINUATION_PLAN.md`, `docs/GUIDANCE.md`, and `docs/ESP32_S3_SERIAL_PORT_RESET.md`. Fresh-check `mvp/environment-controller` HEAD and `agent-control:.agent/status/daemon.json` before doing anything. A-G are formally complete; H is not. Qualified production runtime/tooling source identity is `5a4830db9d10e8cb73d4c617b09122f0844ad899`. H v5 failed its obsolete open-tent baseline criterion but recovery/final fake-locked passed. The tent was closed at `2026-09-07T12:16:42Z` and must remain closed; no user action is needed. The repository-tracked observer is `scripts/stage28e_phase_h_closed_tent.py`. First require the software-only RC preflight result to be PASS. Then run one bounded hardware H task: stable safety-clear physical fan OFF, natural `requested_fan>=0.10`, normal arbiter OFF->ON, RF TX increment with zero errors, unconfounded Shelly physical support and environmental response, followed unconditionally by recovery and final RF-disabled `fake-locked`. Never touch `/dev/cu.usbserial-10`. Do not add request/output forcing. Do not start the production runtime/service-console modularity refactor until H formally passes.
