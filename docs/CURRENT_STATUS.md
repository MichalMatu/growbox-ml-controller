# Current controller status

Date: 2026-08-28
Development branch: `mvp/environment-controller`
Fresh-chat bootstrap: `docs/CONTINUATION_PLAN.md`

This is the short source of truth for the current climate-controller product path. Historical
simulator, browser-contract and repository-convergence documents remain for reproducibility, but
they must not be read as the current climate runtime architecture.

## Authoritative climate path

Climate-v6 is the active migration target for new controller work:

- schema v6 / contract `climate-mvp-v1`;
- 44 runtime-observable input features;
- 6 semantic ML-controlled outputs: heater, cooler, exhaust fan, humidifier, dehumidifier and CO2 doser;
- bounded model shape `44 -> 32 -> 32 -> 6` retained for compatibility/research;
- Rule remains the authoritative runtime policy;
- `MlShadow` evaluates ML without changing the applied command;
- `MlActive` is an explicit research opt-in and is not qualified for real growbox actuation;
- deterministic arbitration and safety remain authoritative over every policy proposal;
- effective-actuator state advances only from the final applied semantic command.

The scientific rationale and rejected alternatives are frozen in `docs/ML_DECISION_REPORT.md`.

## Runtime implementation completed

The C++ climate-v6 runtime includes:

- `ClimateFeatureEncoder`;
- `ClimateRuntimeController` with Rule / ML_SHADOW / ML_ACTIVE modes;
- trend and effective-actuator state estimation;
- Python/C++ golden parity;
- validated trace schema and streaming NDJSON recording;
- deterministic trace replay and counterfactual ML evaluation;
- `ClimateControlLoop` with fail-closed input handling, best-effort OFF on actuator rejection and
  an actuator fault latch;
- multi-step virtual HIL tests covering state, stale/unavailable inputs, shadow ML, safety
  transitions and rejected actuator commands.

These sources compile in the real ESP-IDF ESP32-S3 firmware build. The local framework and CI
baseline are ESP-IDF v5.5.4.

## Hardware-neutral I/O seam

`src/climate/ClimateIoAdapters.*` is the application-side boundary for future hardware work. It
deliberately contains no SCD41, BLE, RTC, GPIO, relay, PWM or networking dependency.

`ClimateSnapshotProvider` supplies runtime-observable measurements/configuration. The input
adapter maps that snapshot to `ClimateInputSource`. `ClimateRoleDriver` accepts normalized
semantic role commands and the actuator adapter maps all six climate outputs to those roles.

`ClimateControlLoop` owns confirmed previous actions. `ClimateRuntimeController` owns trends and
estimated effective actions. Hardware providers must not duplicate those states.

Stage25A adds `ClimateApplication`, a deliberately small constructor-injected composition root around the existing input adapter, control loop and actuator adapter. Host tests now exercise the complete `ClimateSnapshotProvider -> ClimateInputAdapter -> ClimateControlLoop -> ClimateActuatorAdapter -> ClimateRoleDriver` path across multiple ticks, including stale/invalid/unavailable input, ML shadow isolation, rejected commands with OFF recovery, fault latching/reset, confirmed applied feedback and all six semantic actuator roles. Fake providers and drivers remain test-only implementations of the same public interfaces intended for future hardware.

Stage25B adds an explicit build-time application boundary. `GROWBOX_APP_MODE` defaults to `legacy`, while `climate-v6-fake` selects a hardware-neutral climate-v6 runtime backed by a fixed fake snapshot provider and an accept-all fake role driver. The climate-v6 fake runtime emits startup/status identity (`application`, policy mode, input backend and output backend) and never touches GPIO or physical loads. Both application modes are required to compile in the ESP-IDF v5.5.4 gate.

Stage25C replaces the fixed smoke snapshot with `DeterministicClimateScenarioProvider`, a hardware-neutral provider whose output is a pure function of monotonic time. Its 240-tick cycle varies inside/outside T/RH/CO2, day/night targets and light schedule plus actuator capabilities. Host tests prove timestamp determinism, cycle periodicity and a 1,200-tick full `ClimateApplication` run with fake outputs. Fault injection remains intentionally reserved for Stage25E.

## Not integrated yet

`src/main.cpp` still runs the preserved legacy simulator/serial demonstration through the older
`EnvironmentController`. Climate-v6 is compiled and host/HIL tested but is not yet the default
`app_main()` execution path and does not drive physical loads.

Planned first hardware set remains:

- inside: SCD41 for air temperature, RH and CO2;
- outside: external BLE temperature/RH sensor, exact model not frozen;
- system time: backed-up hardware RTC, exact part not frozen;
- physical actuator endpoints: not frozen yet.

See `docs/MVP_HARDWARE_SENSOR_SET.md`.

## Next steps

The detailed fresh-context plan is in `docs/CONTINUATION_PLAN.md`.

1. Prove the strict IPO composition with interchangeable fake Input/Output implementations using
   the same public interfaces intended for future hardware.
2. Keep the legacy demo intact while proving the new climate-v6 application composition path.
3. Add concrete SCD41 / BLE / RTC providers only after parts and libraries are frozen.
4. Add concrete semantic actuator-role drivers.
5. Bring up real hardware in Rule mode first.
6. Run ML only in `MlShadow` while collecting real traces.
7. Re-qualify ML from real data before considering active ML actuation.
