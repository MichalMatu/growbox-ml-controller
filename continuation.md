# Growbox project continuation handoff

Date: 2026-09-04
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`

This file is the primary handoff for a fresh ChatGPT conversation after the long Stage28C / pre-Stage28D session. Read it before planning new work. Then verify the fresh work-branch HEAD and `agent-control:.agent/status/daemon.json`; never continue from remembered chat state alone.

## Exact state at handoff

Current transition:

**Stage27C FROZEN -> Stage28A DONE -> Stage28B DONE -> Stage28C DONE -> pre-Stage28D golden gate COMPLETE -> Stage28D IN PROGRESS**

Important SHA distinction:

- exact firmware/source SHA that passed the complete golden software gate and the 5400-second real-hardware soak: `316b58e76de609069ddbf2667fe86f6218fb2143`;
- repository HEAD immediately before this fresh-chat handoff commit: `edd4a2328a7d0d43bccd3becab67500b9948a2e6`, commit `Record pre-Stage28D golden checkpoint`, parent `316b58e76de609069ddbf2667fe86f6218fb2143`;
- this handoff update is documentation-only and therefore advances repository HEAD without creating a new hardware-soaked firmware SHA.

Do not call a later docs-only HEAD "hardware tested". The hardware-qualified golden firmware remains `316b58e76de609069ddbf2667fe86f6218fb2143` until executable firmware changes are separately qualified.

At handoff preparation, Local Agent reported daemon `4.15.0`, self revision `c8251967dcd0b90fe26f14392eb56a67e39d542a`, state `idle`, and no active task. This is only a snapshot; verify fresh daemon state in the new conversation.

## Frozen safety state

These constraints remain active unless the operator explicitly starts and qualifies a later gate:

- Rule policy remains authoritative.
- ML remains shadow/research-only.
- Physical outputs remain `fake-locked`.
- No unattended mains-load actuation is authorized.
- Local RF self-reception is not physical socket/load state acknowledgement.
- Do not reopen frozen Stage27A/B/C or Stage28A/B/C without new evidence that later executable code invalidated them.

## Stage27C frozen real-input baseline

Stage27C native ESP-IDF real-input qualification is complete.

- validated tag: `stage27c-validated-2026-09-03`;
- Stage27C closure commit: `b418520090d0feadc005701092c1b7ed3384afbf`;
- physically soaked Stage27C firmware: `a5726b89e94b9ac628249b780d6548a692c3fd2c`;
- platform direction remains 100% native ESP-IDF;
- first real-input bundle remains SCD41 + DS3231 + BLE climate inputs;
- outputs remained fake/locked throughout Stage27 qualification.

Historical Stage27 soak evidence is useful as calibration/reference only. The later Golden checkpoint has its own hardware soak and is the current pre-Stage28D evidence.

## Stage28A and Stage28B

Stage28A native RF433 codec and temporal classification are complete.

- milestone: `ac29122cbcf9d155fd08baa0df1014d71f04c135`.

Stage28B native ESP-IDF RMT TX/RX loopback is complete.

- historical Stage28B qualified milestone: `a87169748ee2bd42bc4d35cfe3b2964b90f40eb8`.

Do not reconstruct the current receiver configuration from Stage28B values. The old `1 MHz / 1.25 us / 12 ms` RX settings are historical and superseded.

## Stage28C frozen RF433 identity

Stage28C physically validated and froze exactly one neutral remote/socket pair under hardware label `remote_socket_1`.

Frozen identity:

- ON decimal: `906118656`;
- ON hex: `0x36024600`;
- OFF decimal: `1040336384`;
- OFF hex: `0x3E024600`;
- bits: `32`;
- protocol: `2`;
- pulse: `575 us`;
- physically reliable ESP transmit repeat: `10`.

`repeat=10` is a proven reliable transmit setting. It is not a claim that the original handheld remote was measured to transmit exactly ten repeats.

Identity/config freeze commit:

`b3e90c92dd39c50c23ed618aba47e9fe8ddf26ec`

Final known-pair hardware recheck source:

`2cb4b8dffb0835460a9e9ba920d9bd888c99d992`

That hardware recheck required exact ON/OFF decode, TX queued/start/completed, RX capture, decode status 0, `SelfTx` classification, no RX arm error/timeout, and restoration to passive RX-only mode. `SelfTx` proves the local receive/classification path, not the physical state of the mains socket.

Detailed evidence: `docs/STAGE28C_FINAL_EVIDENCE.md`.

## Current RF433 receive contract

The post-Stage28C hardened receive contract is:

- TX/codec resolution: `100 kHz`;
- RX resolution: `100 kHz`;
- RX minimum signal / glitch threshold: `10 us` (`10,000 ns`);
- RX maximum signal / idle threshold: `20 ms` (`20,000,000 ns`);
- TX GPIO: `8`;
- RX GPIO: `14`;
- raw RX capacity: `256` symbols;
- self-TX guard: `50 ms`.

A 32-bit protocol-2 frame occupies 33 symbols. Seven complete repeats fit in one 256-symbol raw capture buffer; ten complete repeats do not.

The 20 ms idle threshold is hardware-qualified. A 300 ms receiver diagnostic did not terminate one-shot capture reliably in the same ambient receiver environment because continuing RF activity prevented the receiver from reaching idle. The successful follow-up used 20 ms. Do not revert this to the old Stage28B threshold without new physical evidence.

## Overnight hardening work completed

The long overnight goal was completed before this handoff. The sequence and evidence are intentionally preserved here so a fresh chat does not redo it.

### 1. Golden baseline audit

Task: `20260904-growbox-prestage-golden-audit-v1`

Starting source: `b3e90c92dd39c50c23ed618aba47e9fe8ddf26ec`

Result: PASS.

Verified host CMake/CTest, panel layout tests and ESP-IDF CrowPanel build. No product defect was found.

Terminal marker:

`PRESTAGE_GOLDEN_AUDIT_PASS sha=b3e90c92dd39c50c23ed618aba47e9fe8ddf26ec`

### 2. Real-input runtime responsibility refactor

Task: `20260904-growbox-prestage-runtime-refactor-v1`

Commit:

`a215cae35bbdee155a40fce0c7481a87191a3716` — `Refactor real-input runtime responsibilities`

Created/refined `src/climate/runtime/` responsibilities:

- `Stage27RuntimeAdapters.h/.cpp`;
- `Stage27TelemetryReporter.h/.cpp`;
- `Stage28RfDiagnostics.h/.cpp`;
- `ClimateV6RealInputRuntime.cpp` reduced to orchestration, approximately 202 lines at that checkpoint.

The refactor preserved fake-lock behavior and did not change the frozen RF socket identity.

### 3. RF receive-contract hardening

Final passing task: `20260904-growbox-prestage-rf-contract-hardening-v2`

Commit:

`60da0a4d2a99f3045596b6a8a8bf362a0c6e1aca` — `Harden RF433 receive contract and reuse capture path`

Key changes:

- introduced `src/climate/rf433/Rf433RmtTuning.h`;
- centralized the hardware-qualified RMT RX parameters;
- reused receive arm/collect paths instead of duplicating them;
- preserved overflow semantics;
- added host-test coverage for the RX contract/capacity and frozen pair.

Result: 18/18 host CTest passed and the ESP-IDF CrowPanel build passed.

The earlier v1 compile-only attempt was superseded by v2; it did not establish an unresolved product defect.

### 4. Stage28C / golden documentation synchronization

Final passing task: `20260904-growbox-prestage-docs-sync-v2`

Commit:

`82d92fa0e4c9423a4dd0b3b00ea924d168401f41` — `Synchronize Stage28C golden handoff documentation`

This synchronized the active Stage28C documentation to the frozen RF pair, current RX settings, fake-lock boundary and pre-Stage28D golden gate.

### 5. ESP-IDF Kconfig cleanup

Task: `20260904-growbox-prestage-kconfig-cleanup-v1`

Commit:

`484a7dfa262165fc3e61716cc162a49d61a2ee8a` — `Remove obsolete ESP-IDF Bluetooth Kconfig choices`

Removed obsolete Bluetooth Kconfig choices and reduced unknown Kconfig-symbol warnings to zero on the current ESP-IDF 5.5.4 CrowPanel build. Remaining build warnings were toolchain/ESP-IDF pedantic warnings, not unknown project Kconfig symbols.

### 6. Golden software gate

The first formatting/gate attempt exposed formatting changes and then a Local Agent process-group memory limit during the broad gate. That was an execution-environment resource limit, not a product failure. The bounded v2 gate superseded it.

Passing task:

`20260904-growbox-prestage-format-gate-v2`

Golden firmware/source commit:

`316b58e76de609069ddbf2667fe86f6218fb2143` — `Normalize formatting after Stage28C hardening`

Terminal marker:

`PRESTAGE_FORMAT_GATE_READY commit=316b58e76de609069ddbf2667fe86f6218fb2143 parent=484a7dfa262165fc3e61716cc162a49d61a2ee8a precommit=pass quality_gate=pass crowpanel_build=pass unknown_kconfig_warnings=0 cmake_parallel=2`

The full gate included:

- repository pre-commit/formatting;
- Python regressions;
- host C++ build and CTest;
- clang-tidy;
- ESP-IDF gate;
- exact CrowPanel build;
- zero unknown Kconfig-symbol warnings;
- clean worktree and push.

Recorded Python result in the final checkpoint flow: `479 passed, 3 skipped, 9 deselected`. The three skips were panel visual tests because the Playwright Chromium executable was unavailable on the executor; this was not a firmware/product failure.

Recorded host CTest result: 18/18 passed.

### 7. Golden 90-minute hardware soak

Task:

`20260904-growbox-prestage-golden-hardware-soak-v1`

Exact flashed/tested source:

`316b58e76de609069ddbf2667fe86f6218fb2143`

Duration: `5400 s`.

Result: PASS with `violations: []`.

Important evidence:

- records: `526`;
- resets: `0`;
- serial disconnects: `0`;
- parse errors: `0`;
- unexpected firmware SHA records: `0`;
- max SCD41 age: `4050 ms`;
- max TP357 age: `3052 ms`;
- max Xiaomi age: `11962 ms`;
- BLE advertisement lock drops: `0`;
- BLE scan errors: `0`;
- RTC read errors: `0`;
- RTC untrusted records: `0`;
- SCD41 invalid/read errors: `0`;
- SD mount/write/queue/skip errors: `0`;
- SD telemetry delta: `612` records;
- minimum internal heap: `226200 B`;
- minimum largest internal block: `184320 B`;
- internal heap change across soak: `226328 -> 226200 B`;
- minimum PSRAM free: `8368044 B`;
- minimum largest PSRAM block: `8257536 B`;
- PSRAM change across soak: `8368044 -> 8368044 B`;
- minimum free stack: `9292 B`;
- non-zero IO status records: `0`;
- bad output records: `0`;
- outputs remained `fake-locked`;
- RF automatic transmit disabled;
- no RF433 TX lifecycle observed in the soak logs.

Terminal markers:

`PRESTAGE_GOLDEN_SOAK_SUMMARY records=526 uptime_first=10939 uptime_last=5393079 heap_internal_first=226328 heap_internal_last=226200 heap_psram_first=8368044 heap_psram_last=8368044 min_stack_free=9292 sd_delta=612`

`PRESTAGE_GOLDEN_HARDWARE_SOAK_PASS sha=316b58e76de609069ddbf2667fe86f6218fb2143 duration_s=5400 outputs=fake-locked rf_auto_tx=0`

### 8. Final golden checkpoint documentation

Task:

`20260904-growbox-prestage-golden-checkpoint-docs-v1`

Docs-only commit:

`edd4a2328a7d0d43bccd3becab67500b9948a2e6` — `Record pre-Stage28D golden checkpoint`

Parent:

`316b58e76de609069ddbf2667fe86f6218fb2143`

It created `docs/PRESTAGE28D_GOLDEN_CHECKPOINT.md` and synchronized `continuation.md` / `docs/CURRENT_STATUS.md` without starting Stage28D.

The task also re-ran the broad software quality gate successfully: Python `479 passed, 3 skipped, 9 deselected`, host CTest 18/18, clang-tidy and IDF gate all passed.

Terminal marker:

`PRESTAGE_GOLDEN_CHECKPOINT_READY commit=edd4a2328a7d0d43bccd3becab67500b9948a2e6 hardware_tested=316b58e76de609069ddbf2667fe86f6218fb2143 docs_only=1 precommit=pass quality_gate=pass stage28d_started=0`

## Evidence boundaries that must not be collapsed

Keep these as separate claims:

1. A TX request was accepted / started / completed locally.
2. The local RF receiver captured and decoded the expected RF frame and classified it as `SelfTx`.
3. A real remote socket or connected mains load physically changed state.

Stage28C proves the qualified local RF path and a reliable transmit setting. It does not turn local self-RX into physical load-state acknowledgement. The Golden soak did not transmit RF at all; it proves stability of the post-hardening firmware under real sensor/RTC/BLE/SD operation with outputs fake-locked.

## Local Agent workflow for the next conversation

Repository binding is immutable for this project unless the operator explicitly rebinds Chat Bridge:

`"agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5"`

Rules:

- work only on `MichalMatu/growbox-ml-controller`;
- work branch: `mvp/environment-controller`;
- control branch: `agent-control`;
- every Local Agent task JSON must contain the exact binding above;
- use `resources: []` for repository-local software/docs/build work;
- use `resources: ["board:growbox-s3"]` for USB, serial, flashing or hardware work;
- one task per repository at a time;
- task IDs and payloads are immutable; fixes/retries require a new task ID;
- `expected_head` is not implemented, so exact source identity must be guarded in the task/payload itself;
- machine-generated Local Agent task content, commands, code comments, documentation edits and commit messages must be English-only;
- before a new task, fetch fresh source HEAD, fresh daemon state and the previous terminal result;
- inspect terminal result evidence before claiming completion;
- physical/unattended output work remains fake-locked unless a later explicit hardware gate changes that rule.

For builds/refactors, use bounded verification and avoid repeatedly running the full gate after every small change. For hardware work, serialize on `board:growbox-s3`.

## Fresh-chat bootstrap sequence

A new conversation should do the following before changing anything:

1. Read `AGENTS.md`.
2. Read this `continuation.md` completely.
3. Read `docs/CURRENT_STATUS.md`.
4. Read `docs/PRESTAGE28D_GOLDEN_CHECKPOINT.md`.
5. Read `docs/CONTINUATION_PLAN.md`.
6. Read `docs/STAGE27_NATIVE_IDF_HANDOFF.md` when Stage27/native hardware assumptions matter.
7. Fetch the fresh `mvp/environment-controller` HEAD.
8. Fetch `agent-control:.agent/status/daemon.json` and verify repository/binding/current task.
9. Keep the hardware-qualified firmware SHA `316b58e76de609069ddbf2667fe86f6218fb2143` distinct from any later docs-only HEAD.
10. Do not restart Stage27 or Stage28C debugging without new evidence of regression.
11. Stage28D is already explicitly in progress. Continue only from the bounded scope recorded below and do not infer a semantic role for `remote_socket_1`.

## Stage28D progress

The operator explicitly started Stage28D on 2026-09-04. The first bounded slice is software-only semantic binding hardening:

- validate enabled role mappings before any endpoint write;
- reject enabled mappings without a concrete endpoint;
- reject one physical endpoint being assigned to multiple active semantic roles;
- provide explicit bind/unbind helpers so mapping changes are transactional and reviewable;
- fail closed before endpoint writes when the semantic mapping is invalid.

This slice does not assign `remote_socket_1` to heater, fan, humidifier or any other semantic role. The real-input runtime still uses `LockedFakeRoleDriver`; physical outputs remain `fake-locked`, and this task performs no RF transmit, flashing or mains-load actuation.

The second bounded software-only slice adds a neutral RF433 endpoint registry: stable climate endpoint ID `1` resolves to the frozen `remote_socket_1` hardware configuration, while the registry itself contains no `ClimateActuatorRole` assignment. The registry is compiled by the firmware and covered by host tests; runtime output composition is still unchanged and fake-locked.

## Stage28D manual service console slice

A bounded USB service console is now integrated into the real-input runtime. It is intentionally separate from semantic actuator binding and does not replace `LockedFakeRoleDriver`. The console provides read-only `help`, `status`, `sensors`, and `rf list` commands plus explicit named manual RF transmit commands for lamp, fan and humidifier and a bounded one-shot RF receive command. Safe numeric aliases `0..3` exist only for read-only menu actions.

The neutral RF hardware config now also contains `remote_socket_2` (lamp captured profile, 560 us / repeat 10) and `remote_socket_3` (humidifier captured profile, 560 us / repeat 10). These are capture-derived service profiles pending physical validation. `remote_socket_1` remains the fan and keeps its separately qualified 575 us / repeat 10 transmit evidence. No new climate endpoint IDs or semantic roles are assigned by this slice.

Manual RF service commands use the existing Stage28 RF diagnostics transport and therefore require that transport to be enabled in the hardware build. Console TX evidence must continue to be separated from physical socket/load observation.

## What comes next

There is no unfinished overnight Local Agent task. The overnight hardening goal is complete.

Stage28D is now **IN PROGRESS**.

The neutral endpoint registry and manual service console are now ready. Before further semantic output work, hardware-smoke the console and manually validate the captured lamp/fan/humidifier ON/OFF commands with physical load observation. A later semantic step must still not guess actuator-role binding from hardware identity. Preserve `LockedFakeRoleDriver`, fake-lock/no-unattended-mains safety and the frozen hardware identities below the semantic layer.

Do not silently bake a semantic role such as `exhaust_fan` into the frozen Stage28C hardware identity. Hardware identity and semantic role are separate layers.

## Key files for continuation

- `AGENTS.md` — repository/Local Agent rules and new-chat bootstrap.
- `continuation.md` — this primary handoff.
- `docs/CURRENT_STATUS.md` — concise current status.
- `docs/PRESTAGE28D_GOLDEN_CHECKPOINT.md` — exact Golden software/hardware evidence.
- `docs/STAGE28C_FINAL_EVIDENCE.md` — frozen RF433 pair and physical Stage28C evidence.
- `docs/CONTINUATION_PLAN.md` — short current transition/next-step summary.
- `docs/STAGE27_NATIVE_IDF_HANDOFF.md` — frozen native ESP-IDF/platform/input decisions.
- `src/climate/runtime/` — refactored real-input runtime responsibilities.
- `src/climate/rf433/Rf433HardwareConfig.h` — frozen Stage28C hardware config.
- `src/climate/rf433/Rf433RmtTuning.h` — hardened RMT tuning contract.
- `src/climate/rf433/Rf433RmtLoopback.cpp` — native RMT implementation.
- `test/test_rf433_protocol/test_main.cpp` — RF contract/frozen-pair host tests.
- `scripts/quality_gate_push.sh` — broad software verification gate.
- `scripts/stage27c_crowpanel.sh` — CrowPanel build/flash helper.
- `tools/stage27c_soak.py` — bounded real-hardware soak/evidence collector.

## Short copyable new-chat instruction

Use this if a fresh conversation needs a compact starting instruction:

> Continue `MichalMatu/growbox-ml-controller` on branch `mvp/environment-controller`. First read `AGENTS.md`, `continuation.md`, `docs/CURRENT_STATUS.md`, `docs/PRESTAGE28D_GOLDEN_CHECKPOINT.md`, `docs/CONTINUATION_PLAN.md`, then fetch fresh HEAD and `agent-control:.agent/status/daemon.json`. Treat `316b58e76de609069ddbf2667fe86f6218fb2143` as the exact hardware-soaked Golden firmware SHA. Stage27C and Stage28C are frozen. Stage28D is IN PROGRESS: semantic mapping validation and the neutral `remote_socket_1` endpoint registry are implemented, but no semantic actuator role is assigned, runtime outputs remain fake-locked, and no physical RF output gate is open.
