# Fresh-context continuation plan

Updated: 2026-09-05
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Primary roadmap/handoff: `docs/PROJECT_ROADMAP.md`
Current status: `docs/CURRENT_STATUS.md`
Observability contract: `docs/OBSERVABILITY_AND_INFERENCE_PLAN.md`
Shelly power feedback: `docs/SHELLY_POWER_FEEDBACK.md`

## Read first in a new chat

1. `AGENTS.md`
2. `docs/PROJECT_ROADMAP.md`
3. `docs/CURRENT_STATUS.md`
4. this file
5. `docs/OBSERVABILITY_AND_INFERENCE_PLAN.md` when changing ventilation, inference, telemetry or ML features
6. `docs/SHELLY_POWER_FEEDBACK.md` when changing physical-state supervision

Then fetch fresh `mvp/environment-controller` HEAD and `agent-control:.agent/status/daemon.json`. Never continue from remembered chat state alone.

## Current transition

**Stage27C FROZEN -> Stage28A DONE -> Stage28B DONE -> Stage28C DONE -> pre-Stage28D golden gate COMPLETE -> Stage28D manual RF path COMPLETE -> Gates 1-7 COMPLETE -> moisture-aware ventilation policy NEXT**

Gate 7 hardware-qualified code identity:

`3dfc4b552f669f628d5c9bee455a34666915088c`

Later docs-only commits are not separately hardware-qualified firmware identities.

## Completed physical evidence - do not repeat by default

### RF role routing

- lamp physical signature about `+97 W`;
- fan physical signature about `+2.9 W`;
- humidifier physical signature about `+15.7 W`;
- all controlled loads OFF baseline about `2.2 W`.

### Thermal safety

A deterministic injected-temperature sequence physically proved:

- lamp forced OFF at the hot trip;
- fan forced ON by safety;
- 10-minute `<=26 C` recovery hold;
- no humidifier cross-activation;
- final fake-locked/all-OFF cleanup.

Do not repeat this long thermal test unless safety code changes.

### Ventilation identification

A bounded fan OFF -> ON -> OFF experiment showed:

- absolute humidity inside fell about `0.312 g/m3/min` while fan was ON;
- CO2 fell about `3.09 ppm/min`;
- inside-minus-intake absolute-humidity gradient fell from about `3.27` to `0.96 g/m3`;
- temperature effect was small.

Conclusion: moisture ventilation benefit must be based on absolute humidity/moisture content, not raw RH alone.

### Gate 7 short closed loop

Exact SHA `3dfc4b552f669f628d5c9bee455a34666915088c` passed a 10-minute real-output closed loop with truthful requested-versus-applied binary actuator telemetry, SD logging, Shelly correlation and final fake-lock cleanup.

Key result:

- 58 output records;
- 52 healthy SD-backed records;
- maximum requested fan about `0.317`;
- no physical fan/humidifier transition because complete threshold+dwell conditions were not satisfied;
- 111 dwell holds;
- TP357 about `24.2-26.1 C`;
- final about `2.2 W`, all RF loads OFF, Shelly master ON.

### Gate 7 30-minute bounded soak

The same exact SHA passed a 30-minute bounded soak:

- 174 output records;
- 159 healthy SD-backed records;
- lamp ON for the scheduled interval in all 174 output records;
- fan ON records `0`;
- humidifier ON records `0`;
- maximum requested fan about `0.331`;
- arbiter dwell holds `111`, transitions `0`, safety overrides `0`;
- TP357 about `25.3-27.8 C`;
- final fake-locked, all controlled RF loads OFF, Shelly master ON, about `2.2 W`.

Isolated Shelly low-power samples were not persistent. A separate lamp-stability test held about `98.3-98.8 W` for roughly three minutes with no persistent drop. Physical harnesses should therefore use settled median samples and require repeated mismatch before declaring a physical-state failure.

## Frozen Gate 7 actuator architecture

Control chain:

`rule request -> Stage28dBinaryRoleArbiter -> confirmed actual applied -> RF endpoint -> telemetry`

Defaults:

- fan ON threshold `0.10`, OFF threshold `0.03`, minimum ON/OFF `120 s`;
- humidifier ON threshold `0.10`, OFF threshold `0.03`, minimum ON/OFF `180 s`;
- thermal safety bypasses fan minimum-OFF to force immediate ON;
- clearing safety does not bypass minimum-ON;
- emergency safe OFF bypasses dwell;
- failed RF transition does not advance arbiter state;
- applied telemetry is binary actual state, not the fractional request.

Persisted actuator telemetry includes requested fan/humidifier, applied fan/humidifier, thermal latch/force state and arbiter counters.

## Current locked boundary

- rule controller authoritative;
- ML shadow/research-only;
- installed firmware returned to fake-locked after every bounded physical test;
- automatic real output is not a permanent/unattended mode yet;
- any future physical run must be bounded, exact-SHA, Shelly-supervised, storage-supervised and end with explicit RF OFF + fake-lock;
- do not perform another soak without a specific changed-control hypothesis.

## First incomplete software slice - moisture-aware ventilation

The current rule request still mixes raw-RH logic with ventilation decisions. Replace the moisture-exchange part with deterministic inside-versus-intake absolute-humidity benefit logic.

Required behavior:

1. calculate/use valid inside and intake absolute humidity from synchronized T/RH;
2. ventilate for moisture removal only when intake air is meaningfully drier in absolute-humidity terms;
3. preserve independent temperature-benefit logic;
4. keep SCD41 CO2 as ventilation context without pretending outside CO2 is measured;
5. preserve hard thermal-safety fan override above normal benefit logic;
6. keep binary/dwell arbitration unchanged unless a test demonstrates a defect;
7. keep ML shadow-only.

Required regressions include:

- outside/intake RH equal to or higher than inside RH but lower absolute humidity -> ventilation may still be drying-beneficial;
- outside/intake RH lower but absolute humidity higher -> do not claim drying benefit;
- stale/invalid intake moisture evidence -> do not use it as a positive drying-benefit signal;
- thermal safety still forces fan ON regardless of normal benefit scoring;
- CO2 ventilation context remains independent of nonexistent CO2 dosing capability.

## Verification order for the next slice

1. fetch fresh work HEAD and confirm daemon idle;
2. inspect the existing rule-request moisture/ventilation path and current derived-metric helpers;
3. make the smallest deterministic code change needed for absolute-humidity benefit;
4. add focused host regression tests first;
5. run focused tests;
6. run exactly one final full quality gate with outputs fake-locked and no hardware task;
7. only after software PASS, decide whether the behavioral change needs a new short exact-SHA physical confirmation.

A new hardware run should target the changed ventilation behavior, not repeat RF identity, thermal recovery, lamp stability or the previous 30-minute soak.

## Local Agent / Chat Bridge essentials

Hard binding for every Growbox task:

`"agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5"`

Use `resources: []` for software/docs/build and `resources: ["board:growbox-s3"]` for USB/serial/flashing/hardware. Task IDs and payloads are immutable; a retry always uses a new ID.

Chat Bridge only transports wakeups and pins repository identity. Local Agent executes queued tasks. ChatGPT must inspect result evidence before claiming completion.

Recommended fresh-chat instruction:

`Continue Growbox from docs/PROJECT_ROADMAP.md and docs/CONTINUATION_PLAN.md. Verify fresh work-branch HEAD and Local Agent daemon first. Gates 1-7 are complete; start from the moisture-aware ventilation policy slice. Keep ML shadow-only and do not repeat completed physical gates without new evidence.`
