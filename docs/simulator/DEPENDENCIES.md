# Control dependencies catalog (living document)

**Purpose:** slowly collect *what interacts with what* so growbox behavior stays sensible.
This is **not** a list of thousands of `if` rules. It feeds three different mechanisms.

| Layer | What it is | Scales how? | Where in code |
|-------|------------|-------------|---------------|
| **P — Physics** | Nature: fan cools *and* dilutes CO₂ | Continuous ODE; many couplings “for free” in the sim | `tools/ml/physics/`, `simulator.py` |
| **W — Weights (soft)** | “How much we care” when labeling / training | ~10–20 numbers, not N² rules | `CostConfig` in `teacher.py` → later loss weights |
| **S — Safety (hard)** | Never-do constraints | ~10–20 reasons, independent of ML | `SafetySupervisor` + schema `safety_defaults` |
| **H — Heuristics (optional)** | Short-horizon habits (“cool before dose”) | Few policies, explicit | teacher candidate pruning / later curriculum |

If you try to encode **every** combination as a hard rule:

\[
\text{rules} \sim O(2^{n_{\mathrm{out}}} \times \text{state bins})
\]

With 15 outputs and coarse state bins that explodes.
**Physics + soft cost + few hard safeties** avoid that explosion.

---

## How this relates to “ML and training” (plain language)

```text
1) Simulator: given sensors + commands → next state   (physics P)
2) Teacher: try many short command sequences, pick lowest cost  (weights W)
3) Dataset: (features, chosen commands)
4) Neural net: learn to imitate teacher quickly on-device
5) Safety: on-device hard filter of net output  (rules S)
```

- The **network does not store an explicit table of dependencies**.
- It learns a **smooth mapping** “situation → 15 numbers in [0,1]”.
- **Weights** (`CostConfig`) shape *what the teacher prefers* while building labels.
  Higher `temperature_error` than `co2_error` ⇒ teacher often sacrifices CO₂ to fix heat first.
- That is **priority by soft cost**, not a ranked if-else ladder (unless you add safety).

You do **not** need to understand backprop to use this catalog:
write dependency → mark layer **P / W / S** → we wire it to sim, cost, or safety.

---

## Priority model (recommended)

Use **three priorities only** — do not invent 50 ranks.

| Priority | Meaning | Mechanism |
|----------|---------|-----------|
| **P0 Hard** | Plant/equipment damage, illegal actions | **Safety** only (force 0 / clamp) |
| **P1 Soft goals** | Track targets T / RH / CO₂ / soil | **Cost weights** + teacher horizon |
| **P2 Efficiency** | Energy, water, switching | Smaller cost weights |

Example: “too hot + low CO₂”

| Priority | Behavior |
|----------|----------|
| P0 | If overtemperature alarm → fan min, heater off (safety) |
| P0 | If fan > vent threshold → **no CO₂ dose** (safety) |
| P1 | Teacher cost: large weight on T error, moderate on CO₂ |
| P1 | Physics: fan helps T but hurts CO₂ → teacher learns **sequence** |
| P2 | Prefer less heater / shorter CO₂ pulses when goals met |

Weights ≈ **relative importance of soft goals**, not physics laws.

---

## Catalog template (add rows slowly)

Copy a blank block when you discover a new interaction:

```markdown
### Dxxx — short title
- **Situation:** when …
- **Conflict / coupling:** A vs B because …
- **Layer:** P | W | S | H
- **Priority:** P0 | P1 | P2
- **Desired behavior:** …
- **Not desired:** …
- **Where implemented:** (sim / CostConfig field / SafetyReason / TODO)
- **Probe / test:** how we check
- **Notes / source:** …
```

---

## Seed catalog (start here)

### D001 — Fan cools and dilutes CO₂
- **Situation:** high air T, low CO₂, cold/low-CO₂ outside
- **Conflict:** vent helps T, hurts CO₂ (and moves RH)
- **Layer:** **P** (always) + **S** (block dose while venting) + **W** (T vs CO₂ weights)
- **Priority:** P0 no dose with high fan; P1 prefer cool-then-dose sequences
- **Desired:** cool with fan/cooler; dose when fan low
- **Not desired:** max fan + max CO₂ together
- **Where:** physics vent terms; `fan_venting_co2_threshold` → `Co2VentingFan`; `CostConfig.temperature_error` vs `co2_error`
- **Probe:** `probe_simulator` / manual A-B-C-D (see VALIDATION tradeoff note)
- **Notes:** classic greenhouse practice

### D002 — Heater vs cooler
- **Situation:** both available
- **Conflict:** waste energy if both on
- **Layer:** **S** (mutual exclusion if coded) + **W** (energy + opposing_actuators)
- **Priority:** P0 never both; P2 energy
- **Desired:** at most one of heat/cool active
- **Where:** Safety heater/cooler exclusion; `CostConfig.opposing_actuators` (heater×cooler product)
- **Notes:** soft label penalty always; hard safety where implemented

### D003 — Irrigation raises soil moisture and chamber RH
- **Situation:** dry soil vs high RH
- **Conflict:** watering helps soil, can worsen high humidity
- **Layer:** **P** + **W** (soil_moisture_error vs humidity_error)
- **Priority:** P1 — soil vs RH tradeoff by weights
- **Desired:** water when soil low and RH not extreme
- **Where:** `pots_substrate` → air RH; CostConfig
- **Notes:** no hard ban; soft cost

### D004 — Heat mat vs air temperature
- **Situation:** cold roots, warm air (or reverse)
- **Conflict:** mat heats soil; couples weakly to air
- **Layer:** **P** + **W** (soil_temperature_error vs temperature_error)
- **Priority:** P1
- **Desired:** mat for soil T without overheating air
- **Where:** pot thermal mass; CostConfig soil_temperature_error

### D005 — Lights as heat
- **Situation:** lights_active true
- **Conflict:** photoperiod needs light; heat load raises T
- **Layer:** **P** (lamp watts) + **S** (thermal cutoff may force lights off outside ML) + **H** (schedule outside ML)
- **Priority:** P0 safety thermal; light schedule not ML output
- **Desired:** ML does not control lamp relay; sees `lights_active`
- **Where:** sim lights heat; product Nodeflow/schedule

### D006 — Cold nutrient on warm soil
- **Situation:** irrigation with cold tank into warm pot
- **Conflict:** plant stress / shock
- **Layer:** **S** (ΔT / min nutrient T) + **P** (mix soil T toward nutrient)
- **Priority:** P0 block irrigate when ΔT too large
- **Where:** Safety nutrient-soil delta; pot irrigation mix
- **Notes:** contract targets + safety_defaults

### D007 — Humidifier vs dehumidifier
- **Situation:** both available
- **Conflict:** cancel each other
- **Layer:** **W** energy + **W** opposing_actuators + optional **S** exclusion
- **Priority:** P2 / soft P1 RH
- **Desired:** only one moisture actuator direction at a time
- **Where:** `CostConfig.opposing_actuators` (humidifier×dehumidifier); teacher energy; optional hard exclusion later

### D008 — CO₂ dose when CO₂ already ≥ target
- **Situation:** co2_ppm high
- **Layer:** **S**
- **Priority:** P0
- **Desired:** doser = 0
- **Where:** Safety Co2TargetReached

### D009 — Actuator unavailable
- **Situation:** `available=false`
- **Layer:** **S** + encoder features
- **Priority:** P0
- **Desired:** command forced 0; model sees unavailability
- **Where:** Safety + mix & match

### D010 — Sensor invalid
- **Situation:** validity false
- **Layer:** encoder mask + **S** for critical sensors (e.g. CO₂ dose)
- **Priority:** P0 for unsafe actions relying on bad sensors
- **Desired:** impute default for ML; block actions that need that sensor
- **Where:** FeatureEncoder; Co2SensorUnavailable etc.

---

## Mapping to `CostConfig` (soft priorities)

Current fields (`tools/ml/teacher.py`):

| Weight field | Typical role | Raise when… |
|--------------|--------------|-------------|
| `temperature_error` | P1 air T | heat stress more important than CO₂ |
| `humidity_error` | P1 RH | mold risk / VPD focus |
| `co2_error` | P1 CO₂ | enrichment campaign (but safety still blocks during vent) |
| `soil_moisture_error` | P1 irrigation | drought more critical |
| `soil_temperature_error` | P1 mats | root zone priority |
| `nutrient_temperature_error` | P1 tank | cold feed risk |
| `energy` | P2 | save power |
| `water` | P2 | save irrigation |
| `switching` | P2 | less flapping |
| `constraint_violation` | near-P0 in labels | illegal candidates in teacher search |
| `terminal_multiplier` | end of horizon | hit targets at horizon end |

Changing these **does not** change physics — only **what labels the teacher writes**.

---

## Mapping to Safety (hard priorities P0)

Keep this list short on purpose. New rows only when “must never”:

| Rule (examples) | Schema / reason |
|-----------------|-----------------|
| Fan high → no CO₂ | `fan_venting_co2_threshold` / `Co2VentingFan` |
| CO₂ ≥ target → no dose | `Co2TargetReached` |
| Overtemp → heater off, fan min | temperature alarm reasons |
| Actuator off → 0 | `ActuatorUnavailable` |
| Saturated soil → no pump | soil moisture block |
| Cold nutrient / ΔT → no irrigate | nutrient safety |

Full enum: `SafetyReason` in `EnvironmentTypes.h`.

---

## How you should grow this file

1. Notice a weird real or simulated behavior (“when I…, then…”).
2. Add **Dxxx** with layer P/W/S and priority P0/P1/P2.
3. Prefer:
   - **P** if nature does it → check/fix sim,
   - **S** if never allowed,
   - **W** if “usually prefer A over B”.
4. Only rarely add a new hard rule; default to weight + physics.
5. Link a probe case when possible (`probe_simulator` or a short script).

---

## Why exponential fear is right — and how we dodge it

| Approach | Growth |
|----------|--------|
| Explicit rule for every output combination | Exponential / impossible |
| Physics ODE (many couplings implicit) | ~linear in state size |
| Soft multi-objective cost (~10 weights) | constant small set |
| ~15 safety reasons | constant small set |
| Neural net capacity | fixed architecture; needs good labels + coverage |

Your job in this file: **describe intents and conflicts**.
Code maps them to P, W, or S — not to a combinatorial rule engine.

---

## Related

- [VALIDATION.md](VALIDATION.md) — open-loop probe
- [SLOT_MAP.md](SLOT_MAP.md) — sim ↔ contract
- [FORMULAS.md](FORMULAS.md) — physics extract
- `tools/ml/teacher.py` — `CostConfig`
- `lib/environment_control/src/SafetySupervisor.cpp` — hard rules
