# Data contract

**Source of truth:** [`schemas/environment-controller.json`](../schemas/environment-controller.json) (schema_version **4**)

Field names, order, ranges, and outputs are defined only there. Change the schema → regenerate C++ → retrain → commit generated artifacts together.

## Domain: pots, not zones

Up to **four pots (donice)** share one growbox air volume. JSON root is `pots` (array index 0..3). Feature names use 1-based labels (`pot_1_*`, `irrigation_pot_1`, …).

## Rules

**Mix & match:** fixed slot list; every sensor and actuator is independently enabled. No required bundles.

**Sensors:** each measurement has its own `validity` flag. If false, the encoder substitutes the contract default and the mask tells the model the value is imputed.

**Actuators:** each output has its own `available`. When false, zero max capability; safety forces final output to zero.

**Outputs:** continuous `[0, 1]` per actuator (15 total including irrigation and heat mats per pot).

**Physics (training only):** lumped growbox thermodynamics live in `tools/ml/simulator.py`, not in the JSON contract.

**Version:** schema version + hash. `ModelRuntime` rejects a model built for a different hash/dimensions.

## Regenerate

```bash
python tools/schema/generate_environment_schema.py
python tools/schema/generate_environment_schema.py --check   # CI
```

I/O worksheet: [IO_MAP.md](IO_MAP.md). Pipeline: [MODEL_PIPELINE.md](MODEL_PIPELINE.md).
