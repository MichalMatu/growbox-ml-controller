# Model pipeline

Deterministic path: simulation → teacher labels → Keras MLP → emlearn C export → golden-vector parity on host and firmware.

> **Do not treat `--quick` as the production model.** See [plan.md](plan.md): complete contract v2 first, then `train-full`.

## Simulator fidelity

The training simulator (`tools/ml/simulator.py`, mirrored in firmware `DummyEnvironmentSimulator`) should model growbox **thermodynamics as closely as practical**: one air volume, up to four coupled pots, nonlinear T↔RH↔soil↔fan↔outside exchange. It is a lumped-parameter model, not CFD — but weak physics yields weak ML policies. Full coupling spec: [plan.md](plan.md) → *Symulator — termodynamika growboxa*. I/O slots live in [IO_MAP.md](IO_MAP.md), not physics equations.

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

Teacher is explicit cost search on simulator rollouts, not RL. Calibrate simulator parameters against real growbox replay over time.

Details: `tools/ml/pipeline.py`, `teacher.py`, `simulator.py`.
