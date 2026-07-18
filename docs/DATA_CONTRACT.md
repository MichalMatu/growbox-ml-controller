# Data contract (v4) — short rules

Normative agent/stack/export law: **[`AGENTS.md`](../AGENTS.md)**.
If this file conflicts with `AGENTS.md`, **`AGENTS.md` wins**.

> **This sparse FE branch** keeps the contract JSON, docs, and root gate only.
> C++ generation, board runtime, simulator, and monorepo CI live on **`main`**.

## Source of truth

| Artifact | Path |
|----------|------|
| Contract (ranges, paths, feature order, 15 outputs) | [`schemas/environment-controller.json`](../schemas/environment-controller.json) (`schema_version` **4**) |
| Field meanings for UI | [`SCHEMA_V4_FIELD_GUIDE.md`](SCHEMA_V4_FIELD_GUIDE.md) |
| Configurator product scope | [`HARDWARE_CONFIGURATOR.md`](HARDWARE_CONFIGURATOR.md) |
| Golden export JSON | [`examples/minimal-single-pot.json`](examples/minimal-single-pot.json) |
| Root gate | `pnpm gate` → [`gate/check-contract.mjs`](../gate/check-contract.mjs); regression coverage: `pnpm test:contract` |

**Do not invent ML paths.** UI fields must be:

- a `path` under `model.features`, or
- an **allowed root meta key**: `seed`, `profile_id`, `title`, `enclosure` (see `AGENTS.md`).

## Path notation

- Schema: `pots.0.irrigation.available`
- Export JSON: `pots[0].irrigation.available`
- Same field; different addressing form.

## Domain

- Up to **four pots** share one chamber air volume (`environment.growbox_volume_m3`).
- Export array: always `pots[0]` … `pots[3]` (length **4**).
- Feature names often **1-based** (`pot_1_*`, `irrigation_pot_1`).

## Mix & match (never drop slots)

| Kind | Installed / on | Missing / off |
|------|----------------|---------------|
| Sensor | `validity.<path> = true` + reading | `validity.<path> = false` — slot stays |
| Global actuator | `actuators.*.available = true` (+ limits) | `available = false` + zero capability max/dose/efficiency fields; command forced 0 at runtime |
| Pot module | `pots[N].irrigation` / `heat_mat` available | unavailable module keeps its object but zeroes its capability fields, even on an active pot |
| Pot | `pots[N].available = true` | `false` — slot remains; soil validity false; irr/mat unavailable; irr/mat limits 0; every pot `previous` value 0 (`AGENTS.md` §6) |
| Lights schedule | `pseudo.lights_active` true/false | still present; **not** a 15-way ML output; **no** `actuators.lights` |

**No required bundles.** Any combination of sensors/actuators/pots is valid.

## Outputs

- **15 ML outputs**, each continuous command in **`[0, 1]`**, fixed order (gate checks names):
  `heater`, `fan`, `humidifier`, `dehumidifier`, `cooler`, `co2_doser`,
  `irrigation_pot_1`…`4`, `nutrient_heater`, `heat_mat_pot_1`…`4`.
- Configurator sets **availability and limits**, never removes an output slot.
- Lights heat is **non-ML**; ML sees **`pseudo.lights_active`** only.

## Versioning / model signature

- The schema documents its canonical hash format. The local gate additionally pins the canonical SHA-256 signature of `schema.model`, so an unversioned feature/output order, range, default, or enum change fails immediately.
- **Breaking** (new ML slot, rename path, change meaning) → new `schema_version`, regen board/ML on **`main`**, retrain.
- Non-breaking: UI labels, guides, and grouping. An allowed-root-meta change still requires matching `AGENTS.md` and gate updates.

## Regenerating C++ / monorepo checks

Only on full monorepo (`main`):

```bash
python tools/schema/generate_environment_schema.py
python tools/schema/generate_environment_schema.py --check
```

Not available on this sparse branch (no `tools/`).

## Local contract gate (this branch)

```bash
pnpm gate

# Validate a prospective export file with the same rules:
node gate/check-contract.mjs --input path/to/export.json

# Run after edits to gate/**:
pnpm test:contract
```

Must exit 0 before claiming contract/example correctness. The candidate format has no legacy migration or unknown-key fallback.
