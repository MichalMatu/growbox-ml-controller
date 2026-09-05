# Growbox ML project roadmap and chat handoff

Updated: 2026-09-05
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Local Agent repository id: `growbox-ml-controller`
Agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`

## Purpose and source-of-truth hierarchy

This file is the durable project-level roadmap and preferred orientation document for a fresh chat. It answers where the project came from, what is physically proven now, what remains locked and what the next gates are.

For a fresh chat, use this order:

1. `AGENTS.md` — repository/Local Agent operating contract.
2. `docs/PROJECT_ROADMAP.md` — project history, architecture decisions and ordered gates.
3. `docs/CURRENT_STATUS.md` — concise current implementation/hardware state.
4. `docs/CONTINUATION_PLAN.md` — immediate next-work checklist.
5. `docs/OBSERVABILITY_AND_INFERENCE_PLAN.md` — derived-signal, physical-feedback and learning contract.
6. `docs/SHELLY_POWER_FEEDBACK.md` — Shelly API/power-signature evidence.
7. Stage-specific evidence documents only when needed.

Before changing anything in a fresh chat, verify the current `mvp/environment-controller` HEAD and `agent-control:.agent/status/daemon.json`. Never continue from remembered chat state alone.

## Project direction

The project is a native ESP-IDF growbox environmental controller with real sensors, local RF433 actuators, deterministic safety logic, logging/telemetry and an ML policy path. The current priority is to move from proven sensing and RF transport to safely supervised real-actuator integration while preserving separate safety, schedule, deterministic control and ML responsibilities.

Current policy boundary:

- rule policy remains authoritative;
- ML remains shadow/research-only until a later explicit qualification gate;
- automatic physical outputs remain fake-locked until the ordered gates authorize them;
- manual service RF is an explicit bounded diagnostic path;
- local TX completion or `SelfTx` is never physical socket/load acknowledgement;
- Shelly power feedback may provide independent physical load-state evidence during supervised tests;
- unattended real-output operation requires a separate later authorization.

## Completed milestones

### Stage27C — real-input native ESP-IDF baseline — FROZEN

Validated real-input runtime with SCD41, DS3231 and BLE climate inputs. Outputs stayed fake-locked throughout qualification.

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

Hardware-qualified service-console firmware identity:

`af16aebde8f69d1a1257256c7711e9721c07c9d5`

On 2026-09-05 the operator physically observed successful ESP-to-socket ON/OFF control for all three current RF loads:

| device | ON | OFF | protocol | physical TX profile | result |
| --- | ---: | ---: | ---: | --- | --- |
| lamp | 235030016 | 16926208 | 2 / 32 bit | 560 us, repeat 10 | physically confirmed |
| fan | 906118656 | 1040336384 | 2 / 32 bit | 575 us, repeat 10 | physically confirmed |
| humidifier | 637683200 | 771900928 | 2 / 32 bit | 560 us, repeat 10 | physically confirmed |

The permanent RF register is `docs/RF433_DEVICE_CODES.md`.

This proves the manual supervised ESP -> RF433 -> socket/load path for each device. It does not authorize unattended climate actuation.

### Gate 1 — semantic binding — COMPLETE

Frozen mappings:

- `remote_socket_1` / endpoint 1 -> `ExhaustFan`;
- `remote_socket_3` / endpoint 3 -> `Humidifier`;
- `remote_socket_2` / endpoint 2 -> dedicated scheduled-light path outside normal Climate-v6 output roles.

The binding validator fails closed for missing, duplicate, unknown, stale or lamp-as-climate mappings. Automatic outputs remain fake-locked.

### Gate 2 — lamp timer + thermal safety — COMPLETE

Source contract:

`11b02749fd5896e47ec01d03bcca333be2dea810`

Verification result:

- focused `stage28d_lamp_safety_tests` passed;
- Python `479 passed`, `3 skipped`, `9 deselected`;
- host C++ `20/20` passed;
- clang-tidy passed;
- ESP-IDF/pre-push quality gate passed;
- no RF TX occurred in the verification task and automatic outputs remained fake-locked.

Frozen thermal-safety behavior:

- trip at `28.0 C` -> lamp forced OFF;
- exhaust fan forced ON when available;
- recovery threshold `<=26.0 C`;
- continuous `10 min` recovery hold before latch clear;
- hold resets above `26.0 C`;
- stale/invalid/non-finite authoritative TP357 temperature fails closed for the lamp path.

## Current physical topology

### Environmental sensors

- TP357 BLE T/RH: inside growbox slightly above canopy; authoritative inside T/RH and thermal-safety temperature.
- SCD41: inside at pot height; authoritative inside CO2, diagnostic/backup T/RH.
- Xiaomi BLE T/RH: outside beside intake; intake-air T/RH context.
- DS3231: controller RTC; intended to store UTC and feed the Europe/Warsaw lighting schedule after conversion.

### RF433 loads

- endpoint 1 -> exhaust fan;
- endpoint 2 -> scheduled lamp;
- endpoint 3 -> humidifier.

### Independent power feedback

Shelly Plug S Gen3 is reachable from the Local Agent host at:

`192.168.0.16`

It is currently upstream of the growbox power strip and exposes relay state, active power, voltage, current, accumulated energy and internal temperature through local RPC.

Two supervised one-device-at-a-time power calibrations were completed. The repeat calibration waited `20 s` after every ON/OFF transition and sampled each settled state nine times.

Observed reference contributions:

- controlled-loads-OFF baseline: about `2.2 W`;
- lamp: about `97.0-97.1 W`;
- exhaust fan: about `2.8-3.2 W`;
- humidifier: about `15.4-15.7 W`.

The repeat returned to the same `2.2 W` baseline with all three RF loads OFF and Shelly master ON.

Use calibrated tolerance ranges rather than exact constants. Continue collecting settled signatures, especially for the low-power fan. `docs/SHELLY_POWER_FEEDBACK.md` is the durable reference.

## Lamp architecture decision

The lamp is intentionally a different control layer from the normal climate outputs.

Normal behavior:

`schedule/timer -> requested lamp state -> thermal safety override -> physical lamp output`

The current Climate-v6 model already consumes `schedule.light_level` and the simulator models lamp heat, but the model has six climate outputs and no lamp output. Do not force the lamp into `ClimateActuatorRole` merely to make it an ML output.

Safety override has higher priority than schedule and ML.

## CO2 and ventilation architecture decision

SCD41 CO2 is a real input to ventilation decisions, but there is no CO2 enrichment/doser actuator. Do not advertise or enable a nonexistent CO2 doser.

Normal exhaust-fan policy must not be blind periodic ventilation. Outside hard thermal safety, request ventilation when available evidence predicts exchange is useful.

Priority:

`thermal safety > humidity/VPD safety > CO2 replenishment > normal optimization > fan OFF`

Examples:

- if T/RH/VPD/CO2 are acceptable -> fan OFF;
- thermal trip -> lamp OFF + fan ON regardless of learned effectiveness;
- high inside moisture -> ventilate only when intake moisture content or learned response indicates drying benefit, unless higher-priority safety overrides;
- low CO2 during lights-on -> ventilation may replenish CO2 when observed/predicted exchange is beneficial.

## Existing-sensor observability and inference track

The project should extract maximum information from already installed hardware before adding more sensors. The durable contract is `docs/OBSERVABILITY_AND_INFERENCE_PLAN.md`.

Derived signals should include at least:

- dew point;
- absolute humidity/moisture content;
- air VPD;
- inside-versus-intake temperature/moisture gradients;
- robust `dT/dt`, `dAbsoluteHumidity/dt`, `dCO2/dt` slopes;
- actuator response delay/time constants;
- Shelly power signatures and physical-state confidence;
- sensor freshness/disagreement/confounder flags.

Actuator-effect learning should use clean transitions and baseline slopes. For fan ventilation:

`fan_effect(variable) ~= slope_ON(variable) - slope_OFF_baseline(variable)`

This can reveal measured cooling, drying and CO2-exchange effects. For CO2 it may later support an effective intake-CO2/ACH model, but initially store observable ppm/min response rather than inventing a precise outdoor ppm value.

Similarly collect lamp thermal contribution and humidifier moisture contribution when other actuators are stable.

These observations are useful to deterministic arbitration first and later become strong ML features because they represent what the environment and hardware actually did, not merely what the controller requested.

Hard deterministic safety can never be overruled by learned/inferred effects.

## Ordered gates from current state

### Gate 3 — time, hardware profile and observability foundations — NEXT

#### Gate 3A — DS3231 UTC + Europe/Warsaw schedule

- store UTC in DS3231;
- add bounded RTC set/write/readback support;
- add deterministic CET/CEST conversion for Europe/Warsaw with DST boundary host tests;
- schedule lighting `06:00-22:00` Europe/Warsaw local time;
- preserve trusted/untrusted RTC semantics.

#### Gate 3B — actual hardware capability contract

Runtime capabilities must reflect actual hardware:

- heater false;
- cooler false;
- exhaust fan true;
- humidifier true;
- dehumidifier false;
- CO2 doser false.

Inspect `targets.co2_enabled` semantics before changing it. If it denotes enrichment/dosing, keep it false and implement a separate ventilation-CO2 policy.

#### Gate 3C — observability plumbing, software only

While outputs remain fake-locked, add or prepare pure derived metrics/telemetry needed for:

- inside/intake moisture and temperature gradients;
- environmental slopes;
- actuator transition context;
- confidence/invalid/ambiguous states;
- later host-side Shelly correlation.

Do not block safety/time qualification on a large ML model. Logging plus deterministic pure helpers is sufficient first.

#### Gate 3 verification

Run focused tests for time conversion, schedule boundaries, capability contract and derived-metric helpers, followed by exactly one final full quality gate. No real automatic RF TX.

### Gate 4 — exact-SHA flash and read-only hardware smoke

After Gate 3 passes:

- flash exact qualified SHA;
- verify firmware identity and `outputs=fake-locked`;
- verify RF readiness and service console;
- verify TP357, Xiaomi, SCD41 and DS3231;
- set/read back DS3231 UTC;
- verify Europe/Warsaw local schedule interpretation.

### Gate 5 — bounded physical role-routing with independent feedback

Prove one endpoint at a time, each ending OFF:

1. `ExhaustFan` -> only fan;
2. `Humidifier` -> only humidifier;
3. scheduled light -> only lamp.

For each transition record:

- requested semantic state;
- RF TX evidence;
- Shelly before/after power and voltage;
- expected power-signature match/confidence;
- final safe OFF state.

Shelly provides independent electrical evidence but does not replace environmental/physical response where relevant.

### Gate 6 — supervised thermal-safety test without real overheating

Use deterministic temperature injection rather than deliberately overheating the growbox. Verify physically:

- lamp forced OFF at trip;
- fan forced ON when available;
- recovery remains latched until `<=26 C` continuously for `10 min`;
- no chatter;
- Shelly signatures agree with expected lamp/fan state transitions;
- final state is explicitly safe.

### Gate 7 — bounded ventilation-effect capture and short supervised closed loop

Before/within the first closed-loop session, collect clean fan OFF -> ON -> OFF windows with:

- TP357 inside T/RH;
- Xiaomi intake T/RH;
- SCD41 inside CO2;
- derived absolute humidity/VPD;
- pre-action baseline slopes;
- post-action slopes;
- lamp/humidifier states;
- Shelly fan power confirmation;
- response delay and confidence.

Use this to establish the first measured ventilation-effect model. Learned effects remain advisory until repeatability is demonstrated.

Then run a short conservative real-sensor closed-loop session and verify sensor freshness, requests, physical outputs, Shelly confirmation, telemetry and safety together.

### Gate 8 — separate unattended real-output authorization

Only after Gates 1-7 pass may a later task propose an unattended real-output soak. It requires separate explicit authorization and a bounded safety plan.

## Local Agent and Chat Bridge — mental model

### ChatGPT / planner

The chat decides what bounded task should happen next, reads repository/control-plane evidence, writes or queues exact work and judges results. It must not claim success from intent alone.

### Chat Bridge

The wake envelope pins repository identity and immutable binding:

- `LA_REPO=growbox-ml-controller`;
- `LA_REPOSITORY=MichalMatu/growbox-ml-controller`;
- `LA_AGENT=815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`.

A different repository requires explicit rebind. Never guess or silently switch repositories.

Useful bridge controls:

- `[LAB:NEXT=30s]` or another interval;
- `[LAB:PAUSE]`;
- `[LAB:STOP]`;
- `[LAB:INTERVAL=AUTO]`.

### Local Agent

Local Agent is the deterministic local executor. It reads immutable tasks from `agent-control`, executes declared commands against the declared work branch and writes run/result/status evidence back to the control branch.

Control-plane locations:

- `.agent/tasks/<task-id>.json`;
- `.agent/runs/<task-id>.json`;
- `.agent/results/<task-id>.json`;
- `.agent/status/daemon.json`.

Every Growbox task must contain exactly:

`"agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5"`

Use:

- `resources: []` for repository-local software/docs/build work;
- `resources: ["board:growbox-s3"]` for USB/serial/flashing/hardware work.

One task per repository at a time. Task IDs and payloads are immutable; a retry uses a new ID. `expected_head` is not implemented, so tasks that depend on an exact SHA must verify it explicitly.

The work branch contains product/source changes. `agent-control` is only the execution/control plane.

## Fresh-chat bootstrap

A fresh chat should:

1. honor the exact Bridge binding envelope;
2. read `AGENTS.md`;
3. read `docs/PROJECT_ROADMAP.md`;
4. read `docs/CURRENT_STATUS.md` and `docs/CONTINUATION_PLAN.md`;
5. read `docs/OBSERVABILITY_AND_INFERENCE_PLAN.md` when working on telemetry/feedback/learning;
6. fetch fresh work-branch HEAD and daemon status;
7. continue from the first incomplete gate;
8. never reopen completed physical RF validation unless new evidence invalidates it.

Recommended human instruction:

`Continue Growbox from docs/PROJECT_ROADMAP.md. Verify fresh HEAD and Local Agent daemon first. Start from the first incomplete gate. Keep automatic physical outputs fake-locked until the roadmap explicitly reaches a supervised hardware gate.`
