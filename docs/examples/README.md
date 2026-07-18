# Example scenario / hardware JSON

| File | Meaning |
|------|---------|
| [`minimal-single-pot.json`](minimal-single-pot.json) | **Golden** MVP export shape: 1 active pot; heater+fan+humidifier; pots 2–4 inactive; all `previous` = 0 |

Normative rules: **[`AGENTS.md`](../../AGENTS.md)** §6.
Machine check: from repo root run **`pnpm gate`**.

## Rules for FE export (must match gate)

1. Exactly **4** entries in `pots`.
2. Inactive pot: `available: false`; soil `validity` false; irrigation/heat_mat `available` false; irrigation flow/pulse/interval **0**; heat_mat `max_power_w` **0**. Cultivation numbers may stay non-zero.
3. Unavailable irrigation/heat_mat on any pot (including an active pot) has zero capability fields; every global and per-pot `previous` value is **0**.
4. Inactive global actuator: `available: false` and zero capability fields (including `maximum_*`, dose, and `efficiency` where present).
5. **Do not** emit `actuators.lights` — use `pseudo.lights_active` only.
6. Pot `control_type` only string `"binary"` or `"pwm"`.
7. Global actuators: **no** `control_type` key.
8. Root meta allowed: integer `seed`, string `profile_id` / `title`, optional exact-dimension `enclosure` whose derived volume equals `environment.growbox_volume_m3` — not ML feature paths.
9. Every `model.features[].path` from the schema must resolve on the export object; no unknown nested paths may remain.
10. Numbers stay within schema min/max for that path.

## Validate

```bash
# repo root
pnpm gate

# Any proposed export can be checked before the frontend exists:
node gate/check-contract.mjs --input path/to/export.json

# Run when changing the validator itself:
pnpm test:contract
```

Do not claim a new example is golden until `pnpm gate` is green.
