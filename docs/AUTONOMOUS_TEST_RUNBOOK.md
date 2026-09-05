# Autonomous daytime test runbook

Updated: 2026-09-05
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`

## Scope

This runbook defines the bounded daytime autonomous work sequence for the current growbox reference rig. It is not permanent unattended-production authorization. Every stage advances only after the previous stage has explicit terminal evidence. Failures are handled by repair/reverification for software-only work or by fail-closed stop for physical-risk work.

Automatic physical outputs remain fake-locked until the relevant software and hardware gates explicitly open them.

## Continuous supervision contract

During autonomous execution ChatGPT/Local Agent must repeatedly inspect the active task/run/result/daemon evidence and must not infer success from a queued task or a local TX completion alone.

For software stages monitor at least:

- exact work-branch SHA;
- Local Agent task identity and immutable binding;
- focused-test result;
- final full quality-gate result;
- git diff/status cleanliness;
- memory/time-limit failures.

For hardware stages additionally monitor:

- exact firmware SHA read back from the service console;
- reboot/crash indicators;
- sensor validity/freshness;
- RTC trust and UTC/local-time interpretation;
- RF transport readiness;
- requested actuator state versus RF TX evidence;
- Shelly power delta/physical-state confidence;
- storage backend health and queue/write errors;
- final safe actuator state.

Any `Guru Meditation`, unexpected reset, storage-error escalation, stale authoritative thermal input, untrusted RTC when schedule operation is required, unexplained load power, or failure to achieve a requested safety state blocks progression.

## Data persistence policy

### Primary storage: microSD

Use the existing Stage27 SD telemetry backend as the primary continuous archive.

Current implementation:

- FAT filesystem mount point: `/sdcard`;
- telemetry directory: `/sdcard/GBLOG`;
- NDJSON-like `.JL` session files;
- sample interval on SD: `10 s`;
- health record interval on SD: `60 s`;
- records are flushed after append;
- SD remount/recovery is already supported by the telemetry logger.

### Internal flash fallback

If SD is unavailable, use the existing internal-flash fallback rather than losing all telemetry.

Current implementation is not LittleFS: it uses a wear-levelled FAT partition named `telemetry`, mounted at `/flog`.

Current fallback behavior:

- sample interval on flash: `60 s`;
- health interval on flash: `300 s`;
- segmented/rotating files limit flash growth/wear;
- logger periodically retries SD and returns to SD when it recovers.

Do not replace this proven fallback with LittleFS during today's hardware qualification unless a separate requirement appears. The existing wear-levelled FAT fallback already solves the immediate resilience requirement.

### Storage health acceptance

Track and log:

- active backend (`sd`, `flash`, `none`);
- SD/flash mounted status;
- mount errors;
- write errors;
- queue drops;
- skipped records;
- fallback activations;
- SD recoveries;
- records written;
- last successful write time.

For a supervised/soak stage, `active_backend=none`, persistent write errors, increasing queue drops or a stale `last_write_ms` are faults that must be investigated before claiming the data run successful.

## What to persist

Extend the telemetry record over time so one timestamped record can reconstruct both environment and controller context. Preserve at minimum:

- monotonic uptime;
- trusted UTC epoch from DS3231;
- Europe/Warsaw local schedule context;
- TP357 inside T/RH, age/freshness and battery diagnostics;
- SCD41 CO2 plus diagnostic T/RH, age/freshness and sensor health;
- Xiaomi intake T/RH, age/freshness and battery diagnostics;
- derived air VPD, dew point and absolute humidity;
- inside-intake temperature and moisture gradients;
- robust T/moisture/CO2 trends/slopes when available;
- requested lamp/fan/humidifier states;
- effective state after safety arbitration;
- reason/priority for each decision;
- RF TX evidence;
- Shelly active power, voltage/current and inferred physical-state confidence when available;
- actuator-transition timestamps;
- pre/post actuator response windows;
- storage health counters;
- safety-latch state and reason;
- firmware SHA/config identity.

Actuator-effect experiments should additionally persist the baseline slope before activation and the response slope after activation so `effect ~= slope_ON - slope_OFF_baseline` can be computed later.

## Ordered autonomous sequence

### 1. Finish Gate 3A/3B/3C software

Complete and verify:

- DS3231 UTC encoding/write/readback;
- `rtc set-unix <epoch>` service command;
- Europe/Warsaw CET/CEST conversion including DST boundaries;
- local `06:00-22:00` light schedule;
- real hardware capabilities (`heater=false`, `cooler=false`, `exhaust_fan=true`, `humidifier=true`, `dehumidifier=false`, `co2_doser=false`);
- pure observability/derived-metric helpers needed for moisture gradients and later response analysis;
- no automatic physical TX.

Run focused tests followed by exactly one final full software quality gate.

### 2. Exact-SHA hardware smoke

Only after the software gate is green:

- flash exact qualified firmware;
- verify embedded firmware SHA;
- verify `outputs=fake-locked`;
- verify RF ready;
- verify TP357, Xiaomi, SCD41, DS3231;
- verify SD storage mount and active logging;
- set DS3231 from current host UTC and immediately read it back;
- verify Europe/Warsaw local conversion/schedule phase;
- verify no crash/reset/error markers.

### 3. Shelly-assisted actuator routing check

Use the already-qualified RF codes one load at a time. For each actuator:

- establish stable total-power baseline;
- send explicit RF ON;
- wait long enough for settled confirmation when required;
- read Shelly power and compare delta with calibrated range;
- send explicit RF OFF;
- verify matching negative power delta and return to baseline;
- record environmental state and storage health;
- finish OFF.

Reference centers from two supervised calibrations:

- lamp about `97.0-97.1 W`;
- fan about `2.8-3.2 W`;
- humidifier about `15.4-15.7 W`;
- current controlled-loads-OFF baseline about `2.2 W`.

Use ranges/confidence, not exact equality.

### 4. Deterministic thermal-safety qualification

Without deliberately overheating the growbox, exercise the temperature-injection/test path through at least:

- safe below trip;
- approach trip;
- exact `28 C` trip;
- above trip;
- recovery below trip but above `26 C`;
- `<=26 C` continuous recovery hold;
- full `10 min` latch-clear behavior.

Require:

- lamp OFF at trip;
- fan ON at trip when available;
- Shelly confirms expected electrical state changes;
- no chatter;
- stale/invalid authoritative TP357 input fails closed;
- final state safe.

### 5. Ventilation-effect identification

Collect bounded `fan OFF -> fan ON -> fan OFF` windows while other actuator changes are minimized.

Persist:

- TP357 inside T/RH;
- Xiaomi intake T/RH;
- SCD41 inside CO2;
- absolute humidity/VPD;
- baseline OFF trends;
- post-ON trends;
- fan power confirmation from Shelly;
- response delay and settling behavior;
- lamp/humidifier state;
- confidence/confounders.

First useful learned outputs:

- fan `delta T/min` attributable effect;
- fan `delta absolute humidity/min` attributable effect;
- fan `delta CO2/min` attributable effect;
- response delay/time constant;
- indication whether current intake air improves or worsens each variable.

Do not claim exact outdoor CO2 from one transient. Start with effective response and confidence.

### 6. Lamp and humidifier response windows

When safe, collect similarly clean transitions to estimate:

- lamp thermal slope contribution and delay;
- humidifier absolute-humidity/RH contribution and persistence;
- electrical power signatures versus environmental response.

This enables detection such as `power present but expected physical/environmental effect missing`.

### 7. Short real closed-loop run

Only after prior gates pass:

- deterministic rule controller remains authoritative;
- ML remains shadow/research-only;
- run conservative real-sensor logic;
- continuously verify freshness, decisions, RF evidence, Shelly state confidence and storage health;
- fan defaults OFF when climate is acceptable;
- normal ventilation requires predicted/direct benefit except hard thermal safety;
- record all decision and response data for later replay.

### 8. Bounded daytime soak

A longer daytime run is allowed only if all prior gates remain green. Continuously monitor:

- temperatures and safety margin to `28 C`;
- RH/VPD/moisture state;
- CO2 behavior;
- actuator switching frequency/dwell;
- Shelly unexplained power changes;
- storage continuity;
- reset/crash counters;
- sensor freshness;
- RTC trust;
- environmental response to each actuator.

At the end, force/verify the intended safe physical state and record final Shelly power, sensor state and storage counters.

## Fail-closed escalation

Software-only failure:

- inspect failure;
- repair source;
- create a new immutable verification task;
- do not continue to hardware until green.

Hardware/control failure:

- do not guess physical state;
- send explicit safe actuator commands when possible;
- verify with Shelly/environmental feedback;
- if safe state cannot be established and the master cutoff is appropriate for the wiring/fault, use the separately qualified Shelly master cutoff;
- stop the risky stage and retain logs/evidence.

The master cutoff is not the normal thermal response because cutting the shared strip may also remove the exhaust fan. Normal thermal safety remains `lamp OFF + fan ON`.

## Autonomous supervision cadence

Use Chat Bridge wakeups during active tasks so the chat reviews fresh daemon/run/result evidence instead of waiting for manual prompts. During physical stages, keep wake cadence sufficiently frequent to catch terminal failures and inspect the next gate promptly. A task that is still running is not considered successful until the terminal result is read.

## Completion criterion for today's session

Today's autonomous session is successful when the system has:

- a fully verified UTC/local-time and hardware-capability software slice;
- exact-SHA real-hardware smoke evidence;
- persistent SD telemetry with validated fallback behavior available;
- Shelly-confirmed actuator signatures/routes;
- deterministic thermal-safety evidence;
- at least initial clean ventilation-effect observations;
- a short conservative closed-loop evidence set;
- no unresolved safety/storage/reset faults;
- an explicitly verified final physical state.

A later unattended/overnight production-style run remains a separate authorization gate.
