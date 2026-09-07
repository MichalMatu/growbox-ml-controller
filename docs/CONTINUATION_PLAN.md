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

Latest attempt: H v6

- task: `.agent/tasks/20260907-stage28e-h-v6-closed-autonomous.json`;
- result: `.agent/results/20260907-stage28e-h-v6-closed-autonomous.json`;
- formal primary outcome: FAIL;
- recovery/final: PASS, final RF-disabled `fake-locked`;
- production runtime remained healthy and reached `arbiter_transitions=46`, `tx=50`, `tx_errors=0`;
- retained log contained `24` clean safety-clear OFF windows up to about `145 s`.

Root cause of the formal FAIL was qualification tooling: all `576/576` production `stage28d_output` lines were ESP-IDF-prefixed and the v6 observer incorrectly required a raw-line `startswith` match. Corrected observer RC4 commit: `d91fe21d319d4f85832d9fc95d5912bbae23cf0e`. Parser regression replay accepts all `576/576` retained lines. Full software-only preflight `20260907-stage28e-h-prefix-fix-preflight-rc4` is PASS. Production C/C++ is unchanged relative to qualified firmware identity `5a4830db9d10e8cb73d4c617b09122f0844ad899`.

H remains formally open only because the corrected observer has not yet been used for a successful physical H proof.

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

## Software-only gate before corrected H v7

RC4 preflight `20260907-stage28e-h-prefix-fix-preflight-rc4` is **PASS** on `d91fe21d319d4f85832d9fc95d5912bbae23cf0e`. It proved clean scope/no production C++ delta, parser replay regression, full host suite, fake 12 KiB firmware build, RF/real 16 KiB firmware build and clean tree.

Before H v7, fresh-check branch HEAD and prove that any delta after `d91fe21d319d4f85832d9fc95d5912bbae23cf0e` is docs-only. If executable code/tooling changed, rerun the software gate with a new immutable task id.

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

`Continue Growbox Stage28E Phase H only in MichalMatu/growbox-ml-controller. First read AGENTS.md, docs/STAGE28E_PHASE_H_HANDOFF.md, docs/CURRENT_STATUS.md, docs/CONTINUATION_PLAN.md, docs/GUIDANCE.md and docs/ESP32_S3_SERIAL_PORT_RESET.md, then fresh-check mvp/environment-controller HEAD and agent-control:.agent/status/daemon.json. A-G are formally complete; H is not. Qualified production firmware/source identity remains 5a4830db9d10e8cb73d4c617b09122f0844ad899. H v6 primary was a tooling false negative: all 576 stage28d_output lines were ESP-IDF-prefixed while the observer required startswith; the real run nevertheless had 24 clean OFF windows, 46 arbiter transitions, 50 RF TX and zero TX errors, and recovery/final fake-locked passed. Corrected observer RC4 is d91fe21d319d4f85832d9fc95d5912bbae23cf0e; software-only preflight 20260907-stage28e-h-prefix-fix-preflight-rc4 is PASS, including 576/576 replay parser acceptance, host suite, fake 12 KiB build and RF/real 16 KiB build. The tent remains closed and no user action is needed. Next run one new immutable H v7 bounded hardware task on board:growbox-s3 and /dev/cu.usbserial-1130 using scripts/stage28e_phase_h_closed_tent.py, normal controller path only, no request injection/actuator forcing, and unconditional recovery plus final RF-disabled fake-locked. Never touch /dev/cu.usbserial-10. Do not start the production runtime/service-console modularity refactor until H formally passes.`
