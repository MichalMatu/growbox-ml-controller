# Fresh-context continuation plan

Updated: 2026-09-08
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Latest handoff: `docs/STAGE28E_PHASE_H_HANDOFF.md`
Current status: `docs/CURRENT_STATUS.md`
Execution guide: `docs/GUIDANCE.md`

## Read first in a new chat

1. `AGENTS.md`
2. `docs/STAGE28E_PHASE_H_HANDOFF.md`
3. `docs/CURRENT_STATUS.md`
4. this file
5. `docs/GUIDANCE.md`
6. `docs/ESP32_S3_SERIAL_PORT_RESET.md`
7. `docs/STAGE28D_AH_ARBITER_HANDOFF.md`
8. `docs/PROJECT_ROADMAP.md`

Then fetch fresh `mvp/environment-controller` HEAD and fresh `agent-control:.agent/status/daemon.json`. Read the newest relevant `.agent/results/...` before deciding what has passed. Never continue from remembered chat state alone.

## Current transition

**Stage28E A-G COMPLETE -> H IN PROGRESS**

Formal Phase G exit gate:

`7ddb995d1f6cd190fa110f21f0d8dc0eabc61d26`

Qualified Phase H production runtime/tooling source SHA:

`5a4830db9d10e8cb73d4c617b09122f0844ad899`

The branch may contain later scripts/docs-only qualification preparation. Do not label that later HEAD as newly qualified firmware unless production sources were rebuilt and requalified explicitly.

## Latest H evidence

Latest physical attempt: **H v7**.

- task: `.agent/tasks/20260907-stage28e-h-v7-corrected-parser-v1.json`;
- result: `.agent/results/20260907-stage28e-h-v7-corrected-parser-v1.json`;
- primary was intentionally interrupted with RC `130` after the qualification harness defect was identified;
- mandatory recovery and final RF-disabled `fake-locked` both passed (`recovery=0`, `final=0`);
- retained v7 telemetry showed normal fan cycling with `safety_latched=0`, `force_fan=0`, and `safety_reason=1` (`TimerOff`), so the old `reason == 0` observer gate was a false-negative condition rather than production safety activation.

The observer fix is commit `45065a34ce276ac5cdb7ef8cf0a1ad8a4bae1b0d`. It accepts only `Safe (0)` and `TimerOff (1)` as H safety-clear reasons, and only while both `safety_latched=0` and `force_fan=0`; reasons `2..5` remain rejected. Replay of the retained v7 log accepted `596` TimerOff samples and no unsafe reason.

H v8 software preflight `20260908-stage28e-h-v8-preflight-v1` is **PASS** on executable/preflight HEAD `231eed28f64bdbdc4238fd8bce128264027702f2`. It proved no production C/C++ delta relative to `5a4830db9d10e8cb73d4c617b09122f0844ad899`, passed the focused observer tests and v7 replay, passed all `24/24` host tests, built fake `12288 B` main-stack firmware, built real/recovery `16384 B` main-stack firmware, and ended clean with `hardware_started=0`. H v8 itself has **not** been started.

## Repository-tracked closed-tent observer

Use:

`scripts/stage28e_phase_h_closed_tent.py`

It replaces the interactive/open-tent assumption for the next qualification.

Properties:

- starts with tent already closed;
- no operator notification/action;
- no controller-request injection;
- no actuator command writes;
- requires exact expected firmware SHA;
- requires `outputs=real-bounded` and `rf_ready=1`;
- tolerates only the documented serial-open reset before the stabilized runtime baseline;
- requires a stable safety-clear `fan_known=1 fan_on=0 applied_fan<0.01` baseline for at least 10 seconds;
- does not require `requested_fan<0.10` during that baseline;
- then requires natural `requested_fan>=0.10` from the OFF state;
- requires increased arbiter transition count and RF TX count, `tx_errors=0`, and known physical fan ON with `applied_fan>=0.99`;
- requires lamp/humidifier state unchanged across the fan proof so Shelly power evidence is not confounded;
- requires Shelly master ON and at least 1 W total-power increase;
- records TP357/Xiaomi/SCD41 environmental response;
- defaults to TP357 guard `27.5 C`, safely below thermal trip `28 C`;
- defaults to a bounded 2-hour observation and 10-minute post-transition response window.

The observer does **not** perform recovery. The Local Agent hardware wrapper must always perform recovery RF and final RF-disabled `fake-locked`, regardless of the primary observer return code.

## What H still has to prove

One bounded normal control path:

`natural AH/rule request -> binary arbiter OFF->ON -> RF TX -> physical fan`

Required evidence:

- exact firmware/source identity;
- post-serial-open stable boot/session baseline;
- safety clear;
- physical fan known+OFF prestate;
- natural request `>=0.10` while fan is still OFF;
- normal dwell/counter behavior;
- one normal OFF->ON arbiter transition;
- RF TX increment and `tx_errors=0`;
- independent physical/Shelly support without lamp/humidifier power confounding;
- environmental response snapshot;
- acceptable memory/stack/timing;
- mandatory safe recovery and final RF-disabled `fake-locked`.

Do not add a request injector to force PASS.

## Software-only gate before H v8

H v8 preflight `20260908-stage28e-h-v8-preflight-v1` is **PASS** on `231eed28f64bdbdc4238fd8bce128264027702f2`. It verified the TimerOff-aware observer, v7 replay (`596` accepted TimerOff samples), all `24/24` host tests, fake `12288 B` build, real/recovery `16384 B` builds, no production C/C++ delta from `5a4830db9d10e8cb73d4c617b09122f0844ad899`, and a clean worktree.

Committed documentation-only readiness changes after that preflight are allowed without rebuilding. Before H v8 starts, verify the current worktree is clean and prove any delta after `231eed28f64bdbdc4238fd8bce128264027702f2` is documentation-only; any executable/configuration change requires a new software preflight.

## Overnight bounded-H wrapper

Only after software preflight PASS, prepare a separate immutable hardware task with:

- exact `agent_binding`: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`;
- `resources: []`;
- exact port `/dev/cu.usbserial-1130` and explicit refusal of any other port;
- exact expected qualified firmware/source identity;
- RF-enabled main stack `16384 B`;
- real-bounded flash;
- closed-tent observer with no human action, e.g. `--timeout 7200 --post-seconds 600 --closure-utc 2026-09-07T12:16:42Z`;
- primary return code captured but not allowed to skip recovery;
- recovery RF image + `scripts/stage28e_phase_h_e2e.py recovery`;
- final RF-disabled fake image + `scripts/stage28e_phase_h_e2e.py final`;
- fail the task if recovery/final fails, even if primary proof passed;
- only report formal H PASS after reading terminal result evidence.

This authorizes only one bounded qualification. It is not authorization for continuous unattended real-output production operation.

## Architecture debt — deliberately deferred until H closes

The audit confirms two broad-responsibility areas:

- `src/climate/ClimateV6RealInputRuntime.cpp` (~23 KB) — runtime bootstrap, storage/RF/output arming, object wiring, safety, cycle/scheduler and telemetry/service coordination are too concentrated around `runClimateV6RealInputRuntime()`;
- `src/climate/runtime/Stage28ServiceConsole.cpp` (~32 KB) — UART transport, line editor, dispatch, runtime/stack status, sensors, RF, RTC and SD-log commands are combined in one service-console implementation.

Do not refactor either before H. The correct sequence after H is behavior-preserving extraction:

1. runtime: bootstrap -> scheduler/cycle -> output/fail-safe -> telemetry;
2. console: UART transport/parser -> status -> sensors -> RF -> RTC -> storage.

Keep each extraction narrow, add focused host tests, then run a full software gate and bounded fake-locked hardware evidence if stack/runtime layout changes materially.

## Safety boundaries

- correct serial: `/dev/cu.usbserial-1130`;
- never touch `/dev/cu.usbserial-10`;
- tent remains closed;
- do not intentionally cross `28 C`;
- observer guard defaults to `27.5 C`;
- deterministic rule controller remains authoritative;
- ML remains shadow/research-only;
- manual RF remains blocked during `real-bounded`;
- Shelly master remains ON;
- every bounded real-output attempt must end with verified `fake-locked`.

## Recommended fresh-chat instruction

`Continue Growbox Stage28E Phase H only in MichalMatu/growbox-ml-controller. Read AGENTS.md, docs/STAGE28E_PHASE_H_HANDOFF.md, docs/CURRENT_STATUS.md, docs/CONTINUATION_PLAN.md, docs/GUIDANCE.md and docs/ESP32_S3_SERIAL_PORT_RESET.md, then fresh-check mvp/environment-controller HEAD and agent-control:.agent/status/daemon.json. A-G are complete; H is open. Qualified production firmware identity remains 5a4830db9d10e8cb73d4c617b09122f0844ad899. TimerOff-aware observer commit is 45065a34ce276ac5cdb7ef8cf0a1ad8a4bae1b0d. H v8 software preflight 20260908-stage28e-h-v8-preflight-v1 passed on 231eed28f64bdbdc4238fd8bce128264027702f2 with 24/24 host tests, v7 replay accepted 596 TimerOff samples, fake 12 KiB and real/recovery 16 KiB images built, no production C/C++ delta, and hardware_started=0. H v8 is prepared but not started. All repository tasks use resources: []; verify /dev/cu.usbserial-1130 inside any hardware task and never touch /dev/cu.usbserial-10. When explicitly authorized to start H v8, use only the normal controller path, no request injection or actuator forcing, and always perform recovery plus final RF-disabled fake-locked. Do not begin the production runtime/service-console refactor before formal H PASS.`
