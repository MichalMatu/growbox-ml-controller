# Stage28E Phase H continuation handoff

Updated: 2026-09-07
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Local Agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`

## Exact identities

- Formal Phase G exit gate: `7ddb995d1f6cd190fa110f21f0d8dc0eabc61d26`
- Formal Phase G docs close: `1eb2772f65ddfa82ba185e5658b2c41899f118d4`
- Phase G runtime/source SHA: `389453882f0e0d2209c5bdece7eaf443895aa7ba`
- Current Phase H runtime/tooling source SHA: `5a4830db9d10e8cb73d4c617b09122f0844ad899`
- Correct Growbox serial port: `/dev/cu.usbserial-1130`
- Never touch: `/dev/cu.usbserial-10`

Any later documentation-only commit must not be confused with the firmware identity above. Before hardware work, compare the fresh work-branch HEAD with `5a4830db9d10e8cb73d4c617b09122f0844ad899`; if only the documentation files from this handoff changed, the qualified runtime source remains `5a4830db9d10e8cb73d4c617b09122f0844ad899`.

## Current Stage28E state

A through G are formally complete. H is the only remaining Stage28E phase.

H must prove one bounded physical path:

`natural AH/rule request -> binary arbiter OFF->ON -> RF TX -> physical fan`

and then restore/prove `fake-locked`.

H is **not complete yet**. Do not convert safety-forced ventilation into AH evidence.

## Phase H work completed so far

### Request-interface inspection

No production AH/fan request injector or override exists. Do not add one solely to manufacture a Phase H PASS. The thermal test sequence is also not an AH-path substitute.

The physical harness is:

`scripts/stage28e_phase_h_e2e.py`

It accepts the exact firmware SHA through `--sha`; it does not hard-code the old H SHA and it never creates an actuator request.

### Physical v1

`.agent/tasks/20260907-growbox-stage28e-phase-h-physical-e2e-v1.json`

Invalid task JSON. The daemon rejected it before execution. It touched no hardware.

### Physical v2

This run exposed a real RF-enabled main-task stack overflow.

Root-cause evidence:

- `runClimateV6RealInputRuntime()` has the same compiler frame in RF and fake builds: `0x7f0 = 2032 B`;
- `RuntimeIoOwner`, including RF diagnostics, is static/process-lifetime storage;
- the Stage27C 12 KiB main stack had been qualified only with fake-locked outputs;
- entering the ESP-IDF RMT initialization path consumed additional call-depth headroom and overflowed the 12 KiB main stack.

Fix:

- `config/idf/sdkconfig.defaults.stage28rf` restores `CONFIG_ESP_MAIN_TASK_STACK_SIZE=16384` for RF-enabled builds;
- `scripts/stage27c_crowpanel.sh` appends this overlay only when `GROWBOX_RF433_LOOPBACK_ENABLED=1`;
- fake/non-RF Stage27C builds remain at 12 KiB.

Dual-build verification passed on exact SHA `5a4830db9d10e8cb73d4c617b09122f0844ad899`:

- fake / RF disabled: `12288 B`;
- RF enabled: `16384 B`.

Do not undo this distinction without new measured evidence.

### Physical v3

Task:

`.agent/tasks/20260907-growbox-stage28e-phase-h-physical-e2e-v3.json`

Result:

`.agent/results/20260907-growbox-stage28e-phase-h-physical-e2e-v3.json`

Primary H gate failed only because the required AH-driven OFF->ON prestate was not observed.

Important positive evidence from the real-bounded runtime:

- no stack overflow;
- stable boot/session `8b596499` through the bounded real run;
- `outputs=real-bounded`;
- `rf_ready=1`;
- internal free/min/largest approximately `218592 / 218060 / 176128 B`;
- PSRAM free approximately `8358772 B`;
- main stack configured `16384 B`;
- worst observed main free HWM approximately `2600 B`;
- loop max approximately `845193 us`, zero loop overruns;
- natural `requested_fan` approximately `0.444-0.500`;
- after startup recovery: `safety_latched=0`, `force_fan=0`, `safety_reason=0`;
- physical fan was ON and `applied_fan=1.000`;
- `arbiter_transitions=1`;
- `arbiter_safety_overrides=1`;
- `tx=5`, `tx_errors=0`.

Why this is not H PASS:

startup lamp safety saw temperature unavailable before the first usable TP357 sample. That latched safety and forced the exhaust fan ON. By the time safety recovered, the natural AH request was already high, so there was no clean normal-mode `fan OFF + request >= 0.10` prestate. The harness correctly failed with:

`natural requested_fan>=0.10 not observed in bounded window`

The run therefore proves the fixed RF runtime is stable and that automatic RF can drive the fan, but it does **not** yet prove the required AH/rule OFF->ON transition independently of startup safety.

Recovery after v3 passed:

- manual fake-locked RF recovery PASS;
- fan OFF;
- humidifier OFF;
- lamp ON;
- Shelly master ON;
- final RF-disabled `fake-locked` PASS;
- final Shelly power about `26.9 W`;
- `manual=0 final=0`.

The board was left safe.

## Exact natural fan-request logic

Authoritative rule source:

`lib/environment_control/src/climate/ClimateRuntimeController.cpp`

Current schedule source:

`src/climate/runtime/Stage27ScheduleProfile.cpp`

Day profile, local hour `06:00 <= hour < 22:00`:

- target temperature `24.5 C`;
- target RH `58%`;
- RH control mode;
- exhaust fan available;
- humidifier available.

Night profile:

- target temperature `21.5 C`;
- target RH `65%`.

### Humidity ventilation path

RH is considered too humid when:

`inside_RH > target_RH + 2%`

Humidity level is approximately:

`(inside_RH - target_RH - 2) / 18`, clipped to `0..1`.

Ventilation for drying also requires outside/intake temperature and RH to be usable and intake air to be materially drier in absolute-humidity terms.

The absolute-humidity drying gap must exceed `0.5 g/m3`; drying benefit scales over `3.0 g/m3`.

For the fan request to reach the binary-arbiter ON threshold `0.10` through this path, the useful practical daytime condition is approximately:

- TP357 inside RH at least `61.8%`, and
- inside absolute humidity at least about `0.8 g/m3` above the Xiaomi/intake absolute humidity.

For a clean daytime OFF baseline, keep TP357 RH at or below about `60%` and avoid a separate temperature-ventilation request.

### Temperature ventilation path

The rule evaluates a 20% outside-air mix. Ventilation is requested only when that mix improves the temperature error score by more than `0.08`.

When the inside is hotter than target and Xiaomi/intake is cooler, this is approximately equivalent to needing:

`inside_temperature - intake_temperature > 2 C`

before the temperature ventilation path activates. A difference just above 2 C already gives a request slightly above the arbiter ON threshold.

This is useful for the physical test because the lamp can warm the closed tent while the Xiaomi stays outside. Do **not** approach the 28 C thermal trip. A practical target is roughly `26-27 C` inside with intake around `23-24 C`, while continuously confirming `safety_latched=0`.

### Binary fan arbiter

Current thresholds:

- ON request threshold: `0.10`;
- OFF request threshold: `0.03`;
- minimum ON dwell: `120000 ms`;
- minimum OFF dwell: `120000 ms`.

Safety overrides bypass normal dwell and must not be counted as the Phase H AH transition.

## Startup lamp-safety behavior

Source:

`src/climate/Stage28dLampSafety.{h,cpp}`

Safety limits:

- trip: TP357 `>=28 C`;
- recovery threshold: TP357 `<=26 C`;
- recovery hold: 10 continuous minutes.

If TP357 is unavailable/stale during an early cycle, safety latches `TemperatureUnavailable`, turns the scheduled lamp OFF, and forces exhaust ON. Once latched, it will clear only after TP357 remains `<=26 C` continuously for 10 minutes.

This startup behavior is expected and must be distinguished from an unexplained post-baseline reset or safety fault.

## Recommended physical preparation for the next H run

Do **not** start by sealing the tent and intentionally driving TP357 above 28 C. That would prove only thermal safety and repeat the v3 evidence problem.

Preferred sequence:

1. Keep Xiaomi/intake sensor outside the tent.
2. Put TP357 in the controlled inside location, but initially keep the tent ventilated/open enough that:
   - TP357 stays `<=26 C`;
   - daytime TP357 RH is preferably `<=60%`;
   - no normal fan request remains above the OFF threshold.
3. Start the exact real-bounded firmware and serial harness.
4. Establish the mandatory post-serial-open boot/session baseline.
5. If startup safety latched because TP357 was initially unavailable, keep TP357 `<=26 C` continuously until the 10-minute recovery completes.
6. Require evidence that safety is clear: `safety_latched=0 force_fan=0 safety_reason=0`.
7. Require the physical/arbiter fan to reach OFF in normal mode. Because the startup safety fan has already been ON much longer than the 120 s minimum-ON dwell by this point, a low natural request should permit the normal OFF transition.
8. Once fan OFF is observed, close the tent / enable the intended lamp warming while keeping TP357 safely below 28 C. It is fine for the natural request to rise immediately; the 120 s minimum-OFF dwell should then produce visible dwell evidence.
9. Prefer a clean temperature trigger around `26-27 C` while Xiaomi/intake remains roughly `23-24 C`, or a humidity trigger above approximately `62% RH` with drier Xiaomi intake air.
10. Require `requested_fan>=0.10`, then the normal arbiter OFF->ON transition, RF TX increment with `tx_errors=0`, and independent physical/Shelly support.
11. Fail on any post-baseline reset/session change, RF error, heap integrity failure, critical stack margin, unsafe thermal state, or failed recovery.
12. Always run manual safe recovery and final RF-disabled `fake-locked` verification.

If RH remains around the v3 value of `68-69%` during the entire 10-minute startup-safety recovery, the natural request will already be high when safety clears and the fan is likely to remain ON. That is not a useful H setup.

## Serial-open reset rule

Read:

`docs/ESP32_S3_SERIAL_PORT_RESET.md`

Mandatory order:

`open serial -> tolerate/record port-open reset -> wait for boot stabilization -> request fresh status -> establish post-open baseline -> begin bounded observation`

Any reset/session/lifecycle change after that baseline is a stop condition.

## Local Agent / Sandbox-style workflow for this repository

`AGENTS.md` is the repository-local contract.

Key points:

- Local Agent is a deterministic executor, not the planner/coding model.
- Hard binding is fail-closed. Never borrow another repository binding.
- `agent-control` is control-plane only; product/docs changes belong on `mvp/environment-controller`.
- Task IDs/payloads are immutable; interrupted tasks are not automatically replayed.
- `expected_head` is not implemented; exact SHA must be checked explicitly in an early command/stage.
- use `resources: []` for repository-local software/docs/build work;
- use `resources: ["board:growbox-s3"]` for USB/serial/flash/device work;
- read `.agent/status/daemon.json` before writes/device work;
- follow `.agent/runs/...` while running and read `.agent/results/...` before reporting PASS;
- direct GitHub edits are appropriate for bounded exact diffs; Local Agent is preferred for Mac commands, local builds/tests, and hardware;
- hybrid flow is valid: direct GitHub commit, then Local Agent read-only verification of the exact committed SHA;
- avoid repository-wide source grep through generated/build directories; use narrow source paths such as `src/` and `lib/environment_control/src/`.

`AGENTS.md` points to the canonical Local Agent documents in `MichalMatu/local-agent/main/docs/AUTONOMOUS_CHAT_LOOP.md` and `docs/OPERATIONS.md`. This chat is hard-bound to `MichalMatu/growbox-ml-controller`, so it must not inspect another repository. If canonical Local Agent source itself must be inspected, use a separate explicitly rebound conversation rather than violating this repository binding.

No repository-local document describing a separate `Sandbox Pack` workflow was found. For this Growbox task, treat the practical sandbox/hybrid mode as: planner/direct GitHub for exact bounded edits plus Local Agent for exact-SHA local execution and device evidence, under the rules above.

## Modularity backlog — after formal H only

Do not mix the following refactor with the pending physical H proof. Any production refactor now would change the exact runtime SHA and invalidate the clean comparison with v3.

After H is formally closed, start a separate architecture-hardening continuation with behavior-preserving extractions.

Priority 1: split `runClimateV6RealInputRuntime()`.

Suggested seams:

- `ClimateRuntimeBootstrap`: I2C, storage, BLE, RTC, RF initialization and fail-closed real-output arming;
- `ClimateRuntimeScheduler`: timing/deadlines and loop cadence;
- `ClimateRuntimeCycle`: input collection/merge, schedule, safety evaluation, application tick, output application, fail-safe handling;
- `ClimateRuntimeTelemetry`: periodic runtime/output/status reporting.

Keep existing process-lifetime `RuntimeIoOwner` and `RuntimeControlOwner` semantics unless measurements justify another ownership change.

Priority 2: split `Stage28ServiceConsole`.

Suggested seams:

- UART transport/line framing;
- parser/dispatcher;
- `Stage28StatusReporter`;
- sensor/status commands;
- `Stage28RfConsoleCommands`;
- `Stage28RtcConsoleCommands`;
- `Stage28StorageConsoleCommands`.

Each extraction should be one coherent commit with focused host tests, full software gate at the end of the series, then bounded fake-locked hardware evidence if runtime layout/stack changes materially.

Do not combine modularization with new actuator semantics, AH threshold changes, allocator changes, or additional stack shrinking.

## New-chat bootstrap

Open the new chat on the same Growbox repository. Let Chat Bridge provide the new `LA_CHAT`; never copy/invent the old chat id as the new conversation identity.

Require the bridge envelope to identify:

- repository id `growbox-ml-controller`;
- repository `MichalMatu/growbox-ml-controller`;
- agent binding `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`.

Start the new chat with:

> Continue Stage28E Phase H only. First read `AGENTS.md`, `docs/STAGE28E_PHASE_H_HANDOFF.md`, `docs/CURRENT_STATUS.md`, `docs/CONTINUATION_PLAN.md`, `docs/GUIDANCE.md`, `docs/ESP32_S3_SERIAL_PORT_RESET.md`, and `docs/STAGE28D_AH_ARBITER_HANDOFF.md`. Fresh-check `mvp/environment-controller` HEAD and `agent-control:.agent/status/daemon.json` before changing or queueing anything. A-G are formally complete. Current qualified Phase H runtime/tooling source SHA is `5a4830db9d10e8cb73d4c617b09122f0844ad899`; later docs-only commits must be distinguished from this firmware identity. H v3 fixed the RF stack overflow but did not pass the required AH OFF->ON gate because startup safety forced the fan ON before the natural request. Do not use `>=28 C` thermal safety as H evidence. Prepare a low-request, `<=26 C` startup-recovery state, obtain normal `fan OFF + safety clear`, then use natural temperature/humidity change to cross `requested_fan>=0.10`, observe the 120 s minimum-OFF dwell, normal arbiter OFF->ON, RF TX with zero errors, physical/Shelly evidence, and final fake-locked restoration. Do not add a request injector. Do not start the modularity refactor until H is formally complete.

## Stop conditions

Stop H and preserve evidence on:

- unexplained reset/session/lifecycle change after post-open baseline;
- same-instance cumulative counter regression without legitimate wrap;
- coredump/Guru Meditation;
- heap integrity failure;
- critical stack margin;
- unbounded loop/watchdog behavior;
- safety behavior change;
- RF TX error;
- Shelly master OFF;
- inability to restore safe outputs/final `fake-locked`.
