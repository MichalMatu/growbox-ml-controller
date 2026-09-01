# Fresh-context continuation plan

Date: 2026-09-01
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Primary current handoff: `docs/STAGE27C_CONTINUATION_HANDOFF.md`
Historical Stage27 architecture handoff: `docs/STAGE27_NATIVE_IDF_HANDOFF.md`

This file is the bootstrap pointer for a new ChatGPT conversation. The detailed current Stage27C state is frozen in `docs/STAGE27C_CONTINUATION_HANDOFF.md`; read that file completely before planning or executing new work.

## Current product state

The architecture through Stage26 and the native Stage27A/Stage27B implementation are complete. Do not restart those stages unless fresh evidence demonstrates a regression.

Current physical validation stage: **Stage27C CrowPanel real-input bring-up**.

Frozen rules remain:

- 100% native ESP-IDF v5.5.4;
- no Arduino component and no PlatformIO/Arduino migration;
- e-paper/front-panel UI deferred;
- physical outputs/relays fake/locked;
- Rule remains authoritative;
- ML remains shadow-only;
- no cross-sensor temperature/RH offsets because the real sensors are in different physical locations.

## Current Stage27C status

Stage27C points 1-4 are complete on real hardware:

- CrowPanel N8R8 profile and GPIO21/GPIO38 shared I2C are proven;
- SCD41 and DS3231 are physically detected and operational;
- SCD41 MCU-only reset recovery is implemented;
- TP357 native BLE decoding is proven from the real exact-MAC device;
- Xiaomi/PVVX/BTHome and TP357 are scanned concurrently by one native NimBLE scanner using exact MAC identities;
- TP357 provides primary inside T/RH;
- SCD41 provides controller CO2 plus local/window T/RH diagnostics;
- Xiaomi provides nearby ambient T/RH through the neutral `outside_*` channel;
- RTC trusted validity is separate from availability;
- outputs remain fake/locked;
- physical input gate passed with no panic/watchdog evidence.

The firmware revision that generated the current soak evidence is:

`cf957a7649ec02835f724951d34f0b408f5f6de2` — `Add Stage27C soak diagnostics`

Later documentation-only commits may advance repository HEAD. Do not confuse docs HEAD with the firmware-under-test SHA.

## Stage27C point 5 status

Long-soak diagnostics are implemented.

Two bounded ~90-minute chunks completed with terminal PASS on firmware `cf957a7649ec02835f724951d34f0b408f5f6de2`, preserving MCU uptime continuity and showing stable heap/PSRAM, zero SCD41 read/invalid errors, continuing TP357/Xiaomi traffic and fake/locked outputs.

The third chunk task, `20260831-growbox-stage27c-long-soak-chunk03-v1`, was **intentionally interrupted by the user**. Its terminal failure is `interrupted_previous_attempt`; this is operator interruption, not firmware failure. Never replay or mutate that task id.

The autonomous Stage27C loop is intentionally paused. Do not resume it merely because the executor is idle.

Exact chunk task ids, attempt ids, digests, counters, uptime values, continuation rules and interruption semantics are in `docs/STAGE27C_CONTINUATION_HANDOFF.md`.

## Remaining Stage27C work

1. Resume/complete point 5 only when the user explicitly asks to continue.
2. Before continuing the soak, determine whether the same firmware and uptime continuity survived the pause. If not, start a clearly new soak session rather than silently combining incompatible uptime sequences.
3. After soak closure, perform only safe software-observable point-6 fault/freshness tests unless physical manipulation is explicitly authorized.
4. Freeze final point-7 evidence/status, distinguishing documentation HEAD from the exact flashed/tested firmware SHA.
5. Keep physical outputs and e-paper outside this scope unless a new explicit goal opens them.

## Local Agent and Chat Bridge

Canonical executor repository: `MichalMatu/local-agent`, branch `main`. Do not pin a remembered release line here. Read live runtime identity and compare it with canonical `MichalMatu/local-agent/main` when compatibility matters.

Read before autonomous execution:

- `MichalMatu/local-agent/AGENTS.md`;
- `docs/OPERATIONS.md`;
- `docs/AUTONOMOUS_CHAT_LOOP.md`;
- `docs/MULTI_REPOSITORY.md` when scheduler/resource behavior matters;
- `chat_bridge/README.md` when Chat Bridge operation matters.

Local Agent is a deterministic executor. ChatGPT is the planner. The Chrome Chat Bridge only wakes one selected ChatGPT conversation and transports assistant control markers; it does not understand the project or choose work.

Growbox control-plane state lives on this repository's `agent-control` branch:

- `.agent/tasks/<task-id>.json`;
- `.agent/runs/<task-id>.json`;
- `.agent/results/<task-id>.json`;
- `.agent/status/daemon.json`.

### Parallel execution model

The autonomous planner loop remains sequential for the active Growbox goal, and Growbox executes at most one claimed task at a time. This is **not global serialization**: the production `agent_parallel.py` supervisor may execute unrelated repository tasks concurrently when resource admission permits it. The recommended production width is two workers; verify the actual live supervisor fields rather than assuming a remembered value.

Repository-worker `.agent/status/daemon.json` may be an older idle snapshot and may not contain supervisor-wide fields such as `max_parallel_workers`. When scheduler identity or global concurrency matters, inspect the shared supervisor status as well as the Growbox worker status. Compare `daemon_version` / `self_revision` with canonical `MichalMatu/local-agent/main` instead of treating a stale worker heartbeat as the installed runtime version.

Resource classification is conservative:

- omitted, malformed or unsafe `resources` means full `machine` exclusivity;
- `resources: []` is only for clearly software-only work and requires enabled `memory_limit_mb <= 1024`;
- named resources serialize tasks sharing the same named resource;
- hardware, USB, serial, flashing, PlatformIO-heavy or otherwise uncertain work remains `machine`-exclusive unless a narrower contract has been explicitly proven safe.

For Stage27C, physical serial/soak work should therefore remain machine-exclusive by default. A software-only host-test task may opt into safe overlap when its resource and memory contract is explicit.

Never queue a second Growbox task for the same active goal while its exact task is active. Task ids/payloads are immutable. Interrupted tasks are never automatically replayed.

### Chat Bridge pacing

After queueing a new autonomous task, prefer one early liveness re-check after about 30 seconds. Inspect terminal result first; otherwise inspect the exact run/attempt and daemon status. If execution is healthy, return to a longer interval appropriate to the expected duration. Do not leave a 30-second Bridge interval enabled across a healthy multi-minute or multi-hour task.

This is planner pacing only. It must not alter Local Agent polling, duplicate execution or weaken one-active-task sequencing for the current Growbox goal.

Evidence priority:

1. exact terminal result;
2. exact live run/attempt;
3. daemon/supervisor status;
4. exact source/diff/test evidence;
5. planner analysis.

The full project-specific Local Agent + Chat Bridge handoff, including bridge markers and the SIGTERM interruption behavior observed on chunk 03, is in `docs/STAGE27C_CONTINUATION_HANDOFF.md`.

## First actions in a fresh chat

1. Read `AGENTS.md`.
2. Read this file.
3. Read `docs/STAGE27C_CONTINUATION_HANDOFF.md` completely.
4. Read `docs/STAGE27_NATIVE_IDF_HANDOFF.md` and `docs/STAGE27C_CROWPANEL_BRINGUP.md` for frozen architecture/physical details.
5. Read canonical `MichalMatu/local-agent/docs/OPERATIONS.md`, `docs/AUTONOMOUS_CHAT_LOOP.md` and `docs/MULTI_REPOSITORY.md`; read `chat_bridge/README.md` if automatic wake-ups are to be used.
6. Fetch fresh `mvp/environment-controller` HEAD.
7. Fetch fresh Growbox `agent-control:.agent/status/daemon.json` and any newer exact run/result evidence.
8. When runtime/scheduler identity matters, also inspect the shared supervisor status and compare its `daemon_version` / `self_revision` with canonical `MichalMatu/local-agent/main`.
9. Treat any previously recorded idle/stopped/clean-queue state as historical context only; verify it again before writes/tasks.
10. Do not replay `20260831-growbox-stage27c-long-soak-chunk03-v1`.
11. Do not reopen Stage27A/B or Stage27C points 1-4 without regression evidence.
12. Do not resume the soak/autonomous loop until the user explicitly asks to continue.
13. When resuming, use one new immutable bounded task at a time for the Stage27C goal and keep outputs fake/locked.
14. Classify task resources conservatively so unrelated repositories overlap only when it is genuinely safe.

## Planner behavior expected by the user

- communicate with the user in Polish;
- keep repository documentation, code, commit messages, Local Agent task JSON and commands in English;
- use repository evidence instead of asking the user to repeat information already frozen here;
- be concise but exact about task id, attempt/result and commit SHA;
- prefer concrete progress over repeated generic audits;
- never claim physical success without exact execution/hardware evidence;
- preserve the native ESP-IDF and hardware-neutral architecture boundaries.
