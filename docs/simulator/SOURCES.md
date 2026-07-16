# Research sources for growbox environment simulation

**Purpose:** one place to dump repos, papers, product notes, and raw measurements before we
rewrite physics in code. Nothing here is an ML contract field — only research input.

**How to use:** add a row under the right section. Prefer links + 2–5 bullet takeaways + which
sim subsystem it feeds (air T/RH, soil moisture, CO₂, lamp heat, …).

---

## Index (fill as you go)

| ID | Type | Title / URL | Priority | Used for |
|----|------|-------------|----------|----------|
| S01 | _example_ | _https://…_ | high | air energy balance |
| | | | | |

Priority: `high` | `medium` | `low` | `skip`.

---

## Repositories

<!-- Paste clone URLs, stars/context optional. -->

### Sxx — _repo name_

- **URL:**
- **License:**
- **Language / stack:**
- **What it models well:**
- **What to ignore / wrong domain:**
- **Parameters or formulas to extract:**
- **Maps to our sim:** air | RH | soil | CO₂ | light heat | fan exchange | irrigation | other:
- **Notes:**

---

## Papers / articles / books

### Sxx — _title_

- **Link / DOI:**
- **Key equations or figures:**
- **Assumptions (closed box, greenhouse, hydro, …):**
- **Maps to our sim:**
- **Notes:**

---

## Product / hobby growbox notes

Real equipment dimensions, heater W, fan m³/h, pot sizes, lamp heat — useful for scenario ranges.

### Sxx — _source_

- **Link / photo / private note:**
- **Measured or rated values:**
- **Maps to contract fields:** e.g. `environment.growbox_volume_m3`, `actuators.heater.max_power_w`
- **Notes:**

---

## Datasets / logs from our hardware

NDJSON captures from panel/serial (`logs/`, `make` replay) — gold for calibration later.

| File / session | Conditions | Useful signals | Notes |
|----------------|------------|----------------|-------|
| | | | |

---

## Physics topics checklist (tick when covered by ≥1 source)

- [ ] Chamber energy balance (sensible heat, thermal mass)
- [ ] Moisture balance / absolute humidity / psychrometrics
- [ ] Latent heat of evaporation (T ↔ RH coupling)
- [ ] Substrate water content dynamics + evaporation to chamber
- [ ] Per-pot irrigation impulse → soil moisture
- [ ] Soil / root-zone temperature (heat mat, air coupling)
- [ ] Nutrient tank temperature (heater)
- [ ] Fan + leak ACH exchange with outside T/RH/CO₂
- [ ] CO₂ dosing pulse + dilution
- [ ] Lamp heat when `lights_active`
- [ ] Cooler / dehumidifier / humidifier actuator maps
- [ ] Time constants / lag of actuators
- [ ] Typical growbox dimensions and power ranges (for scenario sampling)

---

## Decision log (short)

| Date | Decision | Rationale | Sources |
|------|----------|-----------|---------|
| | | | |

---

## Out of scope for v4 training sim (do not expand contract)

- CFD / full 3D airflow
- PPFD / spectrum as ML features
- EC/pH hydro chemistry (roadmap later)
- Multi-chamber / multi-controller

See also: [PHYSICS_SCOPE.md](PHYSICS_SCOPE.md).
