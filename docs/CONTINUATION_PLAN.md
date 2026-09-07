# Fresh-context continuation plan

Updated: 2026-09-07
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

H v5 task:

`.agent/tasks/20260907-stage28e-h-v5-fast-close.json`

H v5 result:

`.agent/results/20260907-stage28e-h-v5-fast-close.json`

Formal outcome: **FAIL, safe recovery PASS**.

Failure reason:

`clean safety-clear fan-OFF open-tent baseline not observed`

The failure is a harness-assumption problem for the current experiment state. The tent was manually closed at:

- `2026-09-07T14:16:42+02:00`;
- `2026-09-07T12:16:42Z`.

The user explicitly requested that the tent remain closed and that all remaining tests be autonomous.

End-of-real-run evidence remained healthy: normal controller request, physical fan ON, safety clear, `arbiter_transitions=11`, RF `tx=15`, `tx_errors=0`. Recovery then completed with `manual=0 final=0`, and final RF-disabled `fake-locked` with Shelly master ON.

This evidence does not by itself close H because the retained observer did not prove the required normal closed-tent fan OFF -> natural request -> arbiter/RF -> fan ON chain under a valid baseline.

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

## Before the overnight H run

Do **not** start hardware qualification until the software-only release-candidate preflight is green.

Preflight must verify the exact current branch HEAD and:

1. clean working tree;
2. changed-file set relative to the pre-preparation HEAD `9042559b2d052b2e1942c0a61220bd9b7e74c97f` is restricted to intended `scripts/`/`docs/` files;
3. no production `.c/.cc/.cpp/.h/.hpp` source changed;
4. `python3 -m py_compile scripts/stage28e_phase_h_closed_tent.py`;
5. `python3 scripts/stage28e_phase_h_closed_tent.py --help`;
6. focused/native host tests appropriate to the current controller/arbiter/safety/runtime code;
7. ESP-IDF software build without flash using the repository's established build procedure;
8. final clean working tree.

If the preflight fails, fix the RC first and use a new immutable Local Agent task id for the retry.

## Overnight bounded-H wrapper

Only after software preflight PASS, prepare a separate immutable hardware task with:

- exact `agent_binding`: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`;
- `resources: ["board:growbox-s3"]`;
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

`Continue Growbox Stage28E Phase H only in MichalMatu/growbox-ml-controller. First read AGENTS.md, docs/STAGE28E_PHASE_H_HANDOFF.md, docs/CURRENT_STATUS.md, docs/CONTINUATION_PLAN.md and docs/GUIDANCE.md, then fresh-check mvp/environment-controller HEAD and agent-control:.agent/status/daemon.json. A-G are formally complete; H is not. Qualified production runtime/tooling source identity is 5a4830db9d10e8cb73d4c617b09122f0844ad899. H v5 failed only its obsolete open-tent baseline criterion; recovery/final fake-locked passed. The tent was closed at 2026-09-07T12:16:42Z and must remain closed. Use scripts/stage28e_phase_h_closed_tent.py for the next bounded qualification; no user open/close action, no request injection, no actuator forcing. First require the software-only RC preflight to be green. Then one bounded hardware task must observe stable safety-clear physical fan OFF, natural requested_fan>=0.10, normal arbiter OFF->ON, RF TX increment with zero errors, unconfounded Shelly support and environmental response, followed unconditionally by recovery and final RF-disabled fake-locked. Do not start the runtime/service-console modularity refactor until H formally passes.`


## H v6 qualification-tooling finding

H v6 was a false negative caused by the observer using a raw-line `startswith` check for `stage28d_output` while ESP-IDF prefixes all production output-state lines. Correct the observer only, regression-test raw and prefixed forms, and leave production C/C++ unchanged before rerunning formal H.
