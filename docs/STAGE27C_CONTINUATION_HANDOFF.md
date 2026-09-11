# Stage27C continuation handoff

Date: 2026-08-31
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Local Agent repository id: `growbox-ml-controller`

This file is the primary continuation document for moving Stage27C work to a fresh ChatGPT conversation. Read it together with `AGENTS.md`, `docs/STAGE27_NATIVE_IDF_HANDOFF.md`, and `docs/STAGE27C_CROWPANEL_BRINGUP.md` before resuming work.

The user intentionally stopped the active long-soak task and paused autonomous execution so the shared Local Agent can be used for other work. Do not automatically resume Stage27C merely because the executor is idle. Resume only when the user asks to continue this goal.

## Source identity at handoff

The firmware source that produced the current Stage27C hardware/soak evidence is:

`cf957a7649ec02835f724951d34f0b408f5f6de2` — `Add Stage27C soak diagnostics`

This SHA is the **firmware-under-test identity**. Documentation-only commits created for this handoff may advance `mvp/environment-controller` after this SHA. Do not confuse a later docs HEAD with the firmware revision that generated the physical evidence.

Before any future executable/config change, fetch the current remote branch HEAD again. Before claiming hardware behavior, identify the exact firmware SHA actually built/flashed on the board.

## Frozen Stage27 architecture

Stage27 remains native ESP-IDF only.

- ESP-IDF v5.5.4 baseline.
- No Arduino-ESP32 component.
- No PlatformIO/Arduino migration.
- E-paper/front-panel UI is deferred and must not become a prerequisite for climate input validation.
- Physical relays/actuators remain fake/locked throughout Stage27C.
- The Rule controller remains authoritative; ML remains shadow-only until separately qualified.

The native feasibility decision and earlier Stage27 architecture are frozen in `docs/STAGE27_NATIVE_IDF_HANDOFF.md` and the Stage27A feasibility freeze.

## Physical hardware and semantic mapping

Board:

- Elecrow CrowPanel ESP32-S3 2.9-inch e-paper HMI;
- N8R8: 8 MB flash + 8 MB octal PSRAM;
- shared primary I2C: SDA GPIO21, SCL GPIO38;
- serial adapter previously observed as CH340 VID:PID `1A86:7523`, path `/dev/cu.usbserial-110`; rediscover before future use because the path is not guaranteed stable.

Sensors:

- TP357 BLE MAC `F7:5F:8D:0F:76:20`: physically inside the growbox; **primary inside temperature/RH**.
- Xiaomi LYWSD03MMC/PVVX/BTHome MAC `A4:C1:38:4F:24:CD`: physically on/near the growbox; **nearby ambient temperature/RH**. It is carried through the neutral core's existing `outside_*` channel, but project documentation must not call it physically outdoors.
- SCD41 I2C address `0x62`: physically near the window; **CO2 source for the controller**, with SCD41 temperature/RH retained only as local/window diagnostics.
- DS3231 I2C address `0x68`: backed-up RTC; availability and trusted validity are separate, and OSF/lost-power must make time untrusted.

Do not calculate or apply temperature/RH offsets between TP357, Xiaomi and SCD41. They are intentionally in different physical locations.

The runtime mapping is therefore:

- main inside T/RH = TP357;
- main CO2 = SCD41;
- nearby/ambient T/RH = Xiaomi via neutral `outside_*` fields;
- SCD41 T/RH = diagnostics only;
- outputs = fake/locked.

## Completed Stage27 work

### Stage27A

Native feasibility was frozen: native ESP-IDF, native NimBLE, native I2C, native DS3231 register handling, Sensirion SCD4x driver integration, e-paper deferred, Arduino runtime dropped.

### Stage27B

The native real-input bundle was implemented behind hardware-neutral interfaces:

- native BTHome decoder;
- native DS3231 codec/source;
- shared ESP-IDF I2C owner;
- SCD41 source;
- native BLE source;
- real-input runtime composition;
- fake/locked outputs;
- host tests and ESP-IDF build gates.

### Stage27C points 1-4

Points 1-4 are closed.

1. CrowPanel N8R8 build uses GPIO21/GPIO38 and the correct flash/PSRAM profile with e-paper ignored and outputs fake/locked.
2. SCD41 and DS3231 were physically discovered. SCD41 MCU-only reset recovery was fixed so an inherited periodic session is stopped before a fresh session starts. Physical runtime then showed SCD41 samples and trusted RTC.
3. TP357 manufacturer advertisements were decoded from the real exact-MAC device. A shared native NimBLE scanner now routes TP357 and Xiaomi concurrently by exact MAC.
4. The physical dual-BLE gate passed with simultaneous SCD41, RTC, BLE scanning, TP357 and Xiaomi evidence and no panic/watchdog evidence. Example final readings were TP357 `23.90 C / 74.00 %RH` and Xiaomi `25.06 C / 55.07 %RH`, with `outputs=fake-locked`.

Important commits in the Stage27C path include:

- `063ff4d004dce20c61307fe24114611ff5ae43f6` — CrowPanel Stage27C bring-up preparation;
- `d0b52a352d2488dba4d1f5e64af579ec8fa1545f` — SCD41 restart recovery;
- `5aa478f0dbda59fbc5fd13e555874811d399e8f7` — native TP357 decoder;
- `c3f60834e592ded5b84072e9355dfa7daad95c5a` — dual BLE climate state router;
- `cd4abeb7cd23c23f9e78eb0fcef9f27801e994dc` — shared Stage27C dual BLE scanner;
- `a1a05a91a6928f672a8f4f43963f979fefa7d79d` — Stage27C dual BLE runtime wiring;
- `cd630d079a97571384ff595a63d1685c9e6a53c7` — physical input gate evidence;
- `cf957a7649ec02835f724951d34f0b408f5f6de2` — Stage27C soak diagnostics.

## Stage27C point 5: current soak status

The firmware at `cf957a7649ec02835f724951d34f0b408f5f6de2` adds recurring soak diagnostics for:

- uptime and reset reason;
- internal heap current/minimum;
- PSRAM current/minimum;
- SCD41 sample age, successful samples, read errors and invalid samples;
- TP357 packet/accepted/rejected counters and valid-measurement freshness;
- Xiaomi packet/accepted/rejected counters and valid-measurement freshness;
- fake/locked output state.

A short physical diagnostics gate passed before the long soak.

### Valid long-soak chunk 01

Task: `20260831-growbox-stage27c-long-soak-chunk01-v1`
Attempt: `0d13c274b3c01a4c88dfce43`
Digest: `37004402594f195c103043e29ebcc8efa266f661b3d2f4649d5b986e37e7c957`

Terminal PASS summary:

- rows: 531;
- span: 5,390,920 ms (~89.85 min);
- uptime: `1,902,719 -> 7,293,639 ms`;
- reset reason remained 1;
- internal heap: `260672 -> 260608 B`, minimum `260608 B`;
- PSRAM: `8384992 -> 8384992 B`;
- SCD41 samples `402 -> 1544`, read errors `0 -> 0`, invalid `0 -> 0`;
- TP357 packets/accepted `434 -> 1579`, rejected `0 -> 0`;
- Xiaomi packets `1626 -> 6323`, accepted `807 -> 3140`, rejected `819 -> 3183`;
- outputs remained fake/locked;
- no reboot, panic or watchdog evidence.

Xiaomi rejected advertisements are expected because the exact-MAC device emits advertisements that are not valid climate measurement frames. Rejected frames must not refresh valid-measurement freshness.

### Valid long-soak chunk 02

Task: `20260831-growbox-stage27c-long-soak-chunk02-v1`
Attempt: `05f59d01e19dded69080b275`
Digest: `753d6640253de4a06ef6eac4f859b7eebbc84139b9217ae598ba1c90b7ef19f1`

Terminal PASS summary:

- rows/input rows: 531/531;
- span: 5,390,920 ms (~89.85 min);
- uptime: `8,432,849 -> 13,823,769 ms`;
- previous valid chunk ended at `7,293,639 ms`, so MCU uptime continuity was preserved across the task boundary;
- reset reason remained 1;
- internal heap: `260608 -> 260608 B`, low `260608 B`;
- PSRAM: `8384992 -> 8384992 B`, low `8384992 B`;
- SCD41 max age 4050 ms, samples `1785 -> 2927`, read errors `0 -> 0`, invalid `0 -> 0`;
- TP357 max age 31041 ms, packets/accepted `1825 -> 3276`, rejected `0 -> 0`;
- Xiaomi max age 7398 ms, packets `7330 -> 11955`, accepted `3639 -> 5931`, rejected `3691 -> 6024`;
- outputs remained fake/locked;
- no reboot, panic or watchdog evidence.

Together, chunk 01 + chunk 02 provide about 179.7 minutes of valid long-soak evidence on the same firmware revision.

### Chunk 03 was intentionally interrupted

Task: `20260831-growbox-stage27c-long-soak-chunk03-v1`
Attempt: `91bdc23f1212b121a384cda7`
Digest: `75d87ad64dd044394ab9004552c0a813eb77c012769cfaef526c39f159ad5ef4`

The user intentionally stopped this soak to free the shared Local Agent for other work. The worker received SIGTERM, terminated the active process group, and the recovered terminal result is:

- status: `failed`;
- failure reason: `interrupted_previous_attempt`;
- error: `Previous daemon instance ended while this task was claimed. Automatic replay was blocked.`

This is **not firmware-failure evidence**. It is an intentional operator interruption. Never replay or mutate this task id. A future continuation must use a new unique task id.

## How to resume point 5 safely

First determine whether the CrowPanel firmware/uptime continuity survived the pause.

### Case A: same firmware is still running and uptime continuity survives

If the board is still running firmware `cf957a7649ec02835f724951d34f0b408f5f6de2` and its first observed uptime is greater than the chunk-02 end `13,823,769 ms`, continue the original soak session with a **new unique replacement task** for chunk 03. Do not reuse `...chunk03-v1`.

The replacement must:

- not reflash;
- verify the expected source SHA explicitly because `expected_head` is not implemented;
- rediscover/verify the serial device;
- require first observed uptime > `13,823,769`;
- capture another bounded 5400-second window;
- enforce the same runtime/input/freshness/heap/counter/fake-locked checks;
- publish a terminal result before any following soak task is queued.

Then continue sequentially with new unique chunk 04-07 tasks, one at a time, with no reflash between chunks.

### Case B: the board was reset, reflashed or firmware changed

Do not pretend continuity with chunk 02. Start a new soak session with a fresh baseline and explicitly document the intentional session break.

The two completed chunks remain useful historical evidence, but if final Stage27C acceptance requires a strict continuous ~10.5-hour soak, run a fresh seven-chunk continuous sequence on the final firmware revision. If the acceptance criterion is allowed to aggregate bounded sessions, make that decision explicit in the final evidence document rather than silently combining incompatible uptime sessions.

## Point 6 after soak

Perform only safe software-observable fault tests unless the user explicitly authorizes physical manipulation.

Inspect existing host tests first; do not add duplicate tests unnecessarily. Coverage should include, where not already proven:

- unknown/wrong BLE MAC cannot alter target counters or climate freshness;
- malformed exact TP357 advertisement increments packet/rejected diagnostics but cannot refresh last valid measurement;
- encrypted/unsupported exact Xiaomi frame increments packet/rejected diagnostics but cannot refresh last valid measurement;
- stale valid climate samples become unavailable after the configured freshness timeout even if malformed packets continue to arrive;
- SCD41 cached valid measurement freshness is not incorrectly refreshed by data-ready/read failures;
- SCD41 read-error/invalid counters behave correctly where a host seam/mock can prove it;
- RTC availability and trusted validity remain separate, including OSF/lost-power semantics.

Keep physical outputs fake/locked.

## Point 7 final Stage27C closure

After point 5 and point 6 are complete:

1. analyze all terminal evidence for resets, watchdogs, crashes, BLE freshness, parser rejection, I2C/SCD recovery, RTC trust and heap trend;
2. update `docs/STAGE27C_CROWPANEL_BRINGUP.md` with the final evidence;
3. distinguish final documentation HEAD from the exact firmware SHA that was flashed/tested;
4. record the final Stage27C status in the appropriate current-status/continuation documentation;
5. keep e-paper and physical outputs out of scope unless a new explicit goal opens them.

Only after the whole requested Stage27C goal is proven should an autonomous Chat Bridge loop end with `[LOCAL_AGENT_BRIDGE:STOP]`.

## Local Agent model for the next chat

Canonical implementation: `MichalMatu/local-agent`, branch `main`. Do not pin a remembered release line here; read live `daemon_version` / `self_revision` and canonical `agent_version.py` when compatibility matters.

Read:

- `MichalMatu/local-agent/AGENTS.md`;
- `docs/OPERATIONS.md`;
- `docs/AUTONOMOUS_CHAT_LOOP.md`;
- `chat_bridge/README.md` when bridge operation matters.

### Roles

`ChatGPT planner -> Git-backed control branch -> Local Agent executor -> Git-backed evidence -> ChatGPT planner`

The Chrome Chat Bridge only wakes the selected ChatGPT conversation periodically. It does not inspect code, understand the goal, choose tasks, or execute commands.

ChatGPT is the planner:

- understands the user's active goal;
- reads repository/source/control evidence;
- chooses the smallest next bounded action;
- may make approved bounded direct GitHub edits when safe;
- creates immutable Local Agent task JSON when real local execution is needed;
- inspects exact terminal evidence before claiming success or continuing.

Local Agent is the deterministic executor:

- validates an immutable task payload;
- operates in the registered repository workspace/branch;
- runs exactly the declared commands/edits;
- enforces time, no-output, RSS and descendant-process limits;
- publishes live progress and terminal evidence;
- does not invent fixes or make planning decisions.

### Shared multi-repository execution

The deployment uses one long-lived bounded-parallel supervisor and short-lived repository workers. Growbox still executes at most one claimed task at a time. Unrelated repositories may run concurrently when resource admission permits it. Long hardware/serial/soak tasks normally remain `machine`-exclusive, so they can still block other machine-exclusive work even though the executor is not globally serial.

Never queue a second task while an exact task is active. Never use another repository's `agent-control` branch for Growbox work.

### Control-plane paths

On `agent-control`:

- `.agent/tasks/<task-id>.json` — immutable planner request;
- `.agent/runs/<task-id>.json` — live execution evidence;
- `.agent/results/<task-id>.json` — terminal result;
- `.agent/status/daemon.json` — repository worker/status snapshot;
- `.agent/daemon/control.json` and `.agent/daemon/acks/` — maintenance/status controls where applicable.

Product code and documentation belong on `mvp/environment-controller`, not on `agent-control`.

### Evidence priority

Always use this order:

1. terminal result for the exact task id/digest;
2. newer live run for the exact attempt while active;
3. daemon status;
4. exact source/diff/test evidence referenced by execution;
5. planner analysis.

A stale daemon snapshot can be superseded by a newer exact live run. Do not infer success merely from `idle` when a terminal result should exist.

### Task immutability and interrupted tasks

Task ids and payloads are immutable. Use a new unique id for every continuation or retry.

Interrupted work is never automatically replayed. The chunk-03 interruption demonstrated the intended behavior: SIGTERM terminated the worker/process group, the next worker recovered the task as `interrupted_previous_attempt`, published a terminal failed result and released the claim without replaying the command.

### Direct GitHub + Local Agent hybrid workflow

Docs-only changes may be committed directly through GitHub when the daemon is idle. They do not automatically require a firmware build.

Small clear code/config changes may also be made directly, but publication is not correctness. After executable/config changes, queue a new immutable Local Agent verification task that explicitly synchronizes/verifies the expected source SHA and runs impact-appropriate focused tests/builds plus one final broad gate when warranted.

For larger/refactoring/local-tool-driven changes, let Local Agent perform the edit and verification.

Never allow direct GitHub writes to race an active Local Agent task publishing to the same work branch.

## Chrome Chat Bridge model for the next chat

The bridge is a Chrome Manifest V3 extension in `MichalMatu/local-agent/chat_bridge/`.

Important behavior:

- disabled by default;
- binds to one exact ChatGPT conversation URL;
- periodically sends one configured feedback/wake prompt to that conversation;
- will not send while ChatGPT is already generating;
- will not overwrite non-empty composer text;
- Chrome must remain running and the selected conversation tab must remain open, although it does not need to be foregrounded;
- runtime configuration is fetched from the dedicated `chat-bridge-state` branch with a local fallback;
- the local master enable/disable switch remains authoritative.

The bridge runtime prompt is only a wake-up policy. It does not contain enough project context to replace this handoff. The new conversation must first establish the active goal and read this repository documentation.

### Bridge control markers

A marker is acted on only when it is the final non-empty line of the latest assistant message in the selected conversation:

- `[LOCAL_AGENT_BRIDGE:STOP]` — goal complete; disable automatic wake-ups and clear interval override;
- `[LOCAL_AGENT_BRIDGE:PAUSE]` — user/manual/external action required; disable wake-ups while preserving runtime settings;
- `[LOCAL_AGENT_BRIDGE:RESUME]` — re-enable automatic wake-ups;
- `[LOCAL_AGENT_BRIDGE:INTERVAL=N]` — persistent assistant interval override;
- `[LOCAL_AGENT_BRIDGE:INTERVAL=AUTO]` — clear the override and return to runtime/fallback timing.

Do not emit `STOP` merely because Local Agent is idle. Idle means capacity is available, not that the goal is complete.

## Canonical autonomous wake algorithm

When the bridge is enabled for this goal, every wake must:

1. identify the exact active Stage27C goal from the conversation;
2. fetch fresh `.agent/status/daemon.json`;
3. inspect the exact active/latest run and terminal result;
4. if an exact task is still active, do not queue another task;
5. if a terminal result exists, analyze that exact result first;
6. on success, compare remaining scope and queue only the next necessary bounded task;
7. on failure, diagnose exact evidence and use a new unique task id only when a concrete safe next action exists;
8. pause when genuine manual/user action is required;
9. stop only when the complete requested goal is supported by evidence.

## Fresh-chat bootstrap procedure

A new ChatGPT conversation continuing this work should do the following before changing anything:

1. Read `MichalMatu/growbox-ml-controller:AGENTS.md` on `mvp/environment-controller`.
2. Read this file completely.
3. Read `docs/STAGE27_NATIVE_IDF_HANDOFF.md` and `docs/STAGE27C_CROWPANEL_BRINGUP.md`.
4. Read canonical `MichalMatu/local-agent/docs/OPERATIONS.md` and `docs/AUTONOMOUS_CHAT_LOOP.md`; read `chat_bridge/README.md` if automatic wake-ups are going to be used.
5. Fetch the **fresh** current `mvp/environment-controller` HEAD. Do not rely on the SHA captured in this handoff for repository HEAD after docs commits.
6. Fetch the **fresh** `.agent/status/daemon.json` on `agent-control`.
7. Inspect any newer task/run/result evidence before creating work. The user stated the agent and queues were stopped/cleaned at this handoff, but that is historical state, not a substitute for a fresh read.
8. Do not replay `20260831-growbox-stage27c-long-soak-chunk03-v1`.
9. Do not reopen Stage27A/B or Stage27C points 1-4 unless new evidence demonstrates a regression.
10. Ask/confirm whether the user wants to resume Stage27C before starting a new long soak, because this handoff was created during an intentional pause.
11. If resuming point 5, first establish whether the board/firmware uptime can legitimately continue the old soak session or whether a new soak session is required.
12. Continue one bounded task at a time and preserve fake/locked outputs.

## Suggested first message for a new chat

The user can start a new conversation with a prompt equivalent to:

> Continue the Growbox Stage27C CrowPanel work from the repository handoff. Read `AGENTS.md`, `docs/STAGE27C_CONTINUATION_HANDOFF.md`, `docs/STAGE27_NATIVE_IDF_HANDOFF.md`, and `docs/STAGE27C_CROWPANEL_BRINGUP.md` on `mvp/environment-controller`, plus the canonical `MichalMatu/local-agent` operations/autonomous-loop docs. Inspect fresh source HEAD and fresh agent-control daemon/run/result evidence before doing anything. Stage27C points 1-4 are closed. Point 5 has two valid ~90-minute soak chunks on firmware `cf957a7649ec02835f724951d34f0b408f5f6de2`; chunk03-v1 was intentionally interrupted and must never be replayed. Keep e-paper deferred, outputs fake/locked, no cross-sensor offsets, and use only new immutable Local Agent task ids. Do not resume autonomous work until I explicitly tell you to continue.

That prompt is intentionally shorter than this document; this file is the durable source of detailed continuation context.
