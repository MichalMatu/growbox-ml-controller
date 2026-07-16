# Slot map: S03 / S04 → growbox contract v4

Maps external greenhouse models onto **`schemas/environment-controller.json`**
(128 features, 15 outputs, `pots`). Use with [FORMULAS.md](FORMULAS.md).

---

## 1. ML outputs (commands 0–1) → physical inputs

Our controller emits normalized commands. The simulator must convert them to SI
fluxes (W, m³/s, g/h, ppm pulse, …) using scenario capabilities
(`actuators.*.max_*`, zone irrigation flow, heat mat max W, …).

| Our output | S03 (mpcrl) | S04 (GES) | Physical mapping (proposed) |
|------------|-------------|-----------|-----------------------------|
| `heater` | \(u_2\) heating | *not explicit* (unheated demo) | \(P_h = u_{\mathrm{heater}}\, P_{h,\max}\,\eta_h\) → air energy |
| `fan` | \(u_1\) ventilation | \(R_a\) (vent ACH) | \(R_a = R_{a,\mathrm{leak}} + u_{\mathrm{fan}}(R_{a,\max}-R_{a,\mathrm{leak}})\); exchange T/RH/CO₂ with outside |
| `humidifier` | — | \(MW_{cc,i}\) was 0 (dehum stub) | \(\dot m_w^{+} = u_{\mathrm{hum}}\, \dot m_{w,\max}\) → \(C_w\) |
| `dehumidifier` | — | same stub opposite | \(\dot m_w^{-} = u_{\mathrm{dehum}}\, \dot m_{w,\max}\) + optional heat dump |
| `cooler` | — | — | \(P_c = u_{\mathrm{cooler}}\, P_{c,\max}\) remove from air energy (optional latent) |
| `co2_doser` | \(u_0\) CO₂ supply | `added_CO2` / \(MC_{cc,i}\) | pulse: \(\Delta C = u_{\mathrm{co2}}\, \mathrm{dose_{ppm,full}}\) limited by max pulse s; **safety** zeros if fan high |
| `irrigation_pot_k` | — | — | **ours:** water mass to pot \(k\): \(\Delta V = u\, Q_{\mathrm{flow}}\, t_{\mathrm{pulse}}\) |
| `nutrient_heater` | — | — | **ours:** heat to nutrient tank node |
| `heat_mat_pot_k` | — | power into \(T_m\)-like node | \(P_m = u\, P_{m,\max}\) on pot \(k\) soil/mat capacitance |
| *(not ML)* `lights_active` | \(d_0\) solar/light | solar + artificial light flags | if true: \(P_{\mathrm{lamp}}\) into air (and maybe canopy) energy |

### S03 control scaling note

mpcrl uses **non-normalized** bounds:

| S03 input | min | max |
|-----------|----:|----:|
| \(u_0\) CO₂ | 0 | 1.2 |
| \(u_1\) vent | 0 | 7.5 |
| \(u_2\) heat | 0 | 150 |

Map: \(u_{\mathrm{S03},i} = u_{\mathrm{ours},i} \cdot u_{\max,i}\) (or fit \(u_{\max}\) to growbox ratings).

---

## 2. Sensors / features ← model states

| Our feature path | S03 | S04 | Notes |
|------------------|-----|-----|-------|
| `sensors.air_temperature_c` | \(x_2\) or \(y_3\) | \(T_i - 273.15\) | primary |
| `sensors.air_humidity_pct` | \(y_4\) (RH%) | from \(C_w\) + `sat_conc(T_i)` | convert absolute humidity carefully |
| `sensors.co2_ppm` | \(y_2\) | \(C_c\) → ppm via ideal gas | |
| `sensors.outside_temperature_c` | \(d_2\) | climate col T_ext | boundary |
| `sensors.outside_humidity_pct` | from \(d_3\) | climate RH_e | boundary |
| `sensors.outside_co2_ppm` | \(d_1\) | \(C_{ce}\) → ppm | boundary |
| `sensors.nutrient_solution_temperature_c` | — | — | **new node** or constant until modeled |
| `pots[k].sensors.soil_moisture_pct` | — | — | **ours** from water mass / capacity |
| `pots[k].sensors.soil_temperature_c` | — | \(T_m\) (single mat) | split into 4 pots or 1 shared + offset |
| `pseudo.lights_active` | related to \(d_0\) day/night | L_on / solar | schedule boolean |

Validity flags: set by scenario, not by physics.

---

## 3. Configuration features ← model parameters

| Our path | S03 | S04 | Mapping idea |
|----------|-----|-----|----------------|
| `environment.growbox_volume_m3` | implicit capacity in \(p_{15},p_{19}\) | \(V\) | set \(V\) directly; **scale all A from \(V^{2/3}\)** if needed |
| `environment.thermal_mass_j_per_k` | ~ \(p_{15}\) air/structure | \(V\rho c_i\) + structure nodes | lump structure into effective mass |
| `environment.heat_loss_w_per_k` | \(p_{17}\) term | cover/floor UA + vent | UA + optional screen |
| `environment.air_leak_rate_ach` | \(p_{10}\) base vent | \(R_{a,\min}\) crack model | ACH = \(R_a \cdot 3600\) |
| `actuators.heater.max_power_w` | related to \(u_2\) max 150 (model units) | — | set real watts (e.g. 100–600 W) |
| `actuators.fan.max_airflow_m3_h` | related to \(u_1\) max | \(R_{a,\max} V \cdot 3600\) | m³/h = ACH·V |
| `actuators.humidifier.max_output_g_h` | — | — | product rating |
| `actuators.dehumidifier.max_removal_g_h` | — | dehum was 0 | product rating |
| `actuators.cooler.max_cooling_w` | — | — | product rating |
| `actuators.co2_doser.dose_ppm_per_full_pulse` | related to \(u_0\) scale | `added_CO2` | calibrate pulse |
| `actuators.nutrient_heater.*` | — | — | ours |
| `pots[k].cultivation.substrate_water_capacity_ml` | — | mat water fraction ~25% | water capacity |
| `pots[k].cultivation.transpiration_factor` | crop term in \(\phi_{\mathrm{transp}}\) | LAI / SLA | scale plant strength |
| `pots[k].heat_mat.max_power_w` | — | heat into \(T_m\) | 8–45 W mats |
| `pots[k].irrigation.flow_ml_s` | — | — | pump rating |

---

## 4. Targets & previous

| Our path | Role in sim |
|----------|-------------|
| `targets.*` | not physics — teacher cost / scenario |
| `previous.*` | lag / rate limits (S03 has `du_lim`) |
| pot targets soil T/moisture | teacher + optional mat control |

S03 `get_du_lim()` → optional rate limit on our continuous actuators between steps.

---

## 5. Complexity tiers for implementation

### Tier A — chamber only (first skeleton)

States: \(T_{\mathrm{air}},\, C_w,\, C_{\mathrm{CO2}}\) (+ optional crop dummy).
Actuators wired: heater, fan, humidifier, dehumidifier, cooler, co2_doser, lights heat.
Dynamics backbone: **S03 \(\dot x_{1,2,3}\)** *or* reduced **S04 air + moisture + CO₂**.
Pots: static or slowly drifting soil moisture **without** full irrigation physics.

### Tier B — + pots (training-grade target)

Add per pot \(k=0..3\):

- water mass ↔ `soil_moisture_pct`
- soil T with heat mat + weak coupling to air (from S04 mat node)
- evaporation/transpiration share into chamber \(C_w\) (S03/S04 transp)
- irrigation pulse discrete water add

### Tier C — structure / radiation (optional fidelity)

Cover/floor nodes from S04, solar geometry — only if growbox has strong diurnal solar; indoor LED boxes may use constant lamp heat only.

---

## 6. Explicit non-maps (do not force)

| External concept | Why not a 1:1 slot |
|------------------|-------------------|
| S03 \(x_0\) lettuce dry weight | not a contract sensor; optional internal only |
| S04 fruit/leaf/stem C pools | crop growth beyond v4 ML features |
| OCHRE whole-home HVAC | different domain (S07) |
| ISO 52016 monthly EPBD | envelope bookkeeping only (S08) |

---

## 7. Suggested implementation file split (later code)

```text
tools/ml/
  simulator.py              # public API (Scenario, step, observe); chamber_model=
  physics/
    van_henten.py           # S03-derived ODEs (cite Mallick / Van Henten)  ✓ Tier A
    actuators.py            # 0–1 → S03 u + SI moisture extras             ✓ Tier A
    pots_substrate.py       # ours                                         (Tier B)
```

No import from `third_party/` at runtime — equations live in `tools/ml/physics/` with citations.

Default: `Scenario.chamber_model="van_henten"`. Fallback: `"legacy"`.
