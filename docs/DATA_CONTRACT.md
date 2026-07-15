# Data contract

**Source of truth:** [`schemas/environment-controller-v1.json`](../schemas/environment-controller-v1.json)
**Roadmap v2:** [plan.md](plan.md)

Change the schema → regenerate C++ headers → retrain → commit generated artifacts together. Do not add features only in Python or only in firmware.

## Rules

**Mix & match (v2):** fixed slot list; every sensor and actuator is independently enabled in the product profile. No required bundles.

**Sensors:** each measurement has its own `validity` flag. If false, the encoder substitutes the contract default and the mask tells the model the value is imputed.

**Actuators:** each output has its own `available`. When false, zero max capability; the model sees unavailability; safety independently forces final output to zero.

**Outputs:** continuous `[0, 1]` per actuator. Safety may clamp, quantize binary actuators, or limit pump pulses.

**Physics (training only):** coupled growbox thermodynamics live in the simulator (`tools/ml/simulator.py`), not in the JSON contract. See [plan.md](plan.md) → *Symulator — termodynamika growboxa*.

**Version:** schema version + hash. `ModelRuntime` rejects mismatched model dimensions or hash.

## Regenerate

```bash
python tools/schema/generate_environment_schema.py
python tools/schema/generate_environment_schema.py --check   # CI
```

I/O worksheet (hardware mapping): [IO_MAP.md](IO_MAP.md).
