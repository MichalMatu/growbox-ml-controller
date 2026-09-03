# Fresh-context continuation plan

Date: 2026-09-01
Updated: 2026-09-03
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Primary current status: `docs/STAGE27C_FINAL_EVIDENCE.md`
Physical bring-up record: `docs/STAGE27C_CROWPANEL_BRINGUP.md`
Historical handoffs: `docs/STAGE27C_PRE_SOAK_HANDOFF.md`, `docs/STAGE27C_CONTINUATION_HANDOFF.md`

This file is the bootstrap pointer for a fresh ChatGPT conversation.

## Current product state

The architecture through Stage26, Stage27A/Stage27B implementation, and **Stage27C CrowPanel real-input validation are complete** for the requested scope.

Do not restart Stage27A/B/C merely because the Local Agent is idle or because documentation HEAD advances.

Frozen boundaries at Stage27C closure:

- 100% native ESP-IDF v5.5.4;
- no Arduino component and no PlatformIO/Arduino migration;
- e-paper/front-panel UI deferred and not validated by Stage27C;
- physical outputs/relays fake/locked and not validated by Stage27C;
- Rule authoritative;
- ML shadow-only;
- TP357 exact-MAC device provides primary inside T/RH;
- SCD41 provides controller CO2 plus local/window T/RH diagnostics;
- Xiaomi/PVVX/BTHome exact-MAC device provides nearby ambient T/RH through neutral `outside_*` fields;
- no cross-sensor T/RH offsets because the sensors are intentionally in different physical locations.

## Final Stage27C evidence

Exact firmware physically qualified and soaked:

`a5726b89e94b9ac628249b780d6548a692c3fd2c` — `Disable Stage27C CMD0 precondition by default`

Do not confuse later test/documentation commits with the firmware-under-test identity.

Stage27C point 5 completed with seven accepted strict 5400-second SD-primary soak chunks, totaling 37,800 seconds (10.5 hours) of active capture on one preserved MCU uptime sequence. The accepted sequence finished at `last_uptime_ms=59019769` and `last_sd_records_written=6717`. Across accepted chunks there were zero resets, zero serial disconnects, zero parser errors, zero SD mount/write/drop/skip failures, zero SCD41 read/invalid errors, clean BLE scanning/freshness diagnostics, trusted RTC, fake/locked outputs, and the exact firmware SHA throughout.

Stage27C point 6 audited existing host coverage and added only the missing stale-valid-measurement end-to-end assertion. Terminal task `20260903-growbox-stage27c-point6-host-validation-v2` passed the complete portable host suite `17/17` and the targeted Stage27C subset `3/3`.

Full per-chunk task IDs, uptime/SD counters, the rejected chunk-05 capture attempt, memory trend, point-6 evidence and the exact closure boundary are frozen in `docs/STAGE27C_FINAL_EVIDENCE.md`.

## Remaining Stage27C work

None for the requested Stage27C scope.

Do **not**:

- resume or extend the Stage27C soak loop;
- reflash/reset the board merely to collect more Stage27C evidence;
- reopen completed storage fallback/recovery/CMD0 gates without a relevant firmware/storage change;
- add e-paper/front-panel work under the old Stage27C goal;
- enable or validate physical actuators under the old Stage27C goal;
- promote ML from shadow-only under the old Stage27C goal.

A new explicit goal is required for any of those scope expansions. If production firmware/runtime changes invalidate the frozen evidence, open a clearly new validation stage/session rather than silently attaching new results to Stage27C.

## Local Agent and Chat Bridge

Canonical executor repository: `MichalMatu/local-agent`, branch `main`. Read live runtime identity when compatibility matters rather than pinning a remembered release.

Growbox control-plane state lives on this repository's `agent-control` branch:

- `.agent/tasks/<task-id>.json`;
- `.agent/runs/<task-id>.json`;
- `.agent/results/<task-id>.json`;
- `.agent/status/daemon.json`.

For any future Growbox goal:

- use one immutable bounded task at a time for that goal;
- never mutate/replay a terminal task id;
- inspect exact terminal result before claiming completion or queueing the next dependent task;
- classify hardware/USB/serial/flashing work conservatively;
- keep software-only concurrency bounded by an explicit memory/resource contract;
- verify fresh repository HEAD and daemon state instead of relying on historical idle snapshots.

Evidence priority remains:

1. exact terminal result;
2. exact live run/attempt;
3. daemon/supervisor status;
4. exact source/diff/test evidence;
5. planner analysis.

## First actions in a fresh chat

1. Read `AGENTS.md`.
2. Read this file.
3. Read `docs/STAGE27C_FINAL_EVIDENCE.md` and `docs/STAGE27C_CROWPANEL_BRINGUP.md` before discussing Stage27C history.
4. Read `docs/STAGE27_NATIVE_IDF_HANDOFF.md` if Stage27 architecture boundaries matter.
5. Fetch fresh `mvp/environment-controller` HEAD.
6. Fetch fresh Growbox `agent-control:.agent/status/daemon.json` when Local Agent work is requested.
7. Treat `docs/STAGE27C_PRE_SOAK_HANDOFF.md` and `docs/STAGE27C_CONTINUATION_HANDOFF.md` as historical records, not instructions to resume the completed soak.
8. Do not reopen Stage27A/B/C without regression evidence or a new explicit scope.

## Planner behavior expected by the user

- communicate with the user in Polish;
- keep repository documentation, code, commit messages, Local Agent task JSON and commands in English;
- use repository evidence instead of asking the user to repeat frozen information;
- be concise but exact about task ids, terminal results and commit SHAs;
- prefer concrete progress over repeated generic audits;
- never claim physical success without exact execution/hardware evidence;
- preserve native ESP-IDF and hardware-neutral architecture boundaries.
