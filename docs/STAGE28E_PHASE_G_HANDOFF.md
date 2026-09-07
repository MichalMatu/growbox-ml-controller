# Stage28E Phase G handoff — bounded runtime validation and representative soak

Updated: 2026-09-07

Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Local Agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`
Validated firmware/source SHA: `389453882f0e0d2209c5bdece7eaf443895aa7ba`
Correct serial device: `/dev/cu.usbserial-1130`

## Scope and safety

Phase G validated the Stage28E runtime under representative fake-locked operation before any Phase H physical actuator path.

All hardware validation retained these safety boundaries:

- `GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=0`
- `GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=0`
- `GROWBOX_RF433_LOOPBACK_ENABLED=0`
- `GROWBOX_STAGE28E_BREADCRUMB_RESTART_SELFTEST=0`
- outputs remained `fake-locked`
- Shelly master remained ON
- no physical fan/lamp/humidifier actuation was permitted

The final physical `AH/rule request -> binary arbiter -> RF -> physical fan` path remains Phase H only.

## G1 short bounded runtime

Original hardware task:

`20260907-growbox-stage28e-phase-g-short-runtime-v1`

The original task result was formally `failed` because its parser required `scd_sample=1` on every telemetry row, including the first row at approximately `751 ms` uptime before the SCD41 had produced its first sample.

Read-only diagnosis proved this was a harness false negative:

- BLE scanning was healthy for all retained telemetry rows;
- the only SCD anomaly was the first row at `uptime_ms=751`, with `scd_sample=0` and `scd_samples=0`;
- the last retained row had `scd_sample=1` and `scd_samples=37`.

Formal corrected reanalysis task:

`20260907-growbox-stage28e-phase-g-short-v1-reanalysis-v1`

Result: PASS.

Measured short-run evidence:

- boot ID: `a8d86e45`
- reset reason: `1`
- arbiter `instance_id=1`
- arbiter construction count: `1`
- status uptime range: `19339 -> 179489 ms`
- internal free/min/largest: `223792 / 223152 / 180224 B`
- PSRAM free/largest: `8358772 / 8257536 B`
- main configured stack: `12288 B`
- main worst observed HWM: `7240 B` free
- `stage27_store` configured stack: `6144 B`
- `stage27_store` worst observed HWM: `1884 B` free
- heartbeat count: `18`
- heap-integrity OK count: `3`
- telemetry rows retained: `18`
- storage records written: `20`
- loop max: `242265 us`
- queue drops: `0`
- storage write errors: `0`
- unexpected storage fallbacks: `0`
- no coredump, counter regression, Guru Meditation, corrupt heap, stack canary, or watchdog fault
- Shelly master ON, median power `64.80 W`
- final state `fake-locked`

## Serial-open reset behavior discovered during Phase G

A second short task and the first long-soak parser exposed a test-harness property: opening the USB-UART serial device resets this ESP32-S3/CrowPanel path.

This behavior is now documented permanently in:

`docs/ESP32_S3_SERIAL_PORT_RESET.md`

Key rule:

> Opening `/dev/cu.usbserial-1130` may reset the board before observation begins. Establish the runtime baseline only after the port is open, boot has stabilized, and a fresh status snapshot has been captured. Only reset/session/lifecycle changes after that post-open baseline are runtime failures.

The behavior was observed even when pyserial configured `DTR=False` and `RTS=False` before `open()`; therefore those settings alone are not proof of reset-free attachment on this exact board/adapter/driver path.

## G2 representative long soak

Original hardware task:

`20260907-growbox-stage28e-phase-g-long-soak-v1`

Observation wall time: `736.476 s`.

The original task result was formally `failed` because the parser rejected any `ESP-ROM:esp32s3-` marker anywhere in the serial capture. The serial-open reset occurred at the observation boundary, not later during the soak.

Read-only reset-position and evidence analysis:

- final firmware uptime: `733249 ms`
- wall time minus final uptime: `3.227 s`
- therefore the board restarted only at serial-open/startup and then ran continuously for more than 12 minutes
- stable boot ID after startup: `54f2ecb1`
- stable reset reason after startup: `1`
- no later boot/session restart is compatible with the final uptime being within only `3.227 s` of the wall-clock observation duration

Formal corrected long-soak reanalysis task:

`20260907-growbox-stage28e-phase-g-long-soak-reanalysis-v1`

Result: PASS.

Measured long-soak evidence:

- wall time: `736.476 s`
- final uptime: `733249 ms`
- startup reset gap: `3.227 s`
- boot ID: `54f2ecb1`
- reset reason: `1`
- internal free/min/largest: `223792 / 223260 / 180224 B`
- PSRAM free/largest: `8358772 / 8257536 B`
- main worst observed HWM: `7064 B` free
- `stage27_store` worst observed HWM: `1884 B` free
- maximum heartbeat sequence observed: `72`
- maximum heap-integrity check observed: `12`
- retained tail telemetry rows used in reanalysis: `24`
- retained storage records progressed `56 -> 83`
- loop max: `228148 us`
- BLE scanning healthy
- SCD41 samples healthy after startup
- TP and Xiaomi BLE samples healthy
- queue drops: `0`
- storage write errors: `0`
- unexpected storage fallbacks: `0`
- physical light/fan/humidifier remained `0`
- no coredump, `arbiter_counter_regression`, Guru Meditation, corrupt heap, stack canary, watchdog, or heap-integrity failure after the post-open baseline
- Shelly master ON, median power `65.10 W`
- state remained `fake-locked`

## Phase G conclusions

Phase G runtime evidence supports all intended Stage28E hardening goals:

1. The previously suspected internal-RAM crisis is not present under representative runtime load.
2. Phase E memory gains remain stable over the representative soak.
3. Main and storage task stacks retain large accepted margins; do not shrink them merely because this soak passed.
4. Heap integrity remained healthy.
5. Loop timing remained comfortably below the 1 s budget with zero observed overrun evidence.
6. BLE, SCD41, TP, Xiaomi and telemetry storage remained live.
7. Storage progressed without queue drops, write errors or unexpected fallback.
8. No same-instance arbiter counter regression was observed.
9. No unexplained runtime reconstruction, crash, coredump, watchdog or heap corruption was observed after the serial-open baseline.
10. Fake-locked safety remained intact and Shelly master stayed ON.

The two apparent Phase G failures were parser/harness false negatives, not firmware regressions:

- SCD41 first-sample warm-up was incorrectly required at `751 ms` uptime;
- serial-open reset was incorrectly classified as a spontaneous runtime reset.

Both conditions are now understood and documented so future gates can establish the correct post-open baseline.

## Phase G exit status

Runtime evidence is complete and PASS.

Before declaring Phase G formally complete, run one final exact-SHA read-only/software exit gate on the documentation HEAD that contains this handoff and the serial-open reset note. The exit gate must verify:

- exact work-branch HEAD and clean tree;
- this handoff and `docs/ESP32_S3_SERIAL_PORT_RESET.md` are present;
- short reanalysis result is PASS;
- long-soak reanalysis result is PASS;
- source/firmware SHA under runtime validation remains `389453882f0e0d2209c5bdece7eaf443895aa7ba`;
- no production runtime/control code changed between the validated firmware SHA and the Phase G documentation HEAD;
- `git diff --check` passes.

Only after that exact-SHA exit gate passes should documentation advance to **Phase H NEXT**.

Formal Phase G exit gate v2 passed at exact documentation SHA `7ddb995d1f6cd190fa110f21f0d8dc0eabc61d26`. Phase G is therefore formally COMPLETE and Phase H is NEXT.

## Phase H next

Phase H is the only remaining Stage28E phase.

It must run a bounded physical end-to-end path:

`AH/rule request -> binary arbiter -> RF -> physical fan`

Capture at minimum:

- exact SHA
- post-serial-open boot/session baseline
- request and arbiter pre-state
- dwell state/counters and arbiter instance ID
- transition decision
- RF transmit evidence
- physical fan state / independent physical evidence where available
- Shelly master state/power
- memory/stack/timing/safety evidence
- thermal safety state
- restoration to `fake-locked` after the bounded diagnostic

Do not bypass the existing thermal or manual-RF safety interlocks.
