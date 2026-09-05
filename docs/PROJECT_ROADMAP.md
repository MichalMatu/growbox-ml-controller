# Growbox ML project roadmap and chat handoff

Updated: 2026-09-05
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Local Agent repository id: `growbox-ml-controller`
Agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`

## Source-of-truth order

For a fresh chat, read:

1. `AGENTS.md`
2. `docs/PROJECT_ROADMAP.md`
3. `docs/CURRENT_STATUS.md`
4. `docs/CONTINUATION_PLAN.md`
5. `docs/OBSERVABILITY_AND_INFERENCE_PLAN.md`
6. `docs/SHELLY_POWER_FEEDBACK.md`
7. stage-specific evidence only when needed

Then fetch fresh `mvp/environment-controller` HEAD and `agent-control:.agent/status/daemon.json`. Never continue from remembered chat state alone.

## Project direction

The project is a native ESP-IDF growbox environmental controller using real sensors, local RF433 actuators, deterministic safety, telemetry/logging and a shadow ML path.

Current policy boundary:

- deterministic rule policy is authoritative;
- ML remains shadow/research-only;
- installed firmware returns to fake-locked after every bounded physical qualification;
- real outputs are allowed only inside explicit bounded test/qualification tasks;
- local RF TX completion is not physical load acknowledgement;
- Shelly power is independent electrical evidence;
- environmental response is required before claiming actual airflow/moisture effect;
- unattended operation remains a separate future authorization decision.

## Completed platform milestones

### Stage27C - real-input native ESP-IDF baseline - FROZEN

Real SCD41, DS3231 and BLE inputs, SD telemetry and fake-locked outputs were qualified.

### Stage28A - RF433 codec/classification - DONE

Native protocol-2 RF433 codec and temporal classification established.

### Stage28B - ESP-IDF RMT TX/RX - DONE

Native RMT transport and loopback qualified.

### Stage28C - physical RF identity - DONE/FROZEN

Current physical RF devices are frozen as:

| role/load | ON | OFF | profile |
| --- | ---: | ---: | --- |
| fan / endpoint 1 | 906118656 | 1040336384 | protocol 2, 32 bit, 575 us, repeat 10 |
| lamp / endpoint 2 | 235030016 | 16926208 | protocol 2, 32 bit, 560 us, repeat 10 |
| humidifier / endpoint 3 | 637683200 | 771900928 | protocol 2, 32 bit, 560 us, repeat 10 |

### Pre-Stage28D golden gate - COMPLETE

Golden source/firmware `316b58e76de609069ddbf2667fe86f6218fb2143` passed the complete software gate and a strict 5400-second real-hardware soak with outputs fake-locked.

### Stage28D manual service path - COMPLETE

Hardware-qualified manual service-console firmware:

`af16aebde8f69d1a1257256c7711e9721c07c9d5`

Manual ON/OFF control for lamp, fan and humidifier was physically observed on 2026-09-05.

## Gate 1 - semantic binding - COMPLETE

Frozen mapping:

- endpoint 1 -> `ExhaustFan`;
- endpoint 3 -> `Humidifier`;
- endpoint 2 -> dedicated scheduled-light path.

The validator fails closed for missing, duplicate, unknown, stale or scheduled-light-as-climate bindings.

## Gate 2 - lamp timer + thermal safety - COMPLETE

Source contract:

`11b02749fd5896e47ec01d03bcca333be2dea810`

Frozen behavior:

- trip at `>=28.0 C` -> lamp OFF;
- exhaust fan requested ON when available;
- recovery threshold `<=26.0 C`;
- continuous recovery hold `10 min`;
- hold resets above `26.0 C`;
- stale/invalid/non-finite authoritative TP357 temperature fails closed for the lamp path.

Focused tests, Python, host C++, clang-tidy and ESP-IDF/pre-push all passed.

## Gate 3 - time, hardware profile and observability - COMPLETE

Executable verification SHA:

`8710bf127ad895e262f604e1b4c59ea11b760667`

Completed:

- DS3231 UTC storage;
- bounded service-console RTC write/readback;
- deterministic Europe/Warsaw CET/CEST conversion with DST tests;
- local schedule `06:00-22:00`;
- actual capability contract: exhaust + humidifier only for climate outputs;
- SCD41 CO2 as ventilation input, not dosing capability;
- deterministic dew point, absolute humidity, VPD and inside/intake gradients.

## Gate 4 - exact-SHA read-only hardware smoke - COMPLETE

Exact SHA `8710bf127ad895e262f604e1b4c59ea11b760667` was flashed and verified with live TP357, Xiaomi, SCD41, DS3231, RF readiness and healthy SD telemetry while outputs remained fake-locked.

## Gate 5 - physical role routing with independent power evidence - COMPLETE

Shelly reference baseline/signatures:

- controlled-loads-OFF baseline about `2.2 W`;
- lamp contribution about `+97.0 W`;
- exhaust fan about `+2.9 W`;
- humidifier about `+15.7 W`.

Each role was physically confirmed and the test returned all RF loads OFF with Shelly master ON.

## Gate 6 - deterministic physical thermal safety - COMPLETE

A bounded injected-temperature sequence physically proved:

- hot trip -> lamp OFF;
- safety -> fan ON;
- latch retained above recovery threshold;
- `<=26 C` held continuously for 10 minutes before latch clear;
- no humidifier cross-activation;
- final fake-locked/all-OFF cleanup.

Do not repeat the long thermal sequence unless safety code changes.

## Ventilation-effect identification - COMPLETE

A controlled fan OFF -> ON -> OFF experiment with TP357 inside, Xiaomi intake and SCD41 inside CO2 showed:

- inside absolute humidity during fan ON about `-0.312 g/m3/min`;
- inside CO2 about `-3.09 ppm/min`;
- inside-minus-intake AH gradient reduced from about `3.27` to `0.96 g/m3`;
- temperature effect was small.

This establishes the key control principle:

**moisture-exchange decisions should use absolute humidity/moisture content, not raw RH alone.**

Outside CO2 is not measured. Store/learn observable CO2 response, not invented outdoor ppm.

## Gate 7 - binary/dwell arbitration + physical closed loop - COMPLETE

Hardware-qualified code identity:

`3dfc4b552f669f628d5c9bee455a34666915088c`

Architecture:

`rule request -> binary/dwell arbiter -> confirmed actual applied -> RF endpoint -> telemetry`

Default arbiter settings:

- exhaust: ON `0.10`, OFF `0.03`, min ON/OFF `120 s`;
- humidifier: ON `0.10`, OFF `0.03`, min ON/OFF `180 s`;
- safety may force exhaust ON immediately;
- clearing safety does not bypass min-ON;
- emergency safe OFF bypasses dwell;
- failed physical transition does not advance internal state.

The control loop reconciles estimator state to confirmed actual applied levels so binary RF sockets are no longer represented by fractional applied values.

Persisted telemetry includes requested/applied fan and humidifier state, thermal state and arbiter counters.

### Short exact-SHA closed loop

A 10-minute bounded real-output run passed:

- 58 output records;
- 52 healthy SD-backed records;
- max requested fan about `0.317`;
- 111 dwell holds;
- no fan/humidifier transition because full threshold+dwell conditions were not satisfied;
- TP357 about `24.2-26.1 C`;
- final fake-locked/all-OFF cleanup at about `2.2 W`.

### 30-minute exact-SHA bounded soak

A subsequent 1800-second bounded real-output soak passed:

- 174 output records;
- 159 healthy SD-backed records;
- 174 lamp-ON records;
- 0 fan-ON records;
- 0 humidifier-ON records;
- max requested fan about `0.331`;
- 111 dwell holds;
- 0 transitions;
- 0 safety overrides;
- TP357 about `25.3-27.8 C`;
- final fake-locked, all RF loads OFF, Shelly master ON, about `2.2 W`.

The fan staying OFF is consistent with arbiter semantics: requests above threshold occurred while minimum-OFF dwell still blocked the transition and later request history did not satisfy conditions for a state change. Software regressions already cover sustained requests, hysteresis, dwell, safety immediate-ON and fail-safe OFF behavior.

### Shelly transient behavior learned during Gate 7

Shelly occasionally returned isolated low-power values while the physical lamp state remained unchanged. A separate lamp-stability run showed about `98.3-98.8 W` continuously for roughly three minutes with no persistent drop.

Physical harness rule:

- wait for state settling;
- sample multiple times;
- use a median/robust aggregate;
- fail only on repeated/persistent signature mismatch;
- still fail immediately on hard unsafe power or master-relay loss.

## Current physical topology

### Sensors

- TP357 BLE inside above canopy: authoritative inside T/RH and thermal safety;
- SCD41 inside near pot height: primary inside CO2, diagnostic/backup T/RH;
- Xiaomi BLE beside intake outside tent: intake T/RH;
- DS3231: UTC RTC feeding Europe/Warsaw local schedule.

### Growbox

- approximate dimensions `60 x 60 x 180 cm`;
- approximate volume `0.648 m3`;
- current plant: mint.

## Current control baseline

- light schedule `06:00-22:00` Europe/Warsaw;
- nominal day target about `24 C`;
- nominal night target about `21-21.5 C`;
- lamp hard trip `>=28 C`;
- lamp recovery `<=26 C` continuously for 10 minutes;
- RH target around `60%`, initial normal band about `55-65%`;
- VPD target roughly `1.2 kPa` day and `0.9-1.0 kPa` night;
- CO2 informs ventilation only; no dosing hardware;
- no soil-moisture or PAR/PPFD sensor currently in the control contract.

## First incomplete control slice - moisture-aware ventilation policy

The existing rule request still contains mixed raw-RH logic. This is now the first incomplete control-quality issue.

Required next software behavior:

1. use inside-versus-intake absolute humidity for moisture-exchange benefit;
2. preserve temperature-exchange benefit separately;
3. keep SCD41 CO2 as a ventilation context signal;
4. never infer an exact outside CO2 concentration;
5. preserve thermal-safety fan override above normal benefit scoring;
6. leave Gate 7 binary/dwell arbitration unchanged unless a focused regression proves a defect;
7. keep ML shadow-only.

Required regression cases:

- intake RH equal/higher but intake AH lower -> ventilation may still be drying-beneficial;
- intake RH lower but intake AH higher -> no drying-benefit claim;
- invalid/stale intake moisture -> no positive moisture-benefit inference;
- thermal safety forces fan regardless of normal exchange score;
- CO2 ventilation context does not enable a nonexistent CO2 doser.

Verification sequence:

- focused host tests first;
- exactly one final full software quality gate;
- outputs fake-locked and no board resource for software verification;
- only after software PASS decide whether the changed policy needs a short new exact-SHA physical confirmation.

Do not repeat completed RF routing, thermal recovery, lamp-stability or 30-minute soak tests without a new code change or explicit new hypothesis.

## Local Agent / Chat Bridge contract

Every Growbox task must contain exactly:

`"agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5"`

Use:

- `resources: []` for software/docs/build;
- `resources: ["board:growbox-s3"]` for USB/serial/flashing/hardware.

Task IDs and payloads are immutable. Retry with a new ID. Work branch contains product/source changes; `agent-control` is execution/control evidence only.

## Fresh-chat bootstrap

A fresh chat should:

1. honor the exact Bridge binding envelope;
2. read `AGENTS.md`, this roadmap, `CURRENT_STATUS` and `CONTINUATION_PLAN`;
3. fetch fresh work HEAD and daemon status;
4. treat Gates 1-7 as complete;
5. continue with the moisture-aware ventilation policy slice;
6. keep ML shadow-only;
7. avoid repeating completed physical gates unless new evidence invalidates them.
