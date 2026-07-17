# Growbox environment simulator (training)

Status after contract **v4 / pots** (2026-07): code structure is ready for a **new physics-quality
simulator skeleton**. Committed MLP weights are `untrained-placeholder` until that work lands.

## Readiness checklist

| Item | State | Notes |
|------|--------|--------|
| Single schema `schemas/environment-controller.json` | **done** | v4, hash via `load_active_contract()` |
| Domain language: **pots** (donice), not zones | **done** | JSON root `pots`, C++/Python/panel |
| I/O vector frozen for training | **done** | 128 features, 15 outputs — see [IO_INVENTORY.md](IO_INVENTORY.md) |
| Bridge state → encoder | **done** | `tools/ml/controller_input.py` |
| Scenario defaults (no panel dep) | **done** | `tools/ml/scenario_payload.py` |
| Alignment guardrail sim ↔ schema | **done** | `tools/ml/alignment.py` |
| Training pipeline entry | **done** | `python -m tools.ml.pipeline` |
| Lumped physics fidelity | **placeholder** | current `tools/ml/simulator.py` is a stub-grade model |
| Research sources collected | **done (catalog)** | [SOURCES.md](SOURCES.md) + `third_party/` clones |
| Formula extract S03/S04 | **done** | [FORMULAS.md](FORMULAS.md) |
| Slot map → contract v4 | **done** | [SLOT_MAP.md](SLOT_MAP.md) |
| Equation / param design | **in progress** | [PHYSICS_SCOPE.md](PHYSICS_SCOPE.md) — refine after Tier A |
| New sim skeleton + tests | **Tier A+B done** | chamber Van Henten + `pots_substrate.py` |
| Psychrometrics (T-aware RH capacity) | **done** | `physics/psychrometrics.py` |
| Live deviations + foresight | **done** | `deviations.py`, `foresight.py`; panel Δ column |
| Open-loop calibration fit | **done** | `calibration.py` + `python -m tools.ml.calibrate_simulator` |
| Real-box coefficient fit | **pending data** | run protocol on hardware NDJSON / series |
| Scientific 3D twin view (PyVista) | **done (optional)** | `twin_scene` + `twin_view` — glyphs ≠ CFD |

## What “ready for skeleton” means

You can implement a new module (or rewrite `tools/ml/simulator.py`) that:

1. Holds one chamber air state + up to 4 pot substrate states.
2. Steps with `ControlAction` (15 outputs, names from contract).
3. Emits `EnvironmentState` that `controller_input_record` encodes to 128 features.
4. Does **not** invent new ML slots — only physics parameters inside the sim config.

You should **not** yet treat `make train-full` as product training.

## Recommended work order

```text
1. Collect sources          → SOURCES.md + third_party/     ✓
2. Extract formulas + map   → FORMULAS.md + SLOT_MAP.md     ✓
3. Tier A chamber physics   → tools/ml/physics/van_henten.py ✓
4. Tier B pot substrate     → tools/ml/physics/pots_substrate.py ✓
5. Open-loop probe / human validation → `python -m tools.ml.probe_simulator` ✓
6. Deviations + foresight   → tools/ml/deviations.py, foresight.py ✓
7. Calibration tooling      → tools/ml/calibration.py      ✓
8. Fit scalars on real box  → docs/simulator/CALIBRATION.md  next
9. Teacher / train-full     → after calibrated magnitudes
```

Validation notes: [VALIDATION.md](VALIDATION.md). Calibration: [CALIBRATION.md](CALIBRATION.md).

## Related docs

| Doc | Role |
|-----|------|
| [FORMULAS.md](FORMULAS.md) | Van Henten + GES equations and parameter tables |
| [SLOT_MAP.md](SLOT_MAP.md) | External model symbols → our 15 outputs / sensors |
| [IO_INVENTORY.md](IO_INVENTORY.md) | Full ML I/O map from live contract |
| [SOURCES.md](SOURCES.md) | Research index and licenses |
| [DEPENDENCIES.md](DEPENDENCIES.md) | Living catalog: physics / weights / safety priorities |
| [CALIBRATION.md](CALIBRATION.md) | Open-loop fit of lumped parameters |
| [TWIN_VIEW.md](TWIN_VIEW.md) | PyVista 3D chamber + exchange glyphs |
| [../DATA_CONTRACT.md](../DATA_CONTRACT.md) | Contract rules |
| [../IO_MAP.md](../IO_MAP.md) | Hardware mapping worksheet |
| [../MODEL_PIPELINE.md](../MODEL_PIPELINE.md) | Dataset → train → export |

## Code entry points

```python
from tools.ml import load_active_contract, summarize_training_fields
from tools.ml.controller_input import controller_input_record
from tools.ml.simulator import SequentialEnvironmentSimulator, ControlAction
from tools.ml.scenario_payload import default_scenario
from tools.ml.deviations import deviations_from_simulator
from tools.ml.foresight import inject_state, foresight
```

```bash
python -m tools.ml.probe_simulator
python -m tools.ml.calibrate_simulator protocol
python -m tools.ml.calibrate_simulator demo --out-dir build/calibration-demo
# optional 3D twin (pip install pyvista / pip install -e '.[twin]')
python -m tools.ml.twin_view --live
python -m tools.ml.twin_view --fan 1 --steps 40 --screenshot build/twin.png
```
