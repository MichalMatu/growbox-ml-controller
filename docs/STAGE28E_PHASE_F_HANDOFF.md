# Stage28E Phase F Handoff — Arbiter Continuity Regression Proof

Updated: 2026-09-07
Work branch: `mvp/environment-controller`
Phase F implementation SHA: `d88c77d8eab5013a6f94baf60e1404f5b030efdc`
Previous handoff: `docs/STAGE28E_PHASE_E_HANDOFF.md`
Next phase: **Stage28E Phase G — bounded runtime validation and soak**

## Phase F outcome

**The focused V5-inspired single-instance arbiter continuity proof passes.**

Phase F did not change production control code. The only implementation change was an extension of `test/test_stage28d_binary_role_arbiter/test_main.cpp` that exercises the historical symptom family directly against the existing `Stage28dBinaryRoleArbiter` implementation.

The production files `src/climate/Stage28dBinaryRoleArbiter.cpp` and `.h` are byte-for-byte unchanged from the formal Phase E exit SHA `0d4325f08033a38e4fd3769c38b1572e344a27ff`.

## Historical symptom under test

The Stage28D V5 hardware trace contained a cumulative dwell-hold sequence resembling:

`33 -> 43 -> 1 -> 11`

For one continuously living arbiter instance, normal `applyBinary()` execution has no ordinary path that resets `dwell_hold_count_`. Phase F therefore tests the current semantics directly rather than changing the algorithm to fit the historical log.

## Deterministic proof

The new test `testV5SameInstanceDwellContinuityProof()`:

1. constructs one `Stage28dBinaryRoleArbiter` and records its `instanceId()`;
2. synchronizes the arbiter to truthful safe OFF at monotonic time `0`;
3. applies `0.099`, below the ON threshold, and proves no dwell hold or transition is consumed;
4. applies the historical request magnitude `0.111` 43 times while still inside the 120 s minimum-OFF window;
5. proves every call uses the same `instanceId()` and increments the cumulative dwell-hold counter exactly by one, ending at `43`;
6. proves the existing regression helper classifies `43 -> 1` as a regression;
7. applies `0.111` at `119999 ms` and proves the same instance remains OFF while the counter advances `43 -> 44`, never `43 -> 1`;
8. applies `0.111` at exactly `120000 ms` and proves one OFF -> ON transition occurs;
9. proves dwell history remains `44`, transition count becomes `1`, the downstream driver receives exactly one ON command, and continuity fault count remains `0`;
10. makes a subsequent same-state call at `120001 ms` and proves counters remain monotonic and continuity fault count remains `0`.

The existing `binaryArbiterCounterRegressed()` wrap tests remain in place and distinguish a legitimate `uint32_t` wrap from a historical-style regression.

## Local Agent verification

Task:

`20260907-growbox-stage28e-phase-f-arbiter-continuity-gate-v1`

Result: `done / PASS`.

Exact implementation SHA verified:

`d88c77d8eab5013a6f94baf60e1404f5b030efdc`

Verification evidence:

- exact work/origin SHA PASS;
- only `test/test_stage28d_binary_role_arbiter/test_main.cpp` changed relative to Phase E exit;
- production arbiter `.h/.cpp` unchanged;
- focused C++17 compile/run PASS;
- marker `STAGE28E_F_V5_SAME_INSTANCE_CONTINUITY_PROOF_PASS`;
- existing host suite `24/24 PASS`;
- clean worktree and `git diff --check` PASS;
- final marker `STAGE28E_F_ARBITER_CONTINUITY_GATE_PASS`.

## Interpretation

The historical V5 `43 -> 1` dwell-hold drop is **not a normal result of continuous execution of the current arbiter state machine on one instance**.

Under the deterministic request sequence, one living instance can only move the counter forward (subject to legitimate integer wrap). At the exact minimum-OFF dwell boundary, the historical request level `0.111` is eligible and transitions the fan ON normally.

Therefore future reproduction of a same-instance-style cumulative counter decrease must be treated as lifecycle/runtime evidence: reboot/session change, object reconstruction, corruption, or another system-level fault. Phase B diagnostics now make those classes observable.

This conclusion does not claim which historical system-level cause occurred in V5; Phase G runtime evidence is required before that can be narrowed further.

## Safety / behavior statement

Phase F:

- changed no production controller, arbiter, RF, thermal, output, telemetry, storage, or safety behavior;
- used synthetic host inputs only for the new proof;
- did not touch physical outputs or either serial device;
- did not run a hardware actuator transition;
- did not modify `applyBinary()`;
- preserved the Stage28E A-H ordering.

## Phase G entry and scope

After the formal Phase F exact-SHA software exit gate passes, enter Phase G.

Phase G must start with a short bounded hardware runtime using safe fake-locked outputs. Before any longer soak, prove:

- stable boot/session ID and expected reset reason;
- one stable arbiter instance / no unexplained reconstruction;
- no counter regression or continuity fault;
- no coredump, heap-integrity failure, stack warning/critical event, watchdog, or crash;
- internal free/min/largest-block remain within the accepted Phase E margins;
- PSRAM remains healthy;
- main and `stage27_store` stacks retain adequate HWM margin;
- BLE/sensors/telemetry remain active;
- loop timing remains bounded;
- final state remains `fake-locked` with Shelly master ON.

Only after the short bounded run is clean should a representative longer Phase G soak be queued.

Final physical `AH/rule request -> binary arbiter -> RF -> physical fan` remains Phase H only.
