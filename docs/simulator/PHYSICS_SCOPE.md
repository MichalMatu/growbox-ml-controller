# Physics scope (draft — fill after SOURCES)

This file will define **what the training simulator is allowed to model** and what it deliberately
approximates. Do not put new ML features here — only dynamics behind existing contract slots.

## Design principles

1. **One air volume** — shared `air_temperature_c`, `air_humidity_pct`, `co2_ppm`.
2. **Up to 4 pots** — independent soil moisture/temperature; inactive pots contribute zero physics.
3. **Lumped-parameter** — ODE-style steps at scenario `timestep_s` (default 10 s), not CFD.
4. **Contract-facing state only** — sim internal energy/moisture stores may exist, but encoder sees
   only paths in [IO_INVENTORY.md](IO_INVENTORY.md).
5. **Mix & match** — every actuator/sensor can be off; sim must not require all hardware.

## State variables (proposed)

| Variable | Public contract mapping | Notes |
|----------|-------------------------|--------|
| Air temperature | `sensors.air_temperature_c` | chamber bulk |
| Air humidity | `sensors.air_humidity_pct` | RH or convert from absolute humidity internally |
| CO₂ | `sensors.co2_ppm` | |
| Outside T/RH/CO₂ | `sensors.outside_*` | boundary for exchange |
| Nutrient solution T | `sensors.nutrient_solution_temperature_c` | tank |
| Per-pot soil moisture | `pots[i].sensors.soil_moisture_pct` | |
| Per-pot soil T | `pots[i].sensors.soil_temperature_c` | optional validity |
| Lights | `pseudo.lights_active` | heat source, not ML output |

Internal (not in contract): absolute humidity, water mass per pot, effective actuator lag states.

## Actuator effects (proposed)

| Output | Primary effect | Secondary |
|--------|----------------|-----------|
| `heater` | air sensible heat | RH drop if AH fixed |
| `fan` | mix with outside | CO₂/T/RH toward outside |
| `humidifier` | increase AH / RH | slight cooling if latent |
| `dehumidifier` | decrease AH | waste heat optional |
| `cooler` | remove sensible heat | may condense water |
| `co2_doser` | raise CO₂ | ineffective if fan high (safety also blocks) |
| `irrigation_pot_N` | pot N water mass | chamber humidity later |
| `nutrient_heater` | tank temperature | irrigation ΔT safety |
| `heat_mat_pot_N` | pot N soil temperature | weak air heat optional |
| lamp (via `lights_active`) | air heat | not ML-controlled |

## Open questions (answer using SOURCES)

See also [FORMULAS.md](FORMULAS.md) and [SLOT_MAP.md](SLOT_MAP.md) (Tier A/B).

1. Store humidity as RH or absolute humidity internally? *(GES uses \(C_w\) kg/m³; Van Henten uses humidity state + RH output — prefer absolute internally.)*
2. One soil moisture pool per pot or dual (fast surface / bulk)? *(start: one pool per pot.)*
3. How strong is pot evaporation → chamber RH coupling at our box sizes?
4. Default Δt: keep 10 s or allow multi-rate? *(S03 env uses 900 s — we should substep.)*
5. Which parameters are scenario-random vs global constants?
6. Tier A backbone: compact Van Henten air triple vs reduced GES air node?

## Acceptance tests (later)

Directionality checks, e.g.:

- Dry warm pot evaporates faster than cold wet pot.
- Fan + cold outside lowers chamber T toward outside.
- Irrigation pulse raises soil moisture then slowly RH.
- CO₂ pulse raises ppm; fan reduces toward outside CO₂.
