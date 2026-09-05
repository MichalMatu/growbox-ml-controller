# Current controller status

Updated: 2026-09-05
Development branch: `mvp/environment-controller`
Primary roadmap/handoff: `docs/PROJECT_ROADMAP.md`
Continuation checklist: `docs/CONTINUATION_PLAN.md`
Observability contract: `docs/OBSERVABILITY_AND_INFERENCE_PLAN.md`
Shelly feedback reference: `docs/SHELLY_POWER_FEEDBACK.md`

## Current transition

**Stage27C FROZEN -> Stage28A DONE -> Stage28B DONE -> Stage28C DONE -> pre-Stage28D golden gate COMPLETE -> Stage28D manual RF path COMPLETE -> Gates 1-7 COMPLETE -> next software slice: moisture-aware ventilation policy**

Do not reopen completed physical RF identity, deterministic thermal-safety, ventilation-identification, binary/dwell arbitration, short closed-loop or 30-minute bounded-soak tests unless new evidence invalidates them.

## Current safety state

- Rule policy remains authoritative.
- ML remains shadow/research-only.
- Installed firmware has been returned to `outputs=fake-locked` after physical qualification.
- Final controlled-load state after the 30-minute soak was lamp OFF, fan OFF, humidifier OFF, Shelly master ON, about `2.2 W`.
- Real-output operation is allowed only inside explicit bounded hardware tasks with fail-closed cleanup.
- Local RF TX completion is transport evidence, not physical load acknowledgement.
- Shelly power is independent electrical evidence; environmental response is still required when claiming airflow/moisture effect.

## Current exact hardware-qualified code identity

Gate 7 physical closed-loop and bounded soak used exact source/firmware SHA:

`3dfc4b552f669f628d5c9bee455a34666915088c`

A later docs-only commit must not be described as a separately hardware-tested firmware identity.

## Gate 3 - time, profile and observability - COMPLETE

Executable SHA used for Gate 3 verification and read-only hardware smoke:

`8710bf127ad895e262f604e1b4c59ea11b760667`

Completed behavior:

- DS3231 stores UTC;
- service console supports bounded `rtc set-unix <epoch>` write/readback;
- Europe/Warsaw CET/CEST conversion is deterministic and DST-boundary tested;
- lighting schedule evaluates `06:00-22:00` in Europe/Warsaw local time;
- actual hardware capabilities are fan + humidifier only for climate outputs;
- SCD41 CO2 is an input, not a nonexistent CO2-doser capability;
- dew point, absolute humidity, VPD and inside/intake gradients are available as deterministic observability metrics.

Gate 3 verification passed focused tests, Python, host C++, clang-tidy and ESP-IDF/pre-push quality gates with outputs fake-locked and no RF TX.

## Gate 4 - exact-SHA flash/read-only hardware smoke - COMPLETE

Gate 4 passed on the CrowPanel/ESP32-S3 with exact SHA `8710bf127ad895e262f604e1b4c59ea11b760667`.

Observed live sources included:

- TP357 inside T/RH;
- Xiaomi intake T/RH;
- SCD41 inside CO2/T/RH;
- DS3231 UTC with correct Europe/Warsaw conversion;
- SD telemetry advancing with zero write errors and queue drops;
- RF transport ready;
- Shelly baseline about `2.2 W` with controlled loads OFF.

Outputs remained fake-locked.

## Gate 5 - physical role routing - COMPLETE

Physical role routing was independently confirmed with Shelly power signatures:

| role/load | observed contribution | result |
| --- | ---: | --- |
| scheduled lamp | about `+97.0 W` | PASS |
| exhaust fan | about `+2.9 W` | PASS |
| humidifier | about `+15.7 W` | PASS |

The test ended at about `2.2 W`, all three controlled RF loads OFF and Shelly master ON.

Frozen RF identities:

- fan / `remote_socket_1`: ON `906118656`, OFF `1040336384`, protocol 2, 32 bit, 575 us, repeat 10;
- lamp / `remote_socket_2`: ON `235030016`, OFF `16926208`, protocol 2, 32 bit, 560 us, repeat 10;
- humidifier / `remote_socket_3`: ON `637683200`, OFF `771900928`, protocol 2, 32 bit, 560 us, repeat 10.

## Gate 6 - deterministic physical thermal safety - COMPLETE

Do not repeat the long thermal sequence unless the safety implementation changes.

Physically proven behavior:

- hot injected temperature trips the latch;
- lamp is physically forced OFF;
- exhaust fan is physically forced ON;
- recovery remains latched above the recovery threshold;
- `<=26 C` must remain continuous for 10 minutes before latch clear;
- lamp may resume only after the recovery hold completes and schedule allows it;
- humidifier did not spuriously activate;
- test cleanup returned all controlled loads OFF and firmware to fake-locked mode.

Safety thresholds remain:

- trip `>=28.0 C`;
- recovery threshold `<=26.0 C`;
- continuous recovery hold `10 min`;
- stale/invalid authoritative TP357 temperature fails closed for the lamp path.

## Ventilation identification - COMPLETE

A bounded fan OFF -> ON -> OFF identification run produced a clear moisture-exchange effect and negligible temperature effect.

Observed fan-on effect in that run:

- inside absolute humidity slope about `-0.312 g/m3/min`;
- inside CO2 slope about `-3.09 ppm/min`;
- inside-minus-intake absolute-humidity gradient reduced from about `3.27` to `0.96 g/m3`;
- temperature changed little.

Interpretation:

- ventilation moisture benefit must be evaluated using inside versus intake absolute humidity, not raw RH alone;
- outside CO2 is unmeasured, so do not claim a precise outdoor ppm value;
- use measured response slopes and confidence, not invented ACH/outdoor concentration.

## Gate 7 - binary/dwell arbitration and physical closed loop - COMPLETE

Exact qualified SHA:

`3dfc4b552f669f628d5c9bee455a34666915088c`

Architecture:

`rule request -> binary/dwell arbiter -> confirmed actual applied -> RF endpoint -> telemetry`

Default binary arbiter settings:

- exhaust fan: ON threshold `0.10`, OFF threshold `0.03`, minimum ON `120 s`, minimum OFF `120 s`;
- humidifier: ON threshold `0.10`, OFF threshold `0.03`, minimum ON `180 s`, minimum OFF `180 s`;
- thermal safety may force fan ON immediately, bypassing minimum-OFF;
- clearing thermal force does not bypass minimum-ON;
- emergency safe OFF bypasses dwell and safety-force state at the physical endpoint.

Confirmed-state semantics are now truthful: telemetry/estimator state reports binary actual application rather than fractional requests for RF sockets.

Persisted actuator telemetry records requested versus applied state and arbiter counters.

### Short closed-loop result

A 10-minute real-output session passed with:

- 58 output records;
- 52 healthy SD-backed soak records;
- lamp physically ON through the scheduled path;
- no fan or humidifier transition because the requests did not satisfy the complete dwell/threshold history needed for a transition;
- maximum requested fan about `0.317`;
- 111 dwell holds;
- zero RF TX errors;
- TP357 about `24.2-26.1 C`;
- final exact-SHA safe return to fake-locked, all RF loads OFF, about `2.2 W`, Shelly master ON.

### 30-minute bounded soak result

The bounded real-output soak also passed:

- duration `1800 s`;
- 174 output records;
- 159 healthy SD-backed soak records;
- lamp ON records `174`;
- fan ON records `0`;
- humidifier ON records `0`;
- maximum requested fan about `0.331`;
- arbiter dwell holds `111`;
- arbiter transitions `0`;
- safety overrides `0`;
- TP357 about `25.3-27.8 C`;
- storage write errors `0` and queue drops `0` in accepted telemetry;
- final exact-SHA safe return: fake-locked, all controlled RF loads OFF, Shelly master ON, about `2.2 W`.

Shelly occasionally returned isolated transient low-power medians while firmware state remained unchanged. Separate lamp-stability testing showed a stable physical lamp around `98.3-98.8 W` for about three minutes with no persistent drop. The closed-loop harness therefore requires repeated mismatches before failing instead of trusting one transient sample.

## Storage status

- SD primary path: `/sdcard/GBLOG/*.JL`, NDJSON;
- SD sample interval: 10 s;
- SD health interval: 60 s;
- flash fallback: wear-levelled FAT partition `telemetry` mounted at `/flog`;
- flash sample interval: 60 s;
- flash health interval: 300 s;
- SD retry/recovery path remains active;
- queue depth 16;
- health telemetry includes mount/write errors, queue drops, records written/skipped, fallback activations, recoveries and last write.

Short `storage_backend=none` telemetry transients were observed during physical sessions, followed by healthy SD records with zero write errors/queue drops. The bounded harness treats transient non-SD state as recoverable but fails if healthy SD telemetry does not return within 45 seconds.

## Current physical topology

| sensor | placement | role |
| --- | --- | --- |
| TP357 BLE | inside, slightly above canopy | authoritative inside T/RH and thermal safety |
| SCD41 | inside near pot height | primary inside CO2; backup/diagnostic T/RH |
| Xiaomi BLE | outside beside intake | intake T/RH for exchange-benefit inference |
| DS3231 | controller | UTC RTC / Europe-Warsaw schedule source |

Current growbox: approximately `60 x 60 x 180 cm`, tent volume about `0.648 m3`, mint plant.

## Immediate next work

The first incomplete control-quality issue is moisture-aware ventilation policy.

The existing rule request still contains mixed raw-RH logic. The next software slice should:

1. use inside versus intake absolute humidity as the moisture-exchange benefit signal;
2. keep temperature benefit scoring independent;
3. preserve CO2 as ventilation context without inventing outside CO2;
4. add regression tests for cases where outside RH is equal/higher but absolute humidity is lower and ventilation is still drying-beneficial;
5. retain deterministic thermal safety above all normal ventilation decisions;
6. keep ML shadow-only;
7. verify the software slice with focused tests and exactly one final full quality gate before any new hardware qualification.

Do not run another physical soak simply to repeat Gate 7. A new hardware run should be tied to a meaningful control-code change or a new specific hypothesis.
