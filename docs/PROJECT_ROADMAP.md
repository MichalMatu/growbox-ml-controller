# Growbox ML project roadmap and chat handoff

Updated: 2026-09-05
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Local Agent repository id: `growbox-ml-controller`
Agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`

## Purpose and source-of-truth hierarchy

This file is the durable project-level roadmap and the preferred orientation document for a fresh chat. It answers: where the project came from, what is physically proven now, what remains locked, and what the next gates are.

For a fresh chat, use this order:

1. `AGENTS.md` — repository/Local Agent operating contract.
2. `docs/PROJECT_ROADMAP.md` — project history, architecture decisions and next gates.
3. `docs/CURRENT_STATUS.md` — concise current implementation/hardware state.
4. `docs/CONTINUATION_PLAN.md` — immediate next-work checklist.
5. Stage-specific evidence documents only when the next task needs their detailed evidence.

`continuation.md` remains useful historical long-form evidence from earlier sessions, but this roadmap plus `CURRENT_STATUS.md` / `CONTINUATION_PLAN.md` is the current handoff surface.

Before changing anything in a fresh chat, verify the current `mvp/environment-controller` HEAD and `agent-control:.agent/status/daemon.json`. Never continue from remembered chat state alone.

## Project direction

The project is a native ESP-IDF growbox environmental controller with real sensors, local RF433 actuators, deterministic safety logic, logging/telemetry and an ML policy path. The current priority is to move from proven sensing and RF transport to safely supervised real-actuator integration without collapsing safety, schedule and ML responsibilities into one layer.

Current policy boundary:

- rule policy remains authoritative;
- ML remains shadow/research-only until a later explicit qualification gate;
- unattended physical outputs remain fake-locked;
- manual service RF is allowed only as an explicit bounded operator-present diagnostic;
- local TX completion or `SelfTx` is never physical socket/load acknowledgement.

## Completed milestones

### Stage27C — real-input native ESP-IDF baseline — FROZEN

Validated real-input runtime with SCD41, DS3231 and BLE climate inputs. The platform direction is native ESP-IDF. Outputs stayed fake-locked throughout qualification.

### Stage28A — RF433 codec/classification — DONE

Native protocol-2 RF433 codec and temporal classification were established.

### Stage28B — ESP-IDF RMT TX/RX — DONE

Native RMT transport and loopback were qualified. Historical Stage28B receive timing must not replace the later hardened receive contract.

### Stage28C — physical RF identity — DONE/FROZEN

The original frozen neutral socket pair was physically qualified and later identified by the operator as the fan socket.

Fan profile:

- ON `906118656` / `0x36024600`;
- OFF `1040336384` / `0x3E024600`;
- protocol 2, 32 bit;
- reliable ESP TX profile `575 us`, repeat `10`.

### Pre-Stage28D golden gate — COMPLETE

Golden source/firmware `316b58e76de609069ddbf2667fe86f6218fb2143` passed the complete software gate and a strict 5400-second real-hardware soak with real sensors/RTC/BLE/SD, no resets and outputs fake-locked.

Later executable service-console firmware was separately qualified. Do not call docs-only branch HEADs hardware-soaked firmware identities.

### Stage28D — service console and physical RF validation — COMPLETE FOR MANUAL RF PATH

The primary-UART service console is usable from the normal CH340 serial path and provides read-only diagnostics plus explicit named manual RF commands.

Hardware-qualified service-console firmware identity:

`af16aebde8f69d1a1257256c7711e9721c07c9d5`

On 2026-09-05 the operator physically observed successful ESP-to-socket ON/OFF control for all three current RF loads:

| device | ON | OFF | protocol | physical TX profile | result |
| --- | ---: | ---: | ---: | --- | --- |
| lamp | 235030016 | 16926208 | 2 / 32 bit | 560 us, repeat 10 | physically confirmed |
| fan | 906118656 | 1040336384 | 2 / 32 bit | 575 us, repeat 10 | physically confirmed |
| humidifier | 637683200 | 771900928 | 2 / 32 bit | 560 us, repeat 10 | physically confirmed |

The permanent RF register is `docs/RF433_DEVICE_CODES.md`.

This proves the manual supervised ESP -> RF433 -> socket/load path for each device. It does not yet authorize unattended climate actuation.

## Current physical topology

Sensors:

- TP357 BLE thermo/hygrometer: inside growbox;
- Xiaomi BLE thermo/hygrometer: outside growbox;
- directly connected ESP32 sensors, including SCD41 and DS3231: inside/controller installation.

RF433 loads:

- fan socket -> semantic climate role `ExhaustFan` is the intended mapping;
- humidifier socket -> semantic climate role `Humidifier` is the intended mapping;
- lamp socket -> scheduled light actuator, not a normal Climate-v6 ML output.

## Lamp architecture decision

The lamp is intentionally a different control layer from the normal climate outputs.

Normal behavior:

`schedule/timer -> requested lamp state -> safety override -> physical lamp output`

The current Climate-v6 model already consumes `schedule.light_level` and the simulator models lamp heat, but the model has six climate outputs and no lamp output. Therefore do not force the lamp into `ClimateActuatorRole` merely to make it an ML output.

Required safety behavior:

- normal ON/OFF comes from the lighting schedule/timer;
- actual/requested lamp state must remain visible to the climate/ML feature path as light context;
- an independent over-temperature safety layer may force the lamp OFF even when the timer requests ON;
- the safety layer must also command maximum available exhaust ventilation when appropriate;
- recovery must use hysteresis / minimum recovery conditions so the lamp cannot chatter ON/OFF around one threshold;
- safety override has higher priority than schedule and ML;
- current automated physical outputs stay fake-locked until this behavior is implemented and qualified.

This is deliberately separate from whether a future model version should gain a seventh light-control output. That is a later research decision, not required for the next physical-control gate.

## Next-night plan — ordered gates

The growbox is ready for the next supervised physical session. Do not jump directly to unattended overnight actuation. Complete these gates in order.

### Gate 1 — semantic binding, software only

Implement/freeze the hardware-to-role mapping without enabling real automatic TX:

- fan RF endpoint -> `ExhaustFan`;
- humidifier RF endpoint -> `Humidifier`;
- lamp RF endpoint -> dedicated scheduled-light output path.

Unknown/duplicate/missing bindings must fail closed. Keep the runtime output driver fake-locked.

### Gate 2 — lamp timer + thermal safety, software only

Add the scheduled lamp state and independent thermal safety override. Cover at least:

- timer ON while safe -> requested ON;
- timer OFF -> OFF;
- over-temperature -> forced lamp OFF regardless of timer;
- high temperature -> fan request forced to safe/high state when available;
- recovery hysteresis prevents rapid lamp cycling;
- stale/unusable required temperature input fails safe for physical lighting policy;
- no real RF TX occurs in host/unit tests.

The exact thresholds should be configuration, not hidden magic constants in the RF driver.

### Gate 3 — focused software verification

Run focused host tests for role mapping, schedule/safety arbitration and RF command selection, then the impact-appropriate build/test gate. Executable changes require Local Agent verification before hardware use.

### Gate 4 — flash and read-only hardware smoke

Flash the newly qualified build, verify exact firmware SHA, `outputs=fake-locked`, RF readiness, sensors and service console. No actuation until those gates pass.

### Gate 5 — supervised physical role-routing test

With the operator physically present, enable only a bounded test path and prove one endpoint at a time:

1. `ExhaustFan` request controls only the fan and finishes OFF.
2. `Humidifier` request controls only the humidifier and finishes OFF.
3. scheduled-light request controls only the lamp and finishes OFF.

For every test distinguish local TX evidence from the operator's physical observation.

### Gate 6 — supervised thermal-safety test without real overheating

Use an explicit deterministic test/injection path rather than deliberately overheating the growbox. While the timer requests lamp ON, inject/simulate the configured over-temperature condition and physically verify:

- lamp is forced OFF;
- fan is forced ON when available;
- humidifier/other heat-aggravating actions are inhibited as defined by safety policy;
- clearing the injected condition does not immediately chatter the lamp back ON; recovery follows the configured hysteresis/hold rule;
- final physical state is explicitly returned to the intended safe state.

The test hook must not remain accidentally enabled in normal operation.

### Gate 7 — short supervised closed-loop growbox run

After Gates 1-6 pass, run a short real-sensor closed-loop test while the operator is present. Verify sensor freshness, requested actions, physical outputs, telemetry and RF behavior together. Start conservatively; the goal is evidence, not aggressive climate optimization.

### Gate 8 — separate authorization for unattended real-output soak

Only after the supervised gates pass should a later task propose an unattended soak with real physical outputs. That is a separate operator authorization and safety gate. Do not infer authorization from the manual RF tests completed on 2026-09-05.

## Local Agent and Chat Bridge — mental model

### ChatGPT / planner

The chat decides what bounded task should happen next, reads repository/control-plane evidence, writes or queues exact work, and judges results. It must not claim success from intent alone.

### Chat Bridge

Chat Bridge transports wakeups between the project and this chat. Its wake envelope pins repository identity and the immutable binding. For this project the wake must identify:

- `LA_REPO=growbox-ml-controller`;
- `LA_REPOSITORY=MichalMatu/growbox-ml-controller`;
- `LA_AGENT=815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`.

A different repository requires explicit rebind. Never guess or silently switch repositories.

Bridge control markers used by the chat:

- `[LAB:NEXT=30s]` or another interval — wake again to check continuing work;
- `[LAB:PAUSE]` — stop wakeups because operator input/physical observation is needed;
- `[LAB:STOP]` — goal is complete/no continuation;
- `[LAB:INTERVAL=AUTO]` — allow automatic wake interval selection.

### Local Agent

Local Agent is the deterministic local executor. It does not decide project architecture. It reads immutable tasks from `agent-control`, executes the declared commands against the declared work branch, and writes run/result/status evidence back to the control branch.

Control-plane locations:

- `.agent/tasks/<task-id>.json` — immutable request;
- `.agent/runs/<task-id>.json` — execution state;
- `.agent/results/<task-id>.json` — terminal result;
- `.agent/status/daemon.json` — fresh worker state.

Every Growbox task must contain exactly:

`"agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5"`

Use:

- `resources: []` for repository-local software/docs/build work;
- `resources: ["board:growbox-s3"]` for USB/serial/flashing/hardware work.

One task per repository at a time. Task IDs and payloads are immutable; a retry uses a new ID. `expected_head` is not implemented, so tasks that depend on an exact SHA must verify it explicitly.

The work branch contains product/source changes. `agent-control` is only the execution/control plane.

## Fresh-chat bootstrap

When moving to a new chat, the operator does not need to retell the project history. The fresh chat should:

1. honor the exact Bridge binding envelope;
2. read `AGENTS.md`;
3. read `docs/PROJECT_ROADMAP.md`;
4. read `docs/CURRENT_STATUS.md` and `docs/CONTINUATION_PLAN.md`;
5. fetch fresh work-branch HEAD and daemon status;
6. continue from the first incomplete gate in **Next-night plan**;
7. never reopen completed physical RF validation unless new evidence invalidates it.

Recommended human instruction after opening the new chat:

`Continue Growbox from docs/PROJECT_ROADMAP.md. Verify fresh HEAD and Local Agent daemon first. Start from the first incomplete next-night gate. Keep physical outputs fake-locked until the roadmap explicitly reaches a supervised hardware gate.`
