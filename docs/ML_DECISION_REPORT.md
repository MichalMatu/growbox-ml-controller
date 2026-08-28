# ML decision report — climate-v6 Stages 12–16

Date: 2026-08-28
Branch: `mvp/environment-controller`

This document freezes the decisions reached by the climate-v6 research program so later runtime/product work does not repeat rejected experiments or accidentally reuse revealed evaluation seeds.

## Executive decision

`ClimateRulePolicy` remains the recommended authoritative runtime controller. ML remains valuable as an experimental/shadow policy, but no trained ML candidate from Stages 12–16 is qualified to replace Rule for active actuation. `SafetySupervisor` remains authoritative regardless of policy mode.

## Stage 12 — stronger Sequence Teacher

The previous teacher was too weak because it repeatedly applied the same action over the prediction horizon and did not observe hidden actuator lag state. A receding-horizon Sequence Teacher was added.

Untouched final seed `173205`:

- Rule tracking: `3.91479117413`
- Sequence Teacher tracking: `3.73843104661`
- tracking improvement: `4.5049689672%`
- Rule switching: `0.00507047`
- Sequence switching: `0.0215463`
- safety interventions: `0`
- hard-limit violations: `0`

Verdict: **PASS**. Sequence Teacher is the required teacher for new climate labels.

## Stage 13 — effective actuator observability

Six estimated effective actuator states were added to the feature contract:

- heater, tau 35 s
- cooler, tau 45 s
- exhaust fan, tau 8 s
- humidifier, tau 20 s
- dehumidifier, tau 20 s
- CO2 doser, immediate response in the estimator

The estimator advances from the safe/applied semantic action after the interval. It never consumes raw ML requests. The input contract therefore moved from 38 to 44 features while keeping 6 outputs.

Current bounded network: `44 -> 32 -> 32 -> 6`, 2,694 parameters.

Implementation commit: `34d164cd7b5a68ed7b46228e7aef8539c7539c6e`. Full verification passed (Python, schema, host C++, clang-tidy).

Verdict: **KEEP**. This is part of the active climate-v6 contract.

## Stage 14 — residual ML

Residual control was evaluated as `u = clamp(u_rule + delta_u_ml)`. Projection removed unsafe/opposed commands, but representative DEV did not produce an acceptable tracking/switching Pareto point.

The larger 180-row data probe still showed:

- all-output residual tracking gain: `0.89356%`
- all-output switching increase: `50.84%`
- cooler+exhaust tracking gain: `0.71349%`
- cooler+exhaust switching increase: `35.34%`

Verdict: **NO-GO**. Do not implement residual policy in runtime from this evidence. Do not widen the MLP to compensate.

## Stage 15 — CO2/exhaust deterministic coupling

CO2 dosing and exhaust are physically coupled, but simple deterministic suppression/prioritization rules regressed representative DEV behavior.

The dominant-request candidate on DEV seed `316227` produced:

- tracking: `0.30985%` worse than Rule
- switching: `71.8%` higher
- CO2 MAE: `8.4278%` worse
- safety/arbitration/hard-limit violations: zero after the candidate rule itself

Verdict: **NO-GO**. Do not add a generic CO2/exhaust coupling heuristic without a new physical/runtime hypothesis.

## Stage 16 — limited Sequence-Teacher DAgger

DAgger was updated so new rows can explicitly use Sequence Teacher while preserving the legacy rollout default for compatibility. Source commit: `698d4e7e31a192a19b9f18cc0d11ea7a1a146fa6`.

Exactly one bounded Sequence-Teacher iteration was tested and confirmed on a second DEV seed. The candidate was never persisted.

DEV seed `282843`:

- current ML tracking: `5.23519034206`
- candidate tracking: `4.94940628142`
- improvement vs current ML: `5.4589048719%`
- Rule tracking: `4.25717215776`
- switching ratio vs current ML: `1.5622759317`
- candidate arbitration/safety/hard-limit fractions: `0 / 0 / 0`
- iteration-2 gate: `false`

Confirmation DEV seed `331643`:

- current ML tracking: `5.98614583203`
- candidate tracking: `5.84959558030`
- improvement vs current ML: `2.2811046633%`
- Rule tracking: `4.99485892680`
- switching ratio vs current ML: `2.0542329056`
- candidate arbitration/safety/hard-limit fractions: `0 / 0 / 0`
- iteration-2 gate: `false`

Verdict: **STOP after one iteration**. The candidate consistently improves the current ML model, but switching cost is unacceptable and Rule remains better. No iteration 2, no final/test inspection for this candidate, and no publication.

## Seed hygiene

Revealed/burned seeds must not be reused as untouched final seeds:

`271828, 314159, 577215, 424242, 91273, 161803, 173205, 141421, 223607, 244949, 316227, 707107, 282843, 331643`

Stage-14 A/B reserved test metrics remain uninspected.

## Frozen next direction

Do not start another broad training sweep from the same synthetic assumptions. The next product stages are:

1. runtime policy modes: `Rule`, `MlShadow`, gated `MlActive`;
2. shadow diagnostics while Rule remains authoritative;
3. trace recording and deterministic replay;
4. Python/C++ runtime parity;
5. fake/simulator adapters and hardware-in-the-loop preparation;
6. later hardware calibration of actuator/sensor dynamics;
7. ML v2 only after real or calibrated trajectories provide a new hypothesis.
