# Model pipeline

## Purpose

The pipeline proves that one versioned contract can travel from simulation through training and C
export into the firmware. Its simulator is deliberately simple and physically inspired; it is not
a calibrated digital twin.

## Stages

1. Load and validate the v1 schema.
2. Generate deterministic time-series scenarios with explicit seeds.
3. Keep whole scenario seeds in exactly one of train, validation, or test.
4. Label states with a deterministic rollout teacher over a fixed action grid.
5. Train a small two-hidden-layer Keras MLP with four sigmoid outputs.
6. Evaluate held-out scenarios and record metrics.
7. Convert the trained network with emlearn and emit a portable C header.
8. Generate a deterministic C++ manifest and reproducible golden vectors.
9. Compile a host prediction harness and compare it with Keras predictions.

The quick profile exercises every stage with a small dataset. The full profile increases scenario
count and epochs; it does not change the contract or network interface.

```bash
python -m tools.ml.pipeline --quick
python -m tools.ml.pipeline --full
```

All random generators receive explicit seeds. Generated headers omit wall-clock timestamps. The
firmware model and manifest must regenerate byte-for-byte. Golden inputs and metadata must match
exactly; expected floating-point predictions may vary slightly between CPU math kernels, so CI
accepts them only within the same strict tolerance used by the Python/C export check.

## Teacher

The teacher evaluates a stable Cartesian action set across a short simulator horizon. Its explicit
cost weights cover target errors, energy, water, switching, invalid/unavailable commands, and
unreachable targets. Candidate iteration order is the tie breaker; v1 does not use reinforcement
learning.

## Export verification

Passing Keras evaluation is insufficient. The pipeline also runs the exported implementation on
committed golden inputs and checks all four values against Python within the configured floating
point tolerance. Native C++ tests exercise the same model wrapper and contract hash.
