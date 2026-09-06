# Fresh-context continuation plan

Updated: 2026-09-06
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Latest handoff: `docs/STAGE28E_PHASE_A_HANDOFF.md`
Stage28E execution guide: `docs/GUIDANCE.md`
Prior Stage28D evidence: `docs/STAGE28D_AH_ARBITER_HANDOFF.md`
Current status: `docs/CURRENT_STATUS.md`
Primary roadmap: `docs/PROJECT_ROADMAP.md`

## Read first in a new chat

1. `AGENTS.md`
2. `docs/GUIDANCE.md`
3. `docs/STAGE28E_PHASE_A_HANDOFF.md`
4. `docs/PROJECT_ROADMAP.md`
5. `docs/CURRENT_STATUS.md`
6. this file
7. `docs/STAGE28D_AH_ARBITER_HANDOFF.md` when historical V5 details are needed
8. `docs/OBSERVABILITY_AND_INFERENCE_PLAN.md` when changing ventilation, inference, telemetry or ML behavior
9. `docs/SHELLY_POWER_FEEDBACK.md` when changing physical-state supervision

Then fetch fresh `mvp/environment-controller` HEAD, fresh `agent-control:.agent/status/daemon.json`, and the newest Local Agent result. Never continue from remembered chat state alone.

## Current transition

**Stage27C FROZEN -> Stage28A/B/C DONE -> Gates 1-6 COMPLETE -> Gate 7 previously qualified -> AH policy software COMPLETE -> Gate 7 runtime path REOPENED by V5 -> Stage28E Phase A observability COMPLETE pending exact-SHA docs-only exit gate -> Phase B next**

The immediate development program is Stage28E A -> H. Stage28D AH functional work stays paused until A-G pass; the final physical `AH/rule request -> binary arbiter -> RF -> physical fan` path belongs to Stage28E Phase H.

## Phase A identity and evidence

Phase A started from:

`2218ad30401222537cb568541d80bc07adc2c0eb`

Phase A implementation and bounded hardware diagnostic firmware:

`3058625be2f35c121afcf82549d5c73068839ecd`

The complete Phase A evidence is in:

`docs/STAGE28E_PHASE_A_HANDOFF.md`

Key bounded hardware findings:

- boot/session identity works;
- reset reason was expected power-on reset;
- internal RAM free/min/largest: `221648 / 221028 / 180224 B`;
- PSRAM free/min/largest: `8363512 / 8363108 / 8257536 B`;
- lowest known percentage stack margin was `stage27_store` at about 40.6%;
- no known task was below the 25% warning threshold;
- worst active loop was `194320 us` with a `1000000 us` budget;
- loop overruns were `0`;
- firmware size changed from `726061 B` baseline to `730821 B`, net `+4760 B`.

The previously suspected approximately 1 KiB internal-memory crisis was not reproduced by the bounded representative run.

Two extra read-only confirmation tasks failed only because their UART parser did not capture a complete `status` line in the selected window. `hardware-confirm-v2` command 1 still proved exact work SHA `3058625...`, clean tree and correct `/dev/cu.usbserial-1130`. Do not queue a third identical confirmation unless new evidence requires it.

## V5 issue remains the functional problem to explain

The decisive prior Stage28D task remains:

`20260906-growbox-ah-arbiter-clean-v5`

V5 showed a non-safety fan request above the ON threshold with the fan remaining OFF after the expected dwell window. The strongest clue is cumulative `arbiter_dwell_holds` decreasing:

`33 -> 43 -> 1 -> 11`

This must not be treated as an ordinary expected arbiter path. Stage28E must determine whether it came from board reset, runtime/object reconstruction, state corruption, timing discontinuity, reconciliation/safe-off logic or another lifecycle/system fault.

Do not jump directly to changing `applyBinary()`.

## Serial and hardware invariants

Growbox/CrowPanel serial:

`/dev/cu.usbserial-1130`

Never touch:

`/dev/cu.usbserial-10`

That port belongs to another project.

For Local Agent tasks:

- every task must contain exactly `"agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5"`;
- use `resources: []` for software/docs/build work;
- use `resources: ["board:growbox-s3"]` for serial/flashing/device work;
- check fresh daemon state before editing the same branch or queueing hardware access.

Safety boundary remains:

- rule controller authoritative;
- ML shadow/research-only;
- thermal trip `>=28 C`;
- recovery `<=26 C` continuously for 10 minutes;
- manual RF blocked during `real-bounded`;
- Shelly master ON;
- no unattended real-output operation;
- restore/prove fake-locked after bounded diagnostics.

## Immediate next work

### 1. Finish Phase A exit

Run one docs-only Local Agent gate on the exact current Phase A closing SHA. It should verify:

- exact local and remote branch SHA;
- clean work tree;
- `git diff --check`;
- presence of `docs/STAGE28E_PHASE_A_HANDOFF.md`;
- Phase A handoff contains the implementation SHA `3058625be2f35c121afcf82549d5c73068839ecd`;
- Phase A handoff contains the bounded hardware memory/timing evidence;
- `docs/CURRENT_STATUS.md` points to Stage28E Phase B as next;
- this continuation plan points to `docs/STAGE28E_PHASE_A_HANDOFF.md`;
- no firmware/device action is performed.

If that gate passes, record that exact SHA as the Phase A exit SHA.

### 2. Start Phase B

Phase B starts from the Phase A exit SHA.

First action is read-only Local Agent inspection of:

- installed ESP-IDF coredump configuration symbols and supported format/checksum options;
- exact 8 MiB flash size;
- exact current partition-table offsets/sizes;
- available safe space for a coredump partition;
- current build configuration relevant to reset/coredump reporting.

Known partition layout to verify before editing:

```csv
nvs,       data, nvs,     0x9000,  0x6000
phy_init,  data, phy,     0xf000,  0x1000
factory,   app, factory,  0x10000, 0x400000
telemetry, data, fat,     0x410000,0x200000
```

After the read-only contract is proven, implement Phase B in small slices:

1. flash coredump support;
2. low-wear crash/reset breadcrumbs;
3. arbiter/runtime owner lifecycle and instance IDs;
4. selected state-integrity sentinels;
5. targeted heavy-diagnostic heap-integrity checks;
6. subsystem heartbeat/age diagnostics.

Do not run a long soak in Phase B. Do not run the final real AH actuator transition before Phase H.

## Recommended fresh-chat instruction

`Read AGENTS.md, docs/GUIDANCE.md, docs/STAGE28E_PHASE_A_HANDOFF.md, docs/CURRENT_STATUS.md and docs/CONTINUATION_PLAN.md. Fetch fresh mvp/environment-controller HEAD and Local Agent daemon/result evidence first. Treat Stage28E Phase A as complete only if its docs-only exact-SHA gate passed. Then continue sequentially with Phase B crash/reset/corruption/lifecycle diagnostics; do not return to Stage28D functional AH testing until A-G pass.`
