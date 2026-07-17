# Example scenario / hardware JSON

| File | Meaning |
|------|---------|
| [`minimal-single-pot.json`](minimal-single-pot.json) | Golden **MVP export** shape: 1 active pot, heater+fan+humid, 3 empty pot slots, previous = 0 |

## Rules for FE export

1. Always **exactly 4** entries in `pots`.
2. Inactive pot: `available: false`, soil `validity` false, irrigation/heat_mat `available` false, limits **0**.
3. Inactive global actuator: `available: false` and zero power/flow/dose max fields.
4. Do **not** emit `actuators.lights` (non-ML; use `pseudo.lights_active` only).
5. Pot `control_type` is only `"binary"` or `"pwm"` (schema enum encoding).
6. Global actuators have **no** `control_type` in the v4 feature list — do not invent it in export unless product later extends the contract.
7. `seed` / `profile_id` / `title` are **meta** (helpful for humans and pipelines); not ML feature paths.

Validate numbers against min/max in `schemas/environment-controller.json` (`model.features[].path`).
