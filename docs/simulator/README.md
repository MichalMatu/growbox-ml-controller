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
| Research sources collected | **this folder** | [SOURCES.md](SOURCES.md) |
| Equation / param design | **next** | fill SOURCES → then [PHYSICS_SCOPE.md](PHYSICS_SCOPE.md) |
| New sim skeleton + tests | **next** | after sources reviewed |

## What “ready for skeleton” means

You can implement a new module (or rewrite `tools/ml/simulator.py`) that:

1. Holds one chamber air state + up to 4 pot substrate states.
2. Steps with `ControlAction` (15 outputs, names from contract).
3. Emits `EnvironmentState` that `controller_input_record` encodes to 128 features.
4. Does **not** invent new ML slots — only physics parameters inside the sim config.

You should **not** yet treat `make train-full` as product training.

## Recommended work order

```text
1. Collect sources          → docs/simulator/SOURCES.md  (you paste repos/links)
2. Agree physics scope      → PHYSICS_SCOPE.md (coupled processes, Δt, simplifications)
3. Parameter catalog        → which numbers live in scenario vs fixed constants
4. Skeleton API + tests     → tools/ml/simulator.py (or tools/ml/growbox_sim/)
5. Teacher cost on new dyn. → tools/ml/teacher.py
6. train-quick smoke        → then train-full + commit weights
```

## Related docs

| Doc | Role |
|-----|------|
| [IO_INVENTORY.md](IO_INVENTORY.md) | Full ML I/O map from live contract |
| [../DATA_CONTRACT.md](../DATA_CONTRACT.md) | Contract rules |
| [../IO_MAP.md](../IO_MAP.md) | Hardware mapping worksheet (may lag wording) |
| [../MODEL_PIPELINE.md](../MODEL_PIPELINE.md) | Dataset → train → export |
| [../plan.md](../plan.md) | Product history / thermodynamics intent |

## Code entry points

```python
from tools.ml import load_active_contract, summarize_training_fields
from tools.ml.controller_input import controller_input_record
from tools.ml.simulator import SequentialEnvironmentSimulator, ControlAction
from tools.ml.scenario_payload import default_scenario
```
