# Growbox continuation handoff

Date: 2026-09-03
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Control branch: `agent-control`

This is the primary bootstrap file for the next ChatGPT conversation. Read this file first, then verify fresh repository and Local Agent state before doing any work.

## 1. Where we are coming from

Stage27C CrowPanel real-input validation is complete and frozen as a tested milestone.

Frozen annotated tag:

`stage27c-validated-2026-09-03`

The tag points at the coherent Stage27C closure repository state:

`b418520090d0feadc005701092c1b7ed3384afbf`

The exact firmware that was physically flashed and qualified is different and must remain distinguishable from later documentation/test commits:

`a5726b89e94b9ac628249b780d6548a692c3fd2c` — `Disable Stage27C CMD0 precondition by default`

Stage27C final evidence is frozen in:

- `docs/STAGE27C_FINAL_EVIDENCE.md`
- `docs/CURRENT_STATUS.md`
- `docs/CONTINUATION_PLAN.md`

Do not reopen Stage27C merely because the work branch advances after the tag.

### Stage27C validated hardware/runtime state

- Elecrow CrowPanel ESP32-S3 N8R8;
- native ESP-IDF v5.5.4 only;
- no Arduino component in `growbox-ml-controller`;
- SCD41 + DS3231 on shared I2C, SDA GPIO21 / SCL GPIO38;
- microSD on MOSI40 / MISO13 / CLK39 / CS10 / power GPIO42;
- TP357 BLE exact MAC `F7:5F:8D:0F:76:20` as primary inside T/RH;
- Xiaomi/PVVX/BTHome exact MAC `A4:C1:38:4F:24:CD` as nearby ambient T/RH;
- SCD41 supplies controller CO2 and diagnostic local/window T/RH;
- DS3231 supplies trusted wall-clock state;
- Rule policy remains authoritative;
- ML remains shadow-only;
- physical outputs remain fake/locked;
- e-paper/front-panel remains outside the validated scope.

Final acceptance included seven strict 5400-second SD-primary soak chunks = 37,800 s = 10.5 h active accepted soak, with preserved MCU uptime continuity. Across accepted chunks: zero resets, zero serial disconnects, zero parser errors, zero SD mount/write/drop/skip failures, zero SCD41 read/invalid errors, clean BLE freshness/scanning diagnostics, trusted RTC and exact firmware SHA throughout.

Point-6 host validation finished with full portable host suite `17/17` PASS and targeted Stage27C tests `3/3` PASS.

## 2. New goal: Stage28 — RF433 physical actuator bring-up

The next product step is to connect the already-qualified sensor/Rule path to real controllable devices through the user's 433 MHz mains sockets.

Available devices include sockets intended for:

- exhaust/circulation fan;
- humidifier;
- lamp.

The CrowPanel HAT already has both a 433 MHz transmitter module and receiver module connected. This makes it possible to qualify the radio transport first with a local RF loop before relying on mains-device behavior.

### Important evidence boundary

The RF receiver can prove that the transmitter emitted a decodable frame over the actual radio path. It does **not** by itself prove that a mains socket changed state, because ordinary 433 MHz sockets generally do not provide a state acknowledgement.

Keep three evidence levels distinct:

1. TX backend accepted/completed the requested frame;
2. local RX captured and decoded the expected transmitted frame (`self-TX` loop evidence);
3. physical socket/load actually changed state — this still needs an explicit physical validation step unless independent load/power feedback is later added.

Never call level 1 or 2 a confirmed physical actuator state.

## 3. RF433 donor implementation

Known working RF433 code exists in the donor repository:

`MichalMatu/esp32s3_LiteGraph`

The inspected donor revision was:

`f17c8e59feac80d66b3036b8993ea2ac6bacac5c`

Relevant donor files:

- `lib/framework/hardware/rf433/Rf433ProtocolCodec.h`
- `lib/framework/hardware/rf433/Rf433RmtTxBackend.h/.cpp`
- `lib/framework/hardware/rf433/Rf433RmtRxBackend.h/.cpp`
- `lib/framework/hardware/rf433/Rf433RxBackend.h`
- `src/features/rf433/Rf433Service.cpp`
- `include/platform/hardware/profiles/CrowPanelEsp32S3Common.h`

Useful proven donor behavior:

- CrowPanel RF433 TX data pin: GPIO8;
- CrowPanel RF433 RX data pin: GPIO14;
- RMT resolution: 100 kHz;
- codec supports protocol IDs 1..12;
- code length up to 32 bits;
- configurable repeat and pulse length;
- RMT RX decodes bounded pulse captures;
- service tracks TX start/completion and classifies RX frames occurring during the TX window;
- matching local transmissions are classified as `SelfTx`, while mismatching traffic in the same interval is classified as interference;
- diagnostics already distinguish RX captures, decode failures, ambiguous frames, drops, self-TX, external frames and interference.

### Porting rule

`esp32s3_LiteGraph` is a **donor/reference**, not a dependency.

Do not import Arduino into `growbox-ml-controller`. Some donor implementation files include Arduino/platform wrappers even though the underlying radio path uses ESP-IDF RMT/FreeRTOS. Adapt or reimplement the minimum required behavior using the existing native ESP-IDF architecture of `growbox-ml-controller`.

Prefer reusable protocol/state-machine ideas and pure data structures. Preserve the growbox hardware-neutral seams; RF433 hardware code must live below the semantic actuator layer and must not duplicate Rule/ML policy.

## 4. Proposed Stage28 roadmap

### Stage28A — native RF433 source audit and minimal port plan

Before editing firmware:

1. inspect the exact current growbox hardware/driver seams;
2. inspect donor codec, RMT TX, RMT RX and self-TX classification code at the pinned donor SHA above;
3. identify all Arduino/LiteGraph-specific dependencies that must not cross into growbox;
4. freeze the growbox RF433 pin ownership as TX GPIO8 / RX GPIO14 only after checking it does not conflict with the final Stage27C CrowPanel profile;
5. define the smallest native ESP-IDF RF433 API required by the semantic actuator layer;
6. add host tests for protocol encode/decode and self-TX temporal classification before hardware use.

No mains switching in Stage28A.

### Stage28B — RF loopback qualification, no socket control yet

Use the HAT transmitter and receiver as a closed radio test loop.

Required evidence for a test frame:

`requested FrameKey -> TX queued -> TX started -> TX completed -> RX capture -> decoded identical FrameKey -> classified as self-TX`

Collect at minimum:

- requested code / bit length / protocol / pulse / repeat;
- TX completion and timing;
- RX decoded fingerprint;
- RX classification;
- capture/decode/drop/ambiguity counters;
- timeout/error counters;
- heap/stack diagnostics needed for the new workers;
- no regression in SCD41, RTC, BLE or SD diagnostics.

Run bounded repeated-send tests after a single-frame smoke test. Do not weaken existing Stage27C safety boundaries during this work.

### Stage28C — learn and freeze the user's socket codes

Use the physical receiver to capture the original remote control for each socket.

For every device record separate ON/OFF frame identity:

- code;
- bit length;
- protocol;
- estimated/selected pulse length;
- repeat count used for reliable transmission;
- human role/device label.

Do not hard-code unexplained magic numbers in policy code. Store the RF identity in the hardware/config layer.

First target only one socket/device until the full path is proven.

### Stage28D — semantic actuator integration

Recommended first semantic role: `exhaust_fan`.

Reason: the climate runtime already has a stable `exhaust_fan` semantic output and the first real-output integration should exercise an existing role without inventing new policy semantics.

Then add `humidifier` after the fan path passes its own gate.

The lamp needs separate treatment. `light_level` currently exists as schedule/context, but the six climate ML-controlled semantic outputs are heater, cooler, exhaust fan, humidifier, dehumidifier and CO2 doser. Do not silently map the lamp onto an unrelated climate actuator role. Either add/use an existing dedicated scheduled-light output seam after source inspection, or keep lamp control outside Stage28 climate actuation until that contract is explicitly designed.

### Stage28E — fail-safe behavior before unattended control

For each real actuator role prove at least:

- boot starts from a defined safe command path;
- stale/unusable required sensor data cannot keep unsafe Rule output active;
- rejected/failed RF request does not become a falsely confirmed applied state;
- runtime records command acceptance/completion separately from physical confirmation;
- reset/restart semantics are explicit;
- repeated OFF transmission can be issued as a recovery action where appropriate;
- ML remains shadow-only;
- Rule remains authoritative;
- one actuator is qualified before adding another.

Do not claim fail-safe physical state solely from a self-RX frame. A one-way RF socket can miss a transmission even if local RX heard it.

### Stage28F — real socket/load gate

After RF loopback PASS and one socket's codes are frozen:

1. test the socket manually with its original remote;
2. send one bounded ON/OFF sequence from CrowPanel;
3. verify TX and self-RX evidence;
4. explicitly verify the real socket/load response;
5. repeat a bounded number of transitions;
6. then run a longer but still bounded real-output soak for that one role.

Only after this gate should the next device/role be added.

## 5. Longer-term roadmap after Stage28

### Stage29 — real closed-loop operating traces

Once real sensor inputs and selected real outputs are stable:

- log real measurements;
- Rule proposal and applied command;
- RF transport result;
- known/observed actuator state evidence;
- environmental response after actuation;
- ML Shadow proposal in parallel;
- safety/arbitration interventions.

These traces become the real dataset for evaluating ML usefulness.

### Stage30 — ML qualification from real traces

Before any `MlActive` use:

- offline replay;
- Rule vs ML comparison;
- counterfactual evaluation;
- safety intervention rate;
- robustness to stale/missing/noisy inputs;
- explicit qualification gate.

Do not promote ML merely because it produces plausible commands.

### Optional independent track — e-paper/front-panel

E-paper/UI may be implemented as a separate goal, but it should not block actuator correctness and should not be mixed into Stage28 hardware safety validation unless explicitly chosen.

## 6. Local Agent workflow

ChatGPT is the planner. Local Agent is the deterministic local executor. GitHub `agent-control` is the control/evidence plane.

Current Growbox agent binding used by this project:

`815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`

A new ChatGPT conversation must use the Chat Bridge binding actually assigned to that new conversation. Do not blindly reuse the old conversation's `LA_CHAT` value.

For Growbox tasks:

- repository must be exactly `MichalMatu/growbox-ml-controller`;
- work branch is `mvp/environment-controller` unless a new explicit branch is created;
- control branch is `agent-control`;
- every new Local Agent task JSON created for this project must carry the exact current Growbox `agent_binding`;
- task files: `.agent/tasks/<immutable-id>.json`;
- live run: `.agent/runs/<id>.json`;
- terminal result: `.agent/results/<id>.json`;
- daemon state: `.agent/status/daemon.json`.

One active Growbox goal/task at a time. Never queue a second task while the current task is active.

Task IDs are immutable. If a task is invalid, interrupted or needs changed parameters, create a new ID such as `v2`; never mutate/replay the old semantic identity as if nothing happened.

Evidence priority:

1. exact terminal result;
2. exact live run/attempt;
3. daemon state;
4. exact source/diff/test evidence;
5. planner reasoning.

Never claim a hardware PASS without terminal hardware evidence.

The donor repository `MichalMatu/esp32s3_LiteGraph` may be inspected read-only for RF433 implementation evidence, but Growbox Local Agent tasks must not silently switch repositories. A separate repository goal/binding would be required for donor-repo edits.

## 7. Local Chat Bridge workflow

The Chat Bridge only wakes the selected ChatGPT conversation. It does not plan work and it does not decide repository scope.

Normal wake sequence for one active task:

1. inspect `.agent/results/<task-id>.json` first;
2. if no terminal result, inspect `.agent/runs/<task-id>.json`;
3. inspect `.agent/status/daemon.json`;
4. verify exact repository, task ID, attempt/binding and resource ownership;
5. if running normally, wait for the next bridge wake;
6. after terminal PASS/FAIL, decide the next bounded task from exact evidence.

Bridge pacing markers used by this workflow:

- `[LAB:NEXT=30s]` — early liveness check after queueing;
- `[LAB:NEXT=3m]` — near completion / medium task;
- `[LAB:NEXT=10m]` — healthy long task;
- `[LAB:PAUSE]` — manual hardware/user action required;
- `[LAB:STOP]` — goal complete; stop autonomous wakes.

If a manual hardware action is required, give the user one exact physical instruction and return `[LAB:PAUSE]`. Do not guess that the action happened.

## 8. First actions in the next ChatGPT conversation

1. Read this `continuation.md` completely.
2. Read `docs/STAGE27C_FINAL_EVIDENCE.md` and `docs/CURRENT_STATUS.md` only as frozen baseline/context; do not restart Stage27C.
3. Fetch fresh `mvp/environment-controller` HEAD.
4. Fetch fresh `agent-control:.agent/status/daemon.json` and confirm no active Growbox task before writing/queueing anything.
5. Verify `stage27c-validated-2026-09-03` still identifies the frozen Stage27C closure milestone.
6. Inspect the RF433 donor files listed above at donor SHA `f17c8e59feac80d66b3036b8993ea2ac6bacac5c` plus the current growbox hardware/semantic output seams.
7. Start Stage28A with a bounded source/architecture audit and native port plan — no physical socket switching yet.
8. Preserve native ESP-IDF, Rule-authoritative, ML-shadow-only behavior throughout initial RF bring-up.
9. After the software/native RF layer is tested, qualify TX→air→RX self-loop before commanding a mains socket.
10. Bring up exactly one real socket/actuator role first.

## 9. Scope guard

Stage27C is DONE and tagged.

The next goal is not "more Stage27C". It is a new actuator/radio qualification stage built on top of the validated Stage27C baseline.

Do not mix into Stage28 unless explicitly requested:

- ML Active;
- e-paper/front-panel UI;
- multiple real actuators at once;
- unrelated repository work;
- Arduino compatibility layers.
