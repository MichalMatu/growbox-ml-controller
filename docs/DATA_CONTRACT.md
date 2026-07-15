# Data contract

**Source of truth:** [`schemas/environment-controller-v1.json`](../schemas/environment-controller-v1.json)
**Roadmap v2:** [plan.md](plan.md)

Change the schema → regenerate C++ headers → retrain → commit generated artifacts together. Do not add features only in Python or only in firmware.

## Rules

**Sensors:** each measurement has a `validity` flag. If false, the encoder substitutes the contract default and the mask tells the model the value is imputed.

**Actuators:** `available: false` and zero max capability. The model sees unavailability; safety independently forces final output to zero.

**Outputs:** continuous `[0, 1]` per actuator. Safety may clamp, quantize binary actuators, or limit pump pulses.

**Version:** schema version + hash. `ModelRuntime` rejects mismatched model dimensions or hash.

## Regenerate

```bash
python tools/schema/generate_environment_schema.py
python tools/schema/generate_environment_schema.py --check   # CI
```

I/O worksheet (hardware mapping): [IO_MAP.md](IO_MAP.md).
