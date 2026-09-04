# Growbox continuation handoff

Date: 2026-09-04
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Control branch: `agent-control`

This is the primary bootstrap file for the next ChatGPT conversation. Read it first, then verify fresh branch/daemon state before doing any work.

## 1. Frozen Stage27C baseline

Stage27C CrowPanel real-input validation is complete and frozen.

Annotated milestone tag:

`stage27c-validated-2026-09-03`

Stage27C closure commit:

`b418520090d0feadc005701092c1b7ed3384afbf`

Exact physically soaked Stage27C firmware:

`a5726b89e94b9ac628249b780d6548a692c3fd2c`

Validated baseline remains:

- Elecrow CrowPanel ESP32-S3 N8R8;
- native ESP-IDF v5.5.4;
- SCD41 + DS3231 on SDA21/SCL38;
- microSD MOSI40/MISO13/CLK39/CS10/power42;
- exact BLE identities already frozen in existing Stage27C docs;
- Rule authoritative;
- ML shadow-only;
- physical outputs fake/locked.

Do not restart Stage27A/B/C.

## 2. Stage28 current state

Stage28 RF433 actuator work is active, but Stages 28A and 28B are now complete.

### Stage28A — DONE

Native RF433 codec and temporal classification were implemented and tested.

Source milestone:

`ac29122cbcf9d155fd08baa0df1014d71f04c135`

Implemented under:

`src/climate/rf433/`

Key constraints retained:

- protocols 1..12;
- bits 1..32;
- bounded repeat/pulse validation;
- `FrameKey` identity;
- `SelfTx` vs interference temporal classification;
- no Arduino dependency.

### Stage28B — DONE

Native ESP-IDF RMT TX/RX local RF loopback is implemented and physically qualified.

Initial RMT source commit:

`56813b27f6dc1f93d4899974ffd47a1528d8b6b8`

Final qualified RF source commit:

`a87169748ee2bd42bc4d35cfe3b2964b90f40eb8` — `Fix RF433 RMT receive timing limits`

Final hardware configuration:

- TX GPIO8;
- RX GPIO14;
- TX/codec resolution `100 kHz`;
- RX resolution `1 MHz`;
- RX minimum signal/glitch filter `1,250 ns`;
- RX maximum signal/idle threshold `12,000,000 ns`;
- RX durations converted back to codec ticks before decode.

Original RX configuration failed at `rmt_receive()` with `ESP_ERR_INVALID_ARG (0x102)`. The final configuration above was established by bounded hardware diagnostics and then committed permanently.

Final hardware recheck task:

`20260904-growbox-stage28b-final-hardware-recheck-v1`

Exact firmware/source SHA under test:

`a87169748ee2bd42bc4d35cfe3b2964b90f40eb8`

Final local RF evidence:

`requested 0xA55A/16/protocol1 -> TX queued -> TX started -> TX completed -> RX captured -> decoded 0xA55A/16/protocol1 -> SelfTx`

Counters at acceptance:

- RX arm errors `0`;
- RX timeouts `0`;
- RX decode failures `0`;
- RX ambiguous `0`;
- RX self-TX `1`;
- RX interference `0`;
- outputs remained `fake-locked`.

The strict 180-second Stage27 regression capture reported `violations: []`.

Detailed evidence:

`docs/STAGE28B_FINAL_EVIDENCE.md`

### Critical evidence boundary

Stage28B proves local RF transport only. It does **not** prove that a mains socket changed state.

Keep these distinct:

1. TX request accepted/completed;
2. local RF receiver heard and decoded the transmitted frame (`SelfTx`);
3. actual socket/load state changed.

Never promote level 1 or 2 to level 3 without explicit physical validation.

## 3. Next gate — Stage28C

Stage28C is the exact next task.

Goal: learn and freeze **one** original remote/socket pair before semantic integration.

Capture separate ON and OFF identities from the original remote and freeze:

- ON code;
- OFF code;
- bit length;
- protocol;
- pulse timing;
- repeat behavior needed for reliable transmission;
- stable human-readable device/role label.

Rules:

- first target exactly one socket/device;
- store RF identity in hardware/config layer, not Rule/ML policy code;
- no semantic climate role mapping yet;
- no unattended real-load control yet;
- do not treat self-RX as socket-state acknowledgement.

Stage28C should begin with a bounded receiver/capture task, then freeze one proven ON/OFF pair.

## 4. Remaining Stage28 roadmap

### Stage28D — semantic integration

After 28C passes:

- first role: `exhaust_fan`;
- second role: `humidifier`;
- lamp remains separate and must not be silently mapped to an unrelated climate role.

RF hardware stays below `ClimateRoleDriver` / `MappedClimateRoleDriver`; do not duplicate Rule/ML policy.

### Stage28E — fail-safe/recovery

Before unattended operation prove:

- defined boot command behavior;
- stale/unusable sensor data cannot leave an unsafe Rule command active;
- failed RF request is not recorded as confirmed physical state;
- TX acceptance/completion and physical confirmation remain separate;
- reset/restart semantics are explicit;
- bounded repeated OFF recovery exists where appropriate;
- Rule stays authoritative;
- ML stays shadow-only;
- one actuator at a time.

### Stage28F — real socket/load gate

Only after one remote ON/OFF pair is frozen:

1. verify socket manually with original remote;
2. send bounded ON/OFF from CrowPanel;
3. verify TX/self-RX evidence;
4. explicitly verify real socket/load response;
5. repeat bounded transitions;
6. then run one-role bounded soak.

## 5. Local Agent / binding rules

Growbox Local Agent binding:

`815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`

Every Local Agent task JSON created for this project must contain exactly:

`"agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5"`

Repository scope is immutable for Growbox tasks:

`MichalMatu/growbox-ml-controller`

Do not infer, substitute, queue, cancel or execute work for another repository.

Task rules:

- work branch: `mvp/environment-controller`;
- control branch: `agent-control`;
- one active Growbox task at a time;
- task IDs immutable;
- hardware tasks use `resources: ["board:growbox-s3"]`;
- software-only tasks use `resources: []`;
- verify expected work-branch SHA manually before editing because `expected_head` is not implemented;
- command-based source commit + push remains preferred for permanent Local Agent changes.

A new ChatGPT conversation must use the Chat Bridge `LA_CHAT` value assigned to that new conversation. Do not reuse the old chat id blindly.

## 6. First actions in the next conversation

1. Read this file completely.
2. Read `docs/STAGE28B_FINAL_EVIDENCE.md`.
3. Read `docs/CURRENT_STATUS.md` for the short source-of-truth status.
4. Fetch fresh `mvp/environment-controller` HEAD. The RF implementation to preserve is rooted at `a87169748ee2bd42bc4d35cfe3b2964b90f40eb8`; documentation-only commits may advance HEAD after it.
5. Fetch fresh `agent-control:.agent/status/daemon.json`.
6. Verify exact repository and agent binding.
7. Require daemon `idle` before queueing anything.
8. Do not repeat Stage28A/28B unless later source changes invalidated their evidence.
9. Start the smallest Stage28C remote-capture task for one socket only.

## 7. Scope guard

Do not mix into Stage28 unless explicitly requested:

- ML Active;
- e-paper/front-panel UI;
- multiple real actuators at once;
- unrelated repository work;
- Arduino compatibility layers.

Current transition point is clean:

**Stage28A DONE -> Stage28B DONE -> Stage28C NEXT.**
