# Schema v4 — field guide (configurator)

**Contract file:** [`schemas/environment-controller.json`](../schemas/environment-controller.json) (`schema_version` **4**)
**Example export:** [`examples/minimal-single-pot.json`](examples/minimal-single-pot.json)
**Product scope:** [`HARDWARE_CONFIGURATOR.md`](HARDWARE_CONFIGURATOR.md)
**Normative law (stack, gate, export):** [`AGENTS.md`](../AGENTS.md) — wins on conflict.

This guide explains **what each JSON path means** for a hardware / scenario editor.
It does **not** replace the schema: **min / max / default**, feature **order**, and hash live only in the JSON file.
Machine check of schema + golden example: **`pnpm gate`** at repo root.

| Rule | Detail |
|------|--------|
| Language | Path / identifiers: **English**. UI labels: Polish OK. |
| Path form | Schema path uses dots + numeric pot index: `pots.0.available`. Export JSON uses arrays: `pots[0].available`. |
| Path vs feature name | Editor uses **`path`**. Flat **`name`** (e.g. `air_temperature_valid`) is encoder/ML side. Prefer **path** in UI model. |
| Never drop slots | Off = flag false / available false / zeros per `AGENTS.md` — array length and keys stay. |
| Ranges | Always read from `model.features[]` matching `path`. |
| Meta root keys | `seed`, `profile_id`, `title`, optional `enclosure` only — not ML features. |

---

## Mix & match

| Kind | ON | OFF |
|------|----|-----|
| Sensor | `validity.<sensor_path> = true` | `false` → default value + ML mask; slot remains |
| Global actuator | `actuators.<id>.available = true` + non-zero limits as needed | `available = false` + **zero max power/flow/dose/efficiency** in export |
| Pot module | `pots[N].irrigation` / `heat_mat` available | unavailable module keeps its object but zeroes its capability fields |
| Pot | `pots[N].available = true` | `false` + force soil validity false, irr/mat unavailable, limits 0 |
| Lights schedule | `pseudo.lights_active` | still present; false if no schedule integration |

New ML sensor/output = **new schema version** (breaking). Not a silent UI field.

---

## UI screen map → JSON

| # | UI group | Primary paths |
|---|----------|----------------|
| 1 | **Chamber** | `environment.*` |
| 2 | **Sensors** | `sensors.*` + `validity.*` (air, outside, nutrient) |
| 3 | **Pots 1–4** | `pots[0..3].*` |
| 4 | **Outputs** | `actuators.*` |
| 5 | **Lights (pseudo)** | `pseudo.lights_active` |
| 6 | **Climate targets** (optional MVP) | `targets.*` |
| 7 | **Previous** (default 0) | `previous.*`, `pots[N].previous.*` |
| — | **Meta** | `seed`, `profile_id`, `title` (not ML features) |

---

## Meta (not in `model.features`)

Root-level keys only (not nested under a `meta` object unless product later standardizes that — **current golden uses root keys**):

| Key | Meaning |
|-----|---------|
| `seed` | Scenario / RNG seed for pipelines and board loads. Integer. |
| `profile_id` | Stable id string for this hardware template. |
| `title` | Human label. |
| `enclosure` | Optional UX object with exactly positive numeric `width_cm`, `depth_cm`, `height_cm`. Not ML. Its volume (`width × depth × height / 1_000_000`) must equal `environment.growbox_volume_m3`. |

---

## 1. Chamber — `environment.*`

These **are** ML features (scalars in the 128-vector), not “sim-only hacks”.
In the configurator they describe **box physics parameters** the client can set or leave at template defaults.

| Path | Unit | Meaning |
|------|------|---------|
| `environment.growbox_volume_m3` | m³ | Chamber air volume. |
| `environment.thermal_mass_j_per_k` | J/K | Thermal inertia of the setup. |
| `environment.heat_loss_w_per_k` | W/K | Heat loss to surroundings. |
| `environment.air_leak_rate_ach` | 1/h | Passive air changes without fan. |

---

## 2. Sensors + validity

### Inside air

| Path | Meaning |
|------|---------|
| `sensors.air_temperature_c` | Air temperature in the chamber [°C] (process value). |
| `sensors.air_humidity_pct` | Relative humidity in the chamber [%]. |
| `sensors.co2_ppm` | CO₂ in the chamber [ppm]. |
| `validity.air_temperature_c` | Temperature sensor installed / trusted. |
| `validity.air_humidity_pct` | RH sensor installed. |
| `validity.co2_ppm` | CO₂ sensor installed. |

### Nutrient tank

| Path | Meaning |
|------|---------|
| `sensors.nutrient_solution_temperature_c` | Tank solution temperature [°C]. |
| `validity.nutrient_solution_temperature_c` | Tank temperature sensor installed. |

### Outside / inlet (boundary)

| Path | Meaning |
|------|---------|
| `sensors.outside_temperature_c` | Outside or inlet air temperature [°C]. |
| `sensors.outside_humidity_pct` | Outside or inlet RH [%]. |
| `sensors.outside_co2_ppm` | Outside or inlet CO₂ [ppm]. |
| `validity.outside_temperature_c` | Outside T sensor installed. |
| `validity.outside_humidity_pct` | Outside RH sensor installed. |
| `validity.outside_co2_ppm` | Outside CO₂ sensor installed. |

**Hardware UI:** toggles bind to **`validity.*`**.
**Process seed UI (optional):** number inputs bind to **`sensors.*`**.

---

## 3. Pseudo

| Path | Meaning |
|------|---------|
| `pseudo.lights_active` | Lamps on per schedule / readback (**not** PPFD). ML input. **Not** one of the 15 command outputs. |

Do **not** export `actuators.lights` — lights are listed under `output_scope.non_ml_actuators` in the schema.

---

## 4. Pots — `pots[0..3]` (UI labels Pot 1–4)

- Array index **0-based**.
- Labels and feature names often **1-based** (`pot_1_*`).

### Always four slots

Export **always** includes four pot objects. Empty slots use the inactive pattern (see example JSON).

### Per-pot paths

| Path | Meaning |
|------|---------|
| `pots[N].available` | Pot slot in use (plant / zone active). |
| `pots[N].sensors.soil_moisture_pct` | Substrate moisture [%] (process). |
| `pots[N].sensors.soil_temperature_c` | Substrate temperature [°C] (process). |
| `pots[N].validity.soil_moisture_pct` | Soil moisture probe installed on this pot. |
| `pots[N].validity.soil_temperature_c` | Soil temperature probe installed. |
| `pots[N].cultivation.pot_volume_l` | Pot volume [L]. |
| `pots[N].cultivation.substrate_water_capacity_ml` | Substrate water capacity [ml]. |
| `pots[N].cultivation.transpiration_factor` | Transpiration scale (1 = nominal). |
| `pots[N].targets.soil_moisture_pct` | Soil moisture setpoint [%]. |
| `pots[N].targets.soil_temperature_c` | Soil temperature setpoint [°C]. |
| `pots[N].irrigation.available` | Irrigation pump installed for this pot. |
| `pots[N].irrigation.flow_ml_s` | Pump flow [ml/s]. |
| `pots[N].irrigation.maximum_pulse_s` | Max pulse length [s]. |
| `pots[N].irrigation.minimum_interval_s` | Min time between pulses [s]. |
| `pots[N].irrigation.control_type` | **`binary`** or **`pwm`** only (schema enum). |
| `pots[N].heat_mat.available` | Heat mat under this pot. |
| `pots[N].heat_mat.max_power_w` | Mat max power [W]. |
| `pots[N].heat_mat.control_type` | **`binary`** or **`pwm`** only. |
| `pots[N].previous.irrigation` | Last irrigation command 0–1. |
| `pots[N].previous.heat_mat` | Last heat-mat command 0–1. |

### When `pots[N].available === false` (export must)

- `validity.soil_moisture_pct` = false
- `validity.soil_temperature_c` = false
- `irrigation.available` = false; `flow_ml_s` / `maximum_pulse_s` / `minimum_interval_s` = **0**
- `heat_mat.available` = false; `max_power_w` = **0**
- `previous.irrigation` / `previous.heat_mat` = **0**
- `control_type` keys **stay** (`"binary"` \| `"pwm"`)
- `cultivation.*` **may** remain non-zero (do not require zero volume/capacity)

---

## 5. Global actuators — `actuators.*`

| Path | Meaning |
|------|---------|
| `actuators.heater.available` | Air heater present. |
| `actuators.heater.max_power_w` | Max electrical/thermal scale [W]. |
| `actuators.heater.efficiency` | Fraction of power to air heat [0–1]. |
| `actuators.fan.available` | Fan / exchange present. |
| `actuators.fan.max_airflow_m3_h` | Max airflow [m³/h]. |
| `actuators.fan.minimum_command` | Dead-zone on 0–1 command (below → treat as off). |
| `actuators.humidifier.available` | Humidifier present. |
| `actuators.humidifier.max_output_g_h` | Max vapor output [g/h]. |
| `actuators.dehumidifier.available` | Dehumidifier present. |
| `actuators.dehumidifier.max_removal_g_h` | Max moisture removal [g/h]. |
| `actuators.cooler.available` | Active cooling present. |
| `actuators.cooler.max_cooling_w` | Max cooling power [W]. |
| `actuators.co2_doser.available` | CO₂ doser present. |
| `actuators.co2_doser.dose_ppm_per_full_pulse` | ppm per full pulse. |
| `actuators.co2_doser.maximum_pulse_s` | Max pulse duration [s]. |
| `actuators.nutrient_heater.available` | Tank heater present. |
| `actuators.nutrient_heater.max_power_w` | Max power [W]. |
| `actuators.nutrient_heater.efficiency` | Efficiency [0–1]. |

### Important: no global `control_type` in v4 features

Unlike pot irrigation/mat, **heater / fan / humidifier / … have no `control_type` path** in `model.features`.
Do **not** invent `actuators.heater.control_type` in export. Board policy may still use binary/PWM internally without that contract field.

### When `available === false` (export must)

Zero the capability fields (`max_power_w`, `max_airflow_m3_h`, `max_output_g_h`, `max_removal_g_h`, `max_cooling_w`, `dose_ppm_per_full_pulse`, and set `efficiency` to 0 where present).

---

## 6. Climate targets — `targets.*`

Setpoints — **not** sensor readings.

| Path | Meaning |
|------|---------|
| `targets.air_temperature_c` | Desired air temperature. |
| `targets.air_humidity_pct` | Desired RH. |
| `targets.co2_ppm` | Desired CO₂. |
| `targets.nutrient_solution_temperature_c` | Desired tank temperature. |

---

## 7. Previous commands — `previous.*`

Last applied commands in **`[0, 1]`** (warm start / board continuity).

| Path |
|------|
| `previous.heater` |
| `previous.fan` |
| `previous.humidifier` |
| `previous.dehumidifier` |
| `previous.cooler` |
| `previous.co2_doser` |
| `previous.nutrient_heater` |

Hardware-template export: set all to **0**, including per-pot `pots[N].previous.irrigation` / `heat_mat` for active and inactive pots alike.

---

## 8. Fifteen ML outputs (commands 0–1)

Names used by the model / board decision vector (not nested under `actuators` as paths in the same way — they are **output** slots):

1. `heater`
2. `fan`
3. `humidifier`
4. `dehumidifier`
5. `cooler`
6. `co2_doser`
7. `irrigation_pot_1`
8. `irrigation_pot_2`
9. `irrigation_pot_3`
10. `irrigation_pot_4`
11. `nutrient_heater`
12. `heat_mat_pot_1`
13. `heat_mat_pot_2`
14. `heat_mat_pot_3`
15. `heat_mat_pot_4`

Configurator does **not** remove an output. It sets hardware `available` / pot flags so safety keeps that command at 0.

---

## Enums

| Path pattern | Allowed JSON strings | Schema encoding (for ML) |
|--------------|----------------------|---------------------------|
| `pots[N].irrigation.control_type` | `"binary"`, `"pwm"` | binary → 0, pwm → 1 |
| `pots[N].heat_mat.control_type` | `"binary"`, `"pwm"` | same |

---

## Out of contract v4 (do not add as ML fields)

From `sensing_scope.explicitly_not_v2` and product rules:

- PPFD / light intensity as ML feature
- Leaf temperature, EC, pH, flood sensor
- Separate exhaust-only air sensors, weather station

Roadmap only — requires a new schema version.

---

## FE implementation checklist

- [ ] Model form state by schema **path** (or typed object that serializes 1:1).
- [ ] Import the shared schema; do not copy it into `web/`.
- [ ] Load min/max/default from `model.features`.
- [ ] Always serialize **4 pots**.
- [ ] Enforce unavailable pot-module, inactive-pot, inactive-actuator, and all-previous-zero rules (`AGENTS.md` §6).
- [ ] Structure-match [`examples/minimal-single-pot.json`](examples/minimal-single-pot.json).
- [ ] Reject invalid imports rather than retaining unknown fields or adding legacy-shape fallbacks.
- [ ] No `actuators.lights`.
- [ ] No global actuator `control_type`.
- [ ] `pnpm gate` green at repo root; `pnpm test:contract` green after gate edits; after scaffold, web gate green too.

---

## Related on this branch

- [`../AGENTS.md`](../AGENTS.md) — stack, gate, export law
- [`DATA_CONTRACT.md`](DATA_CONTRACT.md) — short rules
- [`HARDWARE_CONFIGURATOR.md`](HARDWARE_CONFIGURATOR.md) — product
- [`examples/README.md`](examples/README.md) — export rules + gate
