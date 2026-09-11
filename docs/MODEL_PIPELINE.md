# Model pipeline

Status: climate-v6 research path qualified through Stage 16; Rule policy remains the recommended runtime authority until a later ML acceptance gate.

The active climate path is hardware-independent and keeps policy selection separate from arbitration and `SafetySupervisor`. The current ML contract has 44 ordered input features and 6 climate outputs. Light and circulation fan remain deterministic product behavior outside ML v1.

## Active architecture

```text
EnvironmentState + targets + measurement status
                |
                v
      climate-v6 feature encoder (44)
                |
        +-------+-------+
        |               |
        v               v
ClimateRulePolicy   ML candidate / shadow
        |               |
        +-------+-------+
                |
                v
           arbitration
                |
                v
        SafetySupervisor
                |
                v
        applied safe action
                |
                v
 effective-actuator estimator
```

The six ML outputs are:

- `heater`
- `cooler`
- `exhaust_fan`
- `humidifier`
- `dehumidifier`
- `co2_doser`

The six Stage-13 effective-state features are the estimated applied states for the same actuators. They are advanced from the safe/applied semantic command after each interval, never from raw ML output.

## Current model shape

The bounded MLP remains:

```text
44 -> 32 -> 32 -> 6
```

with 2,694 trainable parameters. Stage 11 showed that widening to 64 hidden units worsened closed-loop behavior, so width expansion is not an active optimization direction.

`reports/ml/climate_v6_model_stage13_compat.*` is the compatibility artifact for the Stage-13 feature contract. It preserves the earlier model exactly by inserting the six effective-state inputs with zero first-layer weights; it was not retrained on the new features.

## Teacher and data policy

The old single-step/repeated-action rollout teacher is retained only for compatibility. New labels must use the stronger Sequence Teacher explicitly. `tools/ml/climate_dagger.py` therefore keeps `teacher_kind="rollout"` as the legacy default but supports explicit `teacher_kind="sequence"`; no new experiment may silently generate old-Teacher data.

Sequence Teacher uses a 300 s receding-horizon plan and was qualified on untouched Stage-12 final evaluation before later research stages.

## Acceptance history

The authoritative detailed record is [ML_DECISION_REPORT.md](ML_DECISION_REPORT.md). Current decisions are:

- Stage 12: Sequence Teacher qualified.
- Stage 13: effective actuator observability implemented and fully verified.
- Stage 14: bounded residual ML rejected; tracking gains were too small relative to switching cost.
- Stage 15: deterministic CO2/exhaust coupling edits rejected on representative DEV.
- Stage 16: one bounded Sequence-Teacher DAgger iteration improved the current ML candidate on DEV but failed the switching gate on two DEV seeds and remained worse than Rule. No second DAgger iteration and no candidate publication.

## Runtime direction

The next runtime work is deliberately product-oriented rather than another training sweep:

1. keep `ClimateRulePolicy` authoritative;
2. add explicit `Rule`, `MlShadow`, and gated `MlActive` policy modes;
3. allow shadow ML to produce diagnostics without affecting actuators;
4. record deterministic controller traces containing measurements, targets, encoded features, Rule request, ML-shadow request, arbitration, safety reasons, applied action, and effective-state estimate;
5. add replay and Python/C++ parity before real-sensor integration;
6. calibrate simulator dynamics from hardware later, then reconsider ML architecture only with new evidence.

## Verification rule

Closed-loop behavior is the primary model gate. Offline MAE/F1 may diagnose training, but they do not qualify a controller. `SafetySupervisor` remains authoritative for Rule, teacher, shadow, or active ML paths.
