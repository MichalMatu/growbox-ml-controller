# Architecture

Current status: [CURRENT_STATUS.md](CURRENT_STATUS.md).
Product roadmap: [PROJECT_ROADMAP.md](PROJECT_ROADMAP.md).
Output execution design: [OUTPUT_EXECUTION_ARCHITECTURE.md](OUTPUT_EXECUTION_ARCHITECTURE.md).

## Design rules

The portable climate controller is independent from concrete sensor libraries and physical actuator transports. Hardware code produces semantic measurements and consumes semantic output intent through explicit application/runtime boundaries.

Normal configured physical output execution has one owner: `OutputSupervisor`.

Production deterministic Rule control remains authoritative. ML may be evaluated for shadow/research purposes but production composition does not enable unqualified ML authority.

## Production real-input path

```text
native sensor / RTC / schedule sources
               |
               v
     ClimateApplication / climate-v6
               |
        ControlIntent + ScheduleIntent
               |
               +----------------------+
               |                      |
               v                      v
       Lamp SafetyEnvelope      manual/maintenance lifecycle
               |                      |
               +----------+-----------+
                          v
                  OutputSupervisor
              resolver + binary policy
                          |
                          v
                 OutputPlan / command
                          |
                          v
               RuntimeOutputTransport
                          |
                          v
                 RF433OutputTransport
```

One-way RF transport completion is command/transport evidence only; it is never treated as physical acknowledgement.

## Runtime composition

The real-input runtime is deliberately split by responsibility:

- `ClimateV6RealInputRuntime.cpp` — thin bootstrap: initialize, validate, enter the loop;
- `runtime/RealInputRuntimeComposition.*` — construction, ownership and lifetime wiring;
- `runtime/RealInputRuntimeCoordinator.*` — one-cycle orchestration;
- `runtime/RuntimeCycleState.*` — bounded cycle sequencing/cadence state;
- `runtime/RuntimeOutputTransport.*` — physical transport availability/truth boundary;
- `runtime/RuntimeOutputTelemetryLog.*` — output telemetry formatting/logging;
- `runtime/Stage27RuntimeAdapters.*` — Stage27 source adapters and production runtime policy configuration;
- `runtime/Stage27TelemetryReporter.*` — telemetry snapshot/storage reporting;
- `runtime/Stage28RfDiagnostics.*` — RF diagnostics/passive capture;
- `runtime/Stage28ServiceConsole*` — thin console IO/router plus output/storage/system domain handlers.

The coordinator receives grouped input/output/support service bundles rather than a flat service-locator-like dependency bag.

Invalid lifecycle/automation/maintenance reports fail closed by disabling physical transport readiness for the cycle rather than being silently discarded.

## Output truth model

Requested, resolved, attempted/executed transport state and independently observed physical state are distinct concepts.

When physical transport is unavailable, `RuntimeOutputTransport` returns `NotAttempted` with `Unavailable`. It must not return `Completed`, because doing so would manufacture execution truth in `OutputStateStore`/projection.

`OutputSupervisor` owns normal configured output commands. Raw RF remains an explicit maintenance capability behind `MaintenanceLocked`.

## Policy and safety ownership

- climate rule logic owns environmental control decisions;
- `BinaryActuatorPolicy` owns binary hysteresis/deadband/dwell behavior;
- Stage28 output bindings own endpoint/policy mapping;
- lamp thermal safety owns the frozen `>=28 C` trip and `<=26 C` for 10 minutes recovery contract;
- transport layers do not own climate policy;
- maintenance diagnostics do not become a hidden normal-output path.

The retired Stage28D thermal test-sequence helper is no longer part of production source; historical qualification evidence remains in Git history/docs.

## Configuration source of truth

Resolved runtime/build configuration is owned by CMake profiles under `config/` and exposed to production C++ through generated `runtime/RuntimeBuildConfig.h`.

Production C++ must not reintroduce fallback `GROWBOX_*` default tables. Preprocessor definitions are retained only for switches that genuinely require compile-time preprocessing.

Architecture/config guards enforce these boundaries.

## Climate-v6 controller core

`schemas/environment-controller.v6.json` and generated `ClimateContract.h` define the climate-v6 contract. The portable core lives under `lib/environment_control/src/climate/` and contains feature encoding, runtime rule/ML evaluation, trend estimation and the control loop.

Policy modes exist in the portable research-capable core, but production real-input composition is statically configured for `Rule` authority with unqualified ML active control disabled.

## Legacy isolation

Legacy controller/demo code remains available only through the explicit `legacy` app mode. Production V6 targets do not compile the legacy controller ownership path by default.

`src/main.cpp` is a small app-mode dispatcher; it no longer contains the legacy controller implementation or production control orchestration.

## Verification layers

- architecture/config ownership guards;
- focused portable regression tests;
- complete host C++ suite;
- Python scientific/replay tests where applicable;
- ESP-IDF production builds;
- hardware qualification only when a fresh physical executable claim is required.

Latest compact refactor verification on `1a599a58eb57841206ab92c7a5cacf50f7463f78` passed all guards, the focused runtime transport regression, `51/51` host tests and one CrowPanel real-input ESP-IDF build.

Simulator/host/firmware-build PASS is software evidence, not physical acknowledgement or a new Physical H qualification.
