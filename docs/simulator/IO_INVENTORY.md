# ML I/O inventory (live contract)

**Source of truth:** `schemas/environment-controller.json`
**Verify:** `python -c "from tools.ml import summarize_training_fields; print(summarize_training_fields())"`

Generated conceptually for schema **v4** — if this file drifts, trust the schema + the command above.

## Counts

| | Count |
|--|------:|
| Features | 128 |
| Outputs | 15 |
| Max pots | 4 |

## Outputs (order fixed)

1. `heater`
2. `fan`
3. `humidifier`
4. `dehumidifier`
5. `cooler`
6. `co2_doser`
7. `irrigation_pot_1` … `irrigation_pot_4`
8. `nutrient_heater`
9. `heat_mat_pot_1` … `heat_mat_pot_4`

All outputs normalized to **[0, 1]**; safety may force 0.

## Feature groups (training fields)

| Group | Count | Role |
|-------|------:|------|
| `sensors.*` | 7 | air in, nutrient T, outside air |
| `validity.*` | 7 | masks for those sensors |
| `pots.*.available` | 4 | donica on/off |
| `pots.*.sensors` | 8 | soil moisture + soil T ×4 |
| `pots.*.validity` | 8 | soil masks |
| `pseudo.lights_active` | 1 | lamp schedule readback |
| `environment.*` | 4 | volume, thermal mass, loss, ACH |
| `actuators.*` | 18 | available + capabilities (global) |
| `targets.*` | 4 | air T/RH/CO₂ + nutrient T |
| `previous.*` | 7 | global previous commands |
| `pots.*.cultivation` | 12 | pot volume, water capacity, transpiration |
| `pots.*.targets` | 8 | soil moisture + soil T targets |
| `pots.*.irrigation` | 20 | pump caps + control type |
| `pots.*.heat_mat` | 12 | mat caps + control type |
| `pots.*.previous` | 8 | previous irrigation + heat mat |

## Settings vs sensors (mental model)

| Kind | Examples | In ML vector? |
|------|----------|----------------|
| **Live sensors** | air T/RH, soil moisture | yes + validity |
| **Configuration / settings** | growbox volume, heater max W, pump flow | yes (scenario config) |
| **Targets / setpoints** | target air T, target soil moisture | yes |
| **Previous commands** | previous fan | yes (memory) |
| **Safety limits** | max air T alarm | in scenario JSON / safety config — **not** all are ML features |
| **Physics-only params** | response lags, lamp heat W | simulator scenario only until exposed |

## Mix & match rules

- Sensor off → `validity.<path> = false` (encoder uses default).
- Actuator off → `available = false` (model sees zero capability; safety output 0).
- Pot off → `pots[i].available = false` (targets/soil features canonicalized).

## Not in v4 ML vector (by design)

PPFD, leaf T, EC/pH, flood sensor, exhaust air sensors, weather station — see product roadmap in
[IO_MAP.md](../IO_MAP.md) / [plan.md](../plan.md).
