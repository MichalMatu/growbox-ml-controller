# Model pipeline

Deterministic path: simulation → teacher labels → Keras MLP → emlearn C export → golden-vector parity.

> **Do not treat `--quick` as a production model.** Full train (`make train-full`) exports the
> committed emlearn weights used on ESP demo firmware. After physics/teacher changes, re-run full
> train and flash (`PORT=… make flash`) before on-device evaluation.

## Commands

```bash
make train-quick    # small dataset, CI smoke only
make train-full     # larger dataset — use after simulator fidelity work
python -m tools.ml.pipeline --check-generated
```

## Stages

1. Validate schema (`schemas/environment-controller.json`)
2. Generate scenarios (split by seed: train / val / test)
3. Label with rollout teacher (finite action grid, short horizon)
4. Train MLP (sigmoid outputs, 128 → 32 → 32 → 15)
5. Export emlearn + manifest + golden vectors
6. Host C++ tests match Python within tolerance

Teacher is explicit cost search on simulator rollouts, not RL.

Details: `tools/ml/pipeline.py`, `teacher.py`, `simulator.py`, `controller_input.py`.
Physics redesign notes: [simulator/README.md](simulator/README.md).
