# Current controller status

Updated: 2026-09-07
Development branch: `mvp/environment-controller`
Latest handoff: `docs/STAGE28E_PHASE_H_HANDOFF.md`
Stage28E execution guide: `docs/GUIDANCE.md`
Prior Stage28D evidence: `docs/STAGE28D_AH_ARBITER_HANDOFF.md`
Primary roadmap: `docs/PROJECT_ROADMAP.md`
Continuation checklist: `docs/CONTINUATION_PLAN.md`

## Current transition

**Stage27C FROZEN -> Stage28E A COMPLETE -> B COMPLETE -> C COMPLETE -> D COMPLETE -> E COMPLETE -> F COMPLETE -> G COMPLETE -> H IN PROGRESS**

A-G are formally complete. Phase H is the only remaining Stage28E phase.

Formal Phase G exit gate:

`7ddb995d1f6cd190fa110f21f0d8dc0eabc61d26`

Qualified Phase H production runtime/tooling source SHA:

`5a4830db9d10e8cb73d4c617b09122f0844ad899`

Do not confuse a later scripts/docs-only repository HEAD with the firmware identity above.

## Phase H current result

Phase H is **not PASS yet**.

The required evidence remains:

`natural AH/rule request -> binary arbiter OFF->ON -> RF TX -> physical fan`

followed by mandatory recovery and final RF-disabled `fake-locked`.

### H v5

Task:

`.agent/tasks/20260907-stage28e-h-v5-fast-close.json`

Result:

`.agent/results/20260907-stage28e-h-v5-fast-close.json`

Primary H v5 failed on the harness precondition:

`clean safety-clear fan-OFF open-tent baseline not observed`

This is no longer a valid physical-test assumption because the operator closed the tent during the run and explicitly requested that it remain closed for all subsequent work.

The persisted close marker is:

- local: `2026-09-07T14:16:42+02:00`;
- UTC: `2026-09-07T12:16:42Z`;
- control-plane asset: `.agent/task-assets/20260907-stage28e-h-manual-close-marker.json`.

Important positive end-of-real-run evidence included:

- `outputs=real-bounded`;
- `rf_ready=1`;
- `fan_known=1`, `fan_on=1`;
- `requested_fan≈0.278`;
- `applied_fan=1.000`;
- `safety_latched=0`, `force_fan=0`, `safety_reason=0`;
- `arbiter_transitions=11`;
- `arbiter_safety_overrides=0`;
- `tx=15`, `tx_errors=0`;
- TP357 about `23.2 C / 65% RH`;
- Xiaomi/intake about `23.22 C / 57.76% RH`;
- SCD41 CO2 about `823 ppm`.

These observations are useful evidence but H remains formally open because the retained harness did not establish the required closed-tent normal OFF baseline and then prove the corresponding natural OFF->ON chain without an invalid interactive/open-tent assumption.

H v5 recovery passed:

- manual RF recovery return code `0`;
- final fake verifier return code `0`;
- final `outputs=fake-locked`;
- final `rf_ready=0`;
- Shelly master ON, about `27.3 W` during the final verifier.

The board was left safe.

## H v6 parser false negative

H v6 completed with primary FAIL but recovery/final PASS. The board returned to RF-disabled `fake-locked`.

A retained-log audit established that the failure was in the observer parser, not in the deterministic controller path:

- `576/576` `stage28d_output` lines were ESP-IDF-prefixed;
- `0` began with the raw marker expected by the observer;
- the production runtime nevertheless produced `24` clean OFF windows lasting up to about `145 s`;
- the run reached `arbiter_transitions=46`, `tx=50`, `tx_errors=0`.

The observer now accepts `stage28d_output ` as an in-line marker so both raw and prefixed ESP-IDF serial forms are parsed. Production C/C++ remains unchanged. Formal H is still open until a corrected observer run proves the complete natural OFF->ON path and mandatory recovery/final.

## Closed-tent H release-candidate harness

The repository now contains:

`scripts/stage28e_phase_h_closed_tent.py`

Purpose:

- tent is already closed;
- no user notification/action dependency;
- no request injection;
- no actuator writes;
- exact firmware SHA and `real-bounded`/RF-ready runtime baseline required;
- stable safety-clear physical fan-OFF baseline required for at least 10 seconds;
- `requested_fan` is intentionally unrestricted during that OFF baseline because the arbiter can legally hold OFF while request is already above the ON threshold;
- then a natural `requested_fan>=0.10` must be observed from fan OFF;
- normal arbiter transition count and RF TX count must both increase;
- `tx_errors` must remain zero;
- fan must become known+ON with `applied_fan>=0.99`;
- lamp and humidifier state must remain unchanged across the fan proof so Shelly total-power evidence is not confounded;
- Shelly master must remain ON and total power must rise by at least 1 W;
- TP357/Xiaomi/SCD41 response is collected before/after the transition;
- TP357 guard defaults to `27.5 C`, below the `28 C` thermal safety trip;
- any post-baseline reset/session/lifecycle restart fails the observation;
- the observer is bounded and recovery/final fake-locked remains the task wrapper's mandatory responsibility.

Do not run the observer by itself as an unattended production controller. The intended use is only inside a bounded qualification task that always restores/proves `fake-locked`.

## RF-enabled main-stack correction

Current policy remains:

- RF disabled/fake build: `CONFIG_ESP_MAIN_TASK_STACK_SIZE=12288`;
- RF enabled build: `CONFIG_ESP_MAIN_TASK_STACK_SIZE=16384`.

Implementation:

- `config/idf/sdkconfig.defaults.stage28rf`;
- conditional selection in `scripts/stage27c_crowpanel.sh`.

Do not shrink the RF-enabled stack without new measured evidence.

## Architecture / modularity audit

Two large orchestration areas remain deliberate post-H debt:

1. `src/climate/ClimateV6RealInputRuntime.cpp` is about 23 KB and `runClimateV6RealInputRuntime()` owns too many responsibilities: hardware/bootstrap, storage/RF/output arming, control-object wiring, safety/test-sequence integration, scheduler/cycle execution and telemetry/service-console coordination.
2. `src/climate/runtime/Stage28ServiceConsole.cpp` is about 32 KB and combines UART transport/line editing, parser/dispatcher, status/stack diagnostics, sensor reporting, RF commands, RTC commands and SD-log commands.

These are genuine god-function/god-object risks, but **do not refactor production C++ before the pending H physical proof**. Preserving the already-qualified production runtime is more valuable than structural cleanup immediately before the overnight qualification.

After formal H close, use behavior-preserving extraction commits:

- runtime -> bootstrap / scheduler-cycle / output-fail-safe / telemetry;
- service console -> UART transport/parser plus status / RF / RTC / sensor / storage modules.

No actuator semantics, AH thresholds, allocator policy or stack shrinking should be mixed into those extraction commits.

## Safety boundary

Correct Growbox serial device:

`/dev/cu.usbserial-1130`

Never open/probe/flash:

`/dev/cu.usbserial-10`

Standing invariants:

- tent remains closed for the next qualification; no operator open/close action is required;
- deterministic rule controller authoritative;
- ML shadow/research-only;
- thermal trip `>=28 C`;
- recovery `<=26 C` continuously for 10 minutes;
- manual RF blocked during `real-bounded`;
- Shelly master stays ON;
- after every bounded real-output diagnostic restore/prove RF-disabled `fake-locked`;
- serial-open reset is tolerated only before the stabilized runtime baseline.

## Local Agent execution identity

- repository: `MichalMatu/growbox-ml-controller`;
- repository id: `growbox-ml-controller`;
- agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`;
- control branch: `agent-control`;
- work branch: `mvp/environment-controller`.

For every task:

- exact `agent_binding` is mandatory;
- use `resources: []` for software/docs/build work;
- use `resources: ["board:growbox-s3"]` for serial/flash/hardware;
- verify exact SHA in-task;
- read terminal `.agent/results/<task-id>.json` before reporting PASS.

## Immediate next work

1. Complete the software-only RC preflight for the closed-tent observer and current docs/scripts HEAD.
2. Require clean tree, Python compile/help, focused host tests and an ESP-IDF build without flashing.
3. Prove the delta from the previously qualified baseline contains only `scripts/`/`docs/` preparation files and no production C/C++ runtime change.
4. Only after the preflight is green, prepare one immutable bounded overnight H task.
5. The overnight task starts with the tent already closed, never waits for operator action, uses only the normal controller path, and always runs recovery/final fake-locked even if primary observation fails.
6. Only after formal H PASS should the production modularity backlog begin.
