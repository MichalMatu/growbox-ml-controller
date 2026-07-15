# Model pipeline

Deterministic path: simulation → teacher labels → Keras MLP → emlearn C export → golden-vector parity on host and firmware.

> **Do not treat `--quick` as the production model.** See [plan.md](plan.md): complete contract v2 first, then `train-full`.

## Commands

```bash
make train-quick    # small dataset, CI smoke
make train-full     # larger dataset — use after v2
python -m tools.ml.pipeline --check-generated   # CI: byte-stable headers
```

## Stages

1. Validate schema
2. Generate scenarios (split by seed: train / val / test)
3. Label with rollout teacher (fixed action grid, short horizon)
4. Train MLP (sigmoid outputs)
5. Export emlearn + manifest + golden vectors
6. Host C++ tests match Python within tolerance

Simulator is physically inspired, not a calibrated twin. Teacher is explicit cost search, not RL.

Details: `tools/ml/pipeline.py`, `teacher.py`, `simulator.py`.
