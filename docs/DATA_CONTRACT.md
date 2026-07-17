# Data contract (v4) — short rules

> **This sparse FE branch** keeps the contract JSON and docs only.  
> C++ generation, board runtime, simulator, and CI live on **`main`**.

## Source of truth

| Artifact | Path |
|----------|------|
| Contract (ranges, paths, feature order, 15 outputs) | [`schemas/environment-controller.json`](../schemas/environment-controller.json) (`schema_version` **4**) |
| Field meanings for UI (PL) | [`SCHEMA_V4_FIELD_GUIDE.md`](SCHEMA_V4_FIELD_GUIDE.md) |
| Configurator product scope | [`HARDWARE_CONFIGURATOR.md`](HARDWARE_CONFIGURATOR.md) |
| Example export JSON | [`examples/minimal-single-pot.json`](examples/minimal-single-pot.json) |

**Do not invent paths.** If UI needs a field, it must exist as a `path` under `model.features` (or documented meta such as `seed`).

## Domain

- Up to **four pots** share one chamber air volume.
- JSON array: `pots[0]` … `pots[3]` (0-based).
- Feature / UI labels often use **1-based** names (`pot_1_*`, `irrigation_pot_1`).

## Mix & match (never drop slots)

| Kind | Installed / on | Missing / off |
|------|----------------|---------------|
| Sensor | `validity.<path> = true` + live reading | `validity.<path> = false` — encoder uses default + mask; **slot stays** |
| Actuator | `actuators.*.available = true` (+ limits) | `available = false` — safety forces command **0**; zero dangerous max limits in export |
| Pot | `pots[N].available = true` | `false` — pot slot remains; treat soil/irrigation/mat as inactive |
| Lights schedule | `pseudo.lights_active` true/false | still a fixed pseudo input — not a 15-way ML output |

**No required bundles.** Any combination of sensors/actuators/pots is valid.

## Outputs

- **15 ML outputs**, each continuous command in **`[0, 1]`**:  
  `heater`, `fan`, `humidifier`, `dehumidifier`, `cooler`, `co2_doser`,  
  `irrigation_pot_1`…`4`, `nutrient_heater`, `heat_mat_pot_1`…`4`.
- Configurator sets **availability and limits**, not “remove output from the list”.
- Lights heat is **non-ML** (`output_scope.non_ml_actuators`); ML sees **`pseudo.lights_active`** only.

## Versioning / hash

- Contract identity: schema version + hash metadata in the JSON file.
- **Breaking** change (new ML slot, rename path, change meaning) → new `schema_version`, regenerate board/ML artifacts **on `main`**, retrain.
- Non-breaking: UI labels, this guide, grouping, client template defaults.

## Regenerating C++ / checks

Only on full monorepo (`main`):

```bash
python tools/schema/generate_environment_schema.py
python tools/schema/generate_environment_schema.py --check
```

Not available on this sparse branch (no `tools/`).
