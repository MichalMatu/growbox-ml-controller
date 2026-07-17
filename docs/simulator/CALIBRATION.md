# Simulator calibration (real box → lumped parameters)

**Goal:** make Tier A/B physics *magnitudes* match your growbox without porting GES or Richards.

Directions are already checked by `python -m tools.ml.probe_simulator`.
This document is about **fitting 8–12 scalars** from open-loop tests.

## What we calibrate (and what we do not)

| Do | Do not |
|----|--------|
| `thermal_mass_j_per_k`, heater effective power | Full GES (21 nodes, radiation network) |
| fan / leak ACH | Richards soil PDE |
| humidifier g/h (effective delivery) | Crop dry-weight economics |
| CO₂ ppm per pulse | Dual-porosity substrate |
| substrate water capacity ml | New ML features |

Code:

| Module | Role |
|--------|------|
| `tools/ml/calibration.py` | Protocol + closed-form estimators + apply to `Scenario` |
| `tools/ml/calibrate_simulator.py` | CLI |
| `tools/ml/deviations.py` | Live \(e = x - x^*\) |
| `tools/ml/foresight.py` | Inject sensors + short rollout |
| `tools/ml/physics/psychrometrics.py` | T-aware RH capacity (Magnus) |

## Quick start

```bash
# Human protocol (markdown)
python -m tools.ml.calibrate_simulator protocol

# Self-consistency demo (synthetic series from current sim)
python -m tools.ml.calibrate_simulator demo --out-dir build/calibration-demo

# Fit a real measurement bundle
python -m tools.ml.calibrate_simulator fit --bundle path/to/bundle.json --out build/calibration.json
```

### Bundle JSON shape

```json
{
  "growbox_volume_m3": 0.8,
  "heater_power_w": 180,
  "heater_efficiency": 0.92,
  "heater_series": {
    "t_s": [0, 10, 20],
    "air_temperature_c": [20.0, 20.4, 20.9]
  },
  "fan_series": {
    "t_s": [0, 10, 20],
    "air_temperature_c": [28.0, 26.5, 25.2],
    "outside_temperature_c": [14.0, 14.0, 14.0]
  },
  "humidifier_series": {
    "t_s": [0, 10, 20],
    "air_humidity_pct": [40.0, 48.0, 55.0],
    "air_temperature_c": [24.0, 24.0, 24.0]
  },
  "co2_pulse": { "before_ppm": 600, "after_ppm": 800, "pulses": 2 },
  "irrigation_pulse": {
    "soil_before_pct": 35.0,
    "soil_after_pct": 50.0,
    "applied_ml": 100.0
  }
}
```

Omit keys you did not measure; estimators run only on present sections.

**Important:** `fan_series` **must** include `outside_temperature_c`. Using the final chamber
temperature as a substitute overstates ACH (bug class we reject in the estimator).

Calibrated `thermal_mass_j_per_k` scales heat input in the Van Henten chamber path
(default reference 35 000 J/K), not only the legacy energy-balance mode.

## Protocol (summary)

| ID | Action | Estimates |
|----|--------|-----------|
| `heater_step` | Heater 1, fan 0, 5–10 min | thermal mass |
| `fan_exchange` | Warm box, then fan 1 | ACH / fan airflow |
| `humidifier_step` | Humidifier 1, 3–5 min | effective g/h |
| `co2_pulse` | 1–3 pulses, fan 0 | ppm/pulse |
| `irrigation_pulse` | One known ml pulse | substrate capacity ml |
| `idle_leak` | Optional free drift | leak / UA |

Full text: `python -m tools.ml.calibrate_simulator protocol`.

## Live deviations & foresight (no ML)

```python
from tools.ml.simulator import SequentialEnvironmentSimulator, ControlAction, default_scenario_v2
from tools.ml.deviations import deviations_from_simulator
from tools.ml.foresight import inject_state, foresight

sim = SequentialEnvironmentSimulator(default_scenario_v2())
inject_state(sim, {"air_temperature_c": 18.0, "air_humidity_pct": 40.0})
print(deviations_from_simulator(sim).as_dict())

pred = foresight(sim, ControlAction(heater=1.0), steps=6)
print(pred.steps[-1].deviations.rms_normalized)
```

Panel **Na żywo** shows a **Δ** column (odczyt − cel) for climate and pots.

## After calibration

1. Apply estimates to scenarios used by `generate_dataset` / panel defaults.
2. Re-run `python -m tools.ml.probe_simulator`.
3. Only then retrain (`make train-quick` / `train-full`).

Soft teacher priorities (T vs RH vs CO₂) stay in `CostConfig` — calibration does not replace them.

## Related

- [VALIDATION.md](VALIDATION.md) — directional probe
- [PHYSICS_SCOPE.md](PHYSICS_SCOPE.md) — what the sim is allowed to model
- [DEPENDENCIES.md](DEPENDENCIES.md) — physics vs weights vs safety
