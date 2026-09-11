# Environment Controller MVP

Status: implementation phase — climate-v6 simulation/training path qualified through Stage 16; hardware runtime integration remains in progress
Branch: `mvp/environment-controller`

## 1. Product goal

Build a standalone, hardware-independent environment controller for a typical indoor growbox.

This project owns its own control model, simulation/training path, runtime contract and future embedded implementation. It is not an extension, plugin, ML node or control layer for `esp32s3_LiteGraph`.

Hardware choices do not define the core. ESP32-S3, display, encoder, GPIO, relay boards, BLE, MQTT, Shelly, Modbus and sensor models are adapters around the core.

The first MVP must be deliberately small and climate-only. The goal is a reliable base that can later be extended without redesigning the climate controller.

## 2. Frozen MVP v1 architecture

The core follows IPO separation:

```text
MEASUREMENTS + SYSTEM TIME + CONFIGURATION
                    |
                    v
             EnvironmentState
                    |
                    v
PROCESSING
ControlPolicy
                    |
                    v
ARBITRATION
                    |
                    v
SAFETY SUPERVISOR
                    |
                    v
OUTPUT
semantic device-role commands
```

Rules:

- measurements describe semantic values, never hardware sources;
- current time is system context, not a physical sensor;
- schedule state is derived from current time and configuration;
- VPD is derived inside the core from air temperature and relative humidity;
- processing never directly controls GPIO or a specific device;
- outputs describe device roles, never physical endpoints;
- hardware adapters exist only outside the core;
- `SafetySupervisor` remains independent from the control policy;
- `RuleControlPolicy` is the deterministic reference/fallback policy;
- `MlControlPolicy` may replace only the climate decision policy, never safety, scheduling or hardware adaptation.

## 3. Frozen INPUT contract

Required semantic measurements:

- `air_temperature_c`
- `relative_humidity_pct`

Optional semantic measurements:

- `co2_ppm`
- `outside_temperature_c`
- `outside_humidity_pct`

Every measured value must carry measurement state separately from its numeric value:

- `valid`
- freshness / `age_ms`

System context:

- `current_time`

Derived environment values:

- `air_vpd_kpa`
- optionally `outside_vpd_kpa` when outside temperature and humidity are valid

`light_schedule_active` is not a physical input. It is derived from `current_time` and `light_schedule`.

For MVP v1, VPD is calculated from air temperature and relative humidity only. Leaf temperature and leaf VPD are intentionally outside the MVP to keep hardware, simulation and model training simpler.

CO2 is optional. A basic growbox controller must remain fully functional for temperature, humidity/VPD, ventilation and lighting without a CO2 sensor.

A missing or invalid measurement must never be represented by a fake numeric value such as zero.

The core does not know whether a value came from I2C, BLE, MQTT, Modbus, REST, a simulator or a recorded dataset.

## 4. Frozen user configuration

Light schedule:

- `light_on_time`
- `light_off_time`

Day targets:

- `day_temperature_c`
- `day_humidity_pct`
- `day_vpd_kpa`
- `day_humidity_control_mode = RH | VPD`
- `day_co2_enabled`
- `day_co2_ppm` when CO2 control is enabled
- `day_light_level = 0..1`

Night targets:

- `night_temperature_c`
- `night_humidity_pct`
- `night_vpd_kpa`
- `night_humidity_control_mode = RH | VPD`
- `night_co2_enabled = false` by default
- `night_co2_ppm` only when explicitly enabled
- `night_light_level = 0.0` by default

The active target profile is derived from current time and the light schedule.

RH and VPD are coupled quantities, so the controller must not independently regulate both at the same time. Each DAY/NIGHT profile selects one humidity-control mode:

```text
RH mode  -> relative_humidity_pct is the controlled humidity target
VPD mode -> air_vpd_kpa is the controlled humidity target
```

The non-selected value remains calculated and visible for monitoring and diagnostics.

Temperature always remains an independent target. A correct VPD does not make an incorrect air temperature acceptable.

Control tuning:

- `temperature_deadband_c`
- `humidity_deadband_pct`
- `vpd_deadband_kpa`
- `co2_deadband_ppm`
- `minimum_ventilation`

Safety limits:

- `max_temperature_c`
- `min_temperature_c`
- `max_humidity_pct`
- `max_co2_ppm`
- `max_co2_dosing_time`
- `sensor_timeout`
- actuator-specific minimum ON/OFF times where required

Capabilities/configuration also describe which functions are available and which abstract endpoints are assigned to which output roles.

## 5. Frozen product OUTPUT roles

MVP v1 product roles:

- `heater`
- `cooler`
- `exhaust_fan`
- `circulation_fan`
- `humidifier`
- `dehumidifier`
- `co2_doser`
- `light`

Internal commands use normalized values:

```text
0.0 = off / minimum request
1.0 = full request
```

This applies even when the physical device is binary. The output adapter decides how a normalized command maps to relay ON/OFF, PWM, VFD, Shelly, Modbus or another implementation.

Conceptually:

```text
ControlRequests {
  heater: 0..1
  cooler: 0..1
  exhaust_fan: 0..1
  circulation_fan: 0..1
  humidifier: 0..1
  dehumidifier: 0..1
  co2_doser: 0..1
  light: 0..1
}
```

Each bound actuator may also declare configurable operating limits:

```text
ActuatorLimits {
  min_level: 0..1
  max_level: 0..1
}
```

`None` means that no physical endpoint is bound to a role. `Generic` is not a climate-control role.

## 6. Output binding

The core controls semantic roles. A separate mapping connects roles to abstract output endpoints.

Example:

```text
Endpoint A -> Light
Endpoint B -> ExhaustFan
Endpoint C -> Heater
Endpoint D -> Humidifier
Endpoint E -> Co2Doser
Endpoint F -> None
```

Only an adapter knows what an endpoint physically is.

Possible adapters later:

- GPIO relay
- SSR
- PWM
- Shelly
- Modbus VFD
- MQTT-controlled output

## 7. Frozen policy boundary

The product has eight device roles, but the first ML policy must not control all eight.

`MlControlPolicy` v1 controls exactly these six climate requests:

```text
heater
cooler
exhaust_fan
humidifier
dehumidifier
co2_doser
```

The following remain outside ML v1:

```text
light           -> schedule/configuration, with SafetySupervisor emergency override
circulation_fan -> deterministic configured/baseline policy
```

Reasons:

- ML must not discover that turning the grow light off is an easy way to reduce temperature;
- in a one-zone well-mixed climate model, circulation fan benefit is not sufficiently observable from only T/RH/CO2 to justify an ML output;
- scheduling and safety must remain deterministic and explainable.

`RuleControlPolicy`, teacher policy and `MlControlPolicy` use the same climate state and are benchmarked against each other. Safety remains authoritative after all of them.

## 8. Safety and arbitration

Safety is authoritative and remains outside ML/rule policy.

Minimum responsibilities:

- heater and cooler cannot fight each other;
- humidifier and dehumidifier cannot fight each other;
- CO2 dosing is disabled when CO2 control is not configured;
- CO2 dosing is disabled with lights off unless explicitly supported later;
- CO2 dosing is disabled for missing, invalid or stale CO2 measurement;
- CO2 dosing may be inhibited during strong exhaust ventilation;
- stale/invalid required measurements produce safe behavior;
- VPD control is unavailable when temperature or humidity is invalid/stale;
- actuator commands are clamped to configured min/max capability;
- minimum ON/OFF time and maximum run time can be enforced where needed;
- shared demands are resolved deterministically;
- configured hard safety limits override controller requests;
- model failure, incompatible model contract or non-finite ML output must never bypass deterministic safety.

The system must expose reasons for overrides and resulting actions.

## 9. Fan behavior

`exhaust_fan` and `circulation_fan` are separate roles.

`exhaust_fan` exchanges growbox air with outside air and may be requested for:

- temperature removal;
- humidity/VPD correction;
- baseline air exchange;
- safety.

Individual climate loops do not directly own the exhaust fan. They produce demands and arbitration combines them into the final request.

`minimum_ventilation` together with actuator `min_level` allows the exhaust fan to run continuously at a low baseline and increase only when climate control requires it.

`circulation_fan` represents internal air movement and must not be modeled as outside-air exchange. In MVP v1 its command is deterministic/configured rather than an ML decision.

## 10. Missing capability behavior

Missing hardware is not itself an error.

Examples:

- temperature measurement available, heater absent -> monitor only / use other available strategies;
- humidity measurement absent, humidifier present -> no automatic RH or VPD control;
- temperature or humidity invalid -> calculated air VPD invalid;
- CO2 measurement absent -> temperature/RH/VPD/light control continues normally and automatic CO2 dosing stays disabled;
- CO2 measurement available, doser absent -> monitor only;
- cooler absent -> cooling may use exhaust if available and allowed.

Availability is explicit and never inferred from numeric measurements.

## 11. Configuration and status model

Conceptually:

```text
ControllerConfig
├── light_schedule
├── day_targets
├── night_targets
├── humidity_control_mode
├── control_tuning
├── enabled_functions
├── output_bindings
├── actuator_limits
└── safety_limits
```

The core publishes status independently of any UI:

```text
ControllerStatus
├── environment
│   ├── temperature
│   ├── relative_humidity
│   ├── air_vpd
│   └── co2 [optional]
├── current_time
├── active_profile (DAY/NIGHT)
├── active_targets
├── requested_actions
├── final_safe_actions
├── output_bindings
├── active_interlocks
└── reasons / diagnostics
```

OLED, web UI, app or API are only views/editors of this model.

## 12. MVP v1 boundary

Included:

- temperature control;
- humidity control by RH or calculated air VPD;
- air VPD calculation and monitoring;
- optional CO2 monitoring/control;
- day/night targets;
- light schedule and normalized light level;
- exhaust and circulation fan product roles;
- configurable actuator min/max levels;
- hardware-independent input/output mapping;
- deterministic reference policy;
- ML climate policy with six outputs;
- safety/arbitration;
- status/reason reporting.

Explicitly not included in climate MVP v1:

- leaf-temperature sensing or leaf VPD;
- any pot/donica model;
- irrigation;
- soil moisture;
- soil/root temperature control;
- heat mats;
- nutrient tank control;
- EC;
- pH;
- PPFD;
- multiple climate zones;
- final hardware drivers/UI;
- LiteGraph/Nodeflow integration.

Do not keep dummy/placeholder pot features in the ML contract. Future plant/irrigation support must be added as a separate module instead of bloating the climate model.

## 13. Frozen rebuild order

Work only on the existing `mvp/environment-controller` branch. Do not create another migration branch and do not modify `main`.

The active code on this branch still contains the old v4 4-pot / 15-output pipeline. It is the migration source, not the target architecture.

Rebuild in this order:

0. Capture baseline before code changes.
1. Define climate-only contract/schema v6.
2. Define the minimal controller input/state and trend calculation.
3. Adapt the existing simulator to the climate-only contract.
4. Add physics/regression tests and deterministic replay.
5. Rebuild the rollout teacher for the new contract.
6. Generate data and run dataset audit gates.
7. Train small candidate models only after dataset audit passes.
8. Run closed-loop benchmarks: rule vs teacher vs ML.
9. Export to ESP32 only after the closed-loop acceptance gates pass.
10. Remove obsolete v4-only code only after the replacement path is green.

Do not combine unrelated stages in one large change. Each stage should be reviewable and revertible.

## 14. Decisions intentionally postponed

Do not choose yet:

- exact final ESP32 board revision;
- display or encoder;
- GPIO/relay/SSR hardware;
- MQTT/BLE/Modbus details;
- final UI layout;
- final MLP architecture/optimizer/loss;
- future irrigation/plant architecture details beyond its boundary from climate MVP.

Those choices must adapt to the controller contract, not define it.

## 15. Project boundary

`growbox-ml-controller` and `esp32s3_LiteGraph` remain separate projects.

For this MVP:

- no ML node is added to LiteGraph;
- no LiteGraph graph analysis is required by the growbox controller;
- no shared runtime or control loop is introduced;
- no dependency on Nodeflow contracts is allowed in the controller core;
- any future interoperability must happen through a generic external adapter/API and must not couple either project's internal architecture.

This boundary is intentional: the growbox project must be able to prove or disprove the value of ML on its own, with its own simulator, benchmark and observable controller behavior.

## Current implementation checkpoint — 2026-08-28

The rebuild has progressed beyond the original planning checkpoint:

- climate-v6 uses 44 ordered ML features and 6 climate outputs;
- Sequence Teacher is qualified for new labels;
- effective actuator observability is implemented;
- Rule remains the recommended authoritative runtime policy;
- residual ML and deterministic CO2/exhaust coupling were rejected on DEV evidence;
- one bounded Sequence-Teacher DAgger iteration failed the switching gate on two DEV seeds, so no second iteration or candidate publication is planned;
- next work is runtime policy-mode/shadow diagnostics, trace/replay, parity, and simulated/HIL preparation before real sensors.

See `docs/ML_DECISION_REPORT.md` for the frozen evidence and seed hygiene.

# Frozen implementation plan

The following sections are the implementation checkpoint for the MVP rebuild. They exist so later work can resume without reconstructing decisions from chat history.

## 16. Baseline and regression strategy

Before changing the old v4 code locally:

- record the branch HEAD;
- run the existing test suite and record pass/fail status;
- save several deterministic simulator traces using fixed scenario seeds and commands;
- record the active v4 contract hash, feature count and output count;
- do not treat the previously trained v4 model as an acceptance benchmark because its closed-loop behavior was not satisfactory.

During migration:

- keep commits small and stage-specific;
- run focused tests after each code stage and the complete relevant suite at milestones;
- preserve deterministic seeds;
- use tolerances for floating-point golden traces rather than fragile byte equality;
- do not delete old v4-only implementation pieces until the climate-only replacement is green.

A change to physics must be distinguishable from a change to teacher, dataset generation or training. Avoid changing all of them in one commit because improvements/regressions would become impossible to attribute.

## 17. Product contract vs ML model contract

These are deliberately different concepts.

Product contract:

```text
8 semantic device roles
controller configuration
status
safety
hardware-independent bindings
```

ML contract v1:

```text
minimal feature vector required for climate decisions
6 ML outputs only
strict feature/output ordering
version + schema hash
```

Do not add unused future sensors to the ML vector. Adding a future sensor or plant module is allowed to create a new model-contract version; it must not force unrelated product APIs to change.

Every exported model must be tied to its exact ML contract by schema hash/version. Runtime must reject a model whose feature/output contract does not match the firmware contract.

Recommended model metadata to preserve with every trained artifact:

- contract version/hash;
- feature names in exact order;
- output names in exact order;
- git commit of simulator/training code;
- dataset generator configuration and seed;
- training configuration and seed;
- closed-loop benchmark summary.

## 18. Frozen ML v1 feature semantics

The exact JSON ordering is defined when schema v6 is implemented, but the semantic content is frozen here.

### Direct measurements available to ML

- inside `air_temperature_c`;
- inside `relative_humidity_pct`;
- inside `co2_ppm` when valid;
- outside `outside_temperature_c` when valid;
- outside `outside_humidity_pct` when valid;
- validity/freshness information required to distinguish missing/stale values from real measurements.

There is no outside CO2 sensor in the hardware MVP. Outside CO2 may exist as an internal simulator boundary condition, but it must not appear as a measured ML feature.

### Derived values available to ML

- `air_vpd_kpa`;
- active humidity control mode `RH | VPD`;
- active temperature target;
- active RH target and/or active VPD target with the mode telling the policy which one is authoritative;
- CO2 enabled state and active CO2 target when configured;
- scheduled `light_level 0..1` as a disturbance/context value;
- active DAY/NIGHT profile if useful for diagnostics/contract clarity.

The ML policy does not need raw wall-clock timestamp merely because the controller owns an RTC. Scheduling is deterministic outside ML. Prefer derived active profile/targets/light level over teaching the network calendar semantics.

### Dynamic/trend values

A static measurement alone cannot distinguish a rising process from a falling process at the same value. ML v1 therefore receives deterministic trend estimates:

- `temperature_rate_c_min`;
- `humidity_rate_pct_min`;
- `co2_rate_ppm_min` when CO2 is valid.

Implemented v6 semantics: a deterministic 60-second least-squares trend window. Fresh valid source samples are retained at approximately 5-second spacing, at most 16 samples per channel, and no trend is exposed until at least 10 seconds of source-time span exists. Repeated faster samples are ignored until the 5-second source-time spacing is reached. Invalid/stale measurements suppress the corresponding trend, and monotonic-clock rollback resets trend history. These rules are contractual for v6 and must be mirrored by simulation/training.

### Previous actions

ML receives previous effective/requested climate commands as needed to interpret trends and actuator inertia:

- previous heater;
- previous cooler;
- previous exhaust fan;
- previous humidifier;
- previous dehumidifier;
- previous CO2 doser.

### Capabilities

ML may receive availability flags and stable normalized command limits that are actually known by runtime.

Do not automatically expose simulator-only physical truth such as exact thermal mass, heat-loss coefficient or hidden leakage merely because the simulator knows it. A feature belongs in ML only if the real controller can reliably know the same value.

Calibrated physical-response features may be introduced in a later contract only when the embedded runtime has a reliable way to obtain them.

## 19. Simulator rebuild rules

Preserve and reuse the useful climate physics already in the repository rather than rewriting it without evidence.

Initial protected physics modules:

- `tools/ml/physics/van_henten.py`;
- `tools/ml/physics/psychrometrics.py`.

They may be corrected later if a test or calibration demonstrates a problem, but climate-MVP migration must first adapt around them.

The active climate simulator must remove all pot/nutrient/irrigation dependencies from its state, actions and dataset path.

### Exhaust fan

Old `fan` semantics become `exhaust_fan`.

The exhaust fan causes outside-air exchange and therefore couples simultaneously to:

- inside temperature vs outside temperature;
- inside humidity vs outside humidity;
- inside CO2 vs outside/background CO2.

Fan forcing must remain based on physically meaningful exchange/ACH behavior.

### Circulation fan

Do not map `circulation_fan` onto outside-air exchange.

For the first well-mixed single-zone simulator it may have no explicit climate-state effect. Its product command remains deterministic/configured. A future model may add mixing/plant-level physics if measurements justify it.

### Light

Replace boolean-only `lights_active` physics with normalized:

```text
light_level = 0..1
```

The simulator maps light level to at least:

- lamp heat load;
- radiation/light disturbance used by the crop/climate backbone.

ML receives light level as context but cannot command it in v1. Safety may override the scheduled light only for hard safety behavior.

### CO2

Remove the old possibility of double-counting CO2 through both continuous Van Henten input and an additional per-step ppm pulse.

MVP semantics:

```text
co2_doser command 0..1
    -> one configured physical/equivalent maximum dosing rate
    -> integrated continuously over dt
```

There must be exactly one CO2 injection path in the climate equations.

Changing simulator timestep must not change the physical dose for the same command over the same elapsed real/simulated time. The simulator therefore needs explicit timestep-invariance tests for CO2.

Physical hardware may implement a normalized average request using valve pulses/duty cycles, but that conversion belongs to the hardware adapter, not the climate policy.

## 20. Physics acceptance tests before dataset generation

Do not generate a training dataset until these checks pass.

Required direction/sanity tests include:

- heater ON increases temperature relative to the matching no-heater case;
- cooler ON decreases temperature relative to the matching no-cooler case;
- humidifier increases moisture/RH relative to baseline;
- dehumidifier decreases moisture/RH relative to baseline;
- exhaust moves indoor temperature toward outside temperature;
- exhaust moves indoor humidity toward the outside humidity boundary;
- exhaust dilutes/enriches indoor CO2 toward the simulator outside/background CO2 boundary;
- CO2 dosing increases indoor CO2 when allowed;
- stronger scheduled light level increases the modeled heat/radiation load;
- changing integration timestep within supported bounds produces materially equivalent trajectories for the same elapsed time;
- no NaN/Inf is produced for supported scenarios;
- physical clamps are not hiding routine unstable dynamics;
- deterministic scenario + seed + commands reproduce the same trajectory within floating-point tolerance.

Tests must compare controlled pairs/scenarios, not rely only on absolute magic numbers.

## 21. Scenario generation and domain randomization

Do not repeat the old pattern of relying mainly on a very broad independent uniform randomization of every physical parameter. That can create unrealistic parameter combinations and make the policy learn an unnecessarily ambiguous plant.

The climate dataset must combine:

1. structured scenario families that deliberately exercise each control problem;
2. realistic randomization inside those families;
3. correlated physical parameters where appropriate;
4. held-out scenario families/parameter combinations for generalization tests.

Required scenario coverage includes at least:

- cold outside / heating demand;
- hot outside / cooling or exhaust demand;
- dry outside / humidification demand;
- humid outside / dehumidification or ventilation trade-off;
- day with lamp heat load;
- night transition;
- DAY -> NIGHT and NIGHT -> DAY target transitions;
- elevated/low CO2 with dosing available;
- CO2 control unavailable;
- actuator-missing cases;
- temporary invalid/stale sensor cases;
- disturbances while the current measurement is near target but moving quickly;
- cases where outside air helps control;
- cases where outside air makes the controlled variable worse.

Prefer randomizing physically meaningful response behavior such as ACH, thermal time constants and effective actuator strength within realistic families over independently combining implausible extremes.

## 22. Teacher rebuild

The old rollout teacher used a horizon that was too short relative to actuator lags. The new teacher must evaluate consequences over a meaningful climate horizon.

Default planning principle:

```text
teacher horizon >= roughly 3 x the longest important configured actuator response time
```

A practical initial horizon may be several simulated minutes (for example around 300 s), with performance optimizations allowed as long as the effective horizon is preserved.

Teacher candidate generation must not intentionally include impossible/opposing combinations merely to penalize them later.

Do not generate candidates with:

- heater and cooler simultaneously active;
- humidifier and dehumidifier simultaneously active.

CO2/exhaust conflicts should be handled by explicit policy/arbitration rules and cost/safety appropriate to the scenario.

Teacher objective must evaluate only the active humidity-control objective:

- RH error in RH mode;
- air-VPD error in VPD mode;

while temperature remains independently controlled in both modes.

Teacher cost should also account for:

- temperature tracking;
- optional CO2 tracking when enabled/valid;
- actuator use/energy proxy;
- excessive switching;
- safety/constraint violations;
- terminal/future error strongly enough to avoid shortsighted labels.

The teacher is a label generator/reference, not embedded safety.

## 23. Dataset audit gate

Training is forbidden until a deterministic dataset audit reports acceptable coverage.

At minimum report for each ML output:

- min/max/mean;
- percentiles or histogram;
- OFF/active fraction for binary-like outputs;
- saturation near 0 and 1;
- transition/switch frequency;
- per-scenario-family coverage.

Also report:

- feature min/max/percentiles;
- invalid/stale feature frequency;
- target distributions;
- DAY/NIGHT and RH/VPD mode coverage;
- correlations that reveal accidental leakage or redundant constants;
- split sizes and scenario-family representation.

If an important output is almost always OFF/ON or important state regions are missing, fix scenario generation/teacher first. Do not compensate for a bad dataset only by changing loss weights.

Train/validation/test must continue to split by complete scenarios, not individual adjacent rows, to avoid leakage from the same trajectory.

## 24. Training strategy

Keep the first model intentionally small and embedded-friendly. A compact MLP remains the starting architecture unless evidence shows it is inadequate.

Do not change simulator physics, teacher logic, dataset generation and neural optimizer/loss simultaneously.

After dataset/teacher validation, compare training choices reproducibly, for example:

- current SGD baseline vs Adam;
- MSE vs Huber or another justified loss;
- modest hidden-layer sizes.

Training requirements:

- deterministic/repeatable seeds where supported;
- no tuning against the test set;
- per-output metrics retained for diagnostics;
- model size/parameter count recorded;
- exact contract hash stored with the artifact.

Open-loop label MAE/RMSE is diagnostic only. It is not the main product acceptance metric.

## 25. Closed-loop acceptance benchmark

The primary question is not "does ML imitate teacher labels?" but "does it control the simulated environment well over time?"

Benchmark the same held-out scenarios with:

```text
RuleControlPolicy
Teacher/reference policy
MlControlPolicy
```

Run long closed-loop simulations and report at least:

- time outside target/deadband;
- temperature absolute error;
- RH error in RH mode;
- VPD error in VPD mode;
- CO2 error when enabled;
- overshoot and undershoot;
- actuator switching count/rate;
- heater/cooler/exhaust runtime or energy proxy;
- humidifier/dehumidifier use;
- CO2 consumption proxy;
- number and reason of SafetySupervisor interventions;
- stability after DAY/NIGHT transitions and disturbances.

ML is accepted only if it is stable and provides a measurable benefit or acceptable trade-off against the deterministic baseline. A low neural-network validation loss alone is insufficient.

## 26. Future plant/irrigation extension boundary

Do not reintroduce pot placeholders into climate MVP.

Future plant control should be architected as a separate module, conceptually:

```text
ClimateController
        +
Plant/IrrigationController
        +
Coordinator / Safety
```

A later plant module may own inputs such as:

- soil moisture;
- root-zone/soil temperature;
- EC/pH;
- irrigation history;
- leaf temperature;
- PPFD.

and outputs such as:

- irrigation;
- heat mat;
- nutrient dosing.

Adding that module must not require adding its entire state vector to the proven climate ML policy. Climate will already observe many plant effects indirectly through measured T/RH/CO2. Cross-module coordination should be explicit and minimal rather than silently coupling all inputs into one large neural network.

If later evidence proves a plant variable materially improves climate control, add it through a deliberate new ML contract/version and benchmark the gain.

## 27. Migration cleanup rule

The old v4 branch content currently contains 4-pot, irrigation, nutrient-heater and 15-output assumptions. During the rebuild these may remain temporarily as migration code, but the final climate-MVP active path must not depend on them.

Only after contract v6, climate simulator, teacher, dataset audit and closed-loop benchmark are green should obsolete v4-only code/tests/schema pieces be deleted or archived.

The final result should have one obvious active climate pipeline rather than two competing implementations.

## 28. Stop conditions / anti-pitfall rules

Stop and fix the preceding layer before continuing when any of these occur:

- schema/feature/output ordering is ambiguous;
- runtime and training calculate a derived feature differently;
- simulator requires an ML input that real hardware cannot know;
- CO2 or another actuator response changes materially only because timestep changed;
- dataset output distribution is severely imbalanced without a physical reason;
- teacher chooses contradictory actions;
- model looks good in MAE but loses to the rule controller in closed loop;
- hard clamps routinely prevent simulator divergence;
- a future feature is being added only "in case we need it later";
- a refactor mixes physics, teacher, dataset and trainer changes so regressions cannot be attributed.

When in doubt, prefer a smaller observable model and an explicit future version over speculative complexity in MVP v1.
