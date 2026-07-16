# Research sources for growbox environment simulation

**Purpose:** dump repos, papers, product notes, and raw measurements before we rewrite
physics in code. Nothing here is an ML contract field — only research input.

**Local clones:** [`third_party/`](../../third_party/README.md)
**Refresh:** `bash scripts/fetch_third_party.sh`

---

## Index

| ID | Type | Title / URL | Priority | Used for |
|----|------|-------------|----------|----------|
| S01 | web tool | [LetsGrow GPE](https://gpe.letsgrow.com/) | high | moisture/energy/ventilation intuition |
| S02 | paper | [iGrow arXiv:2107.05464](https://arxiv.org/abs/2107.05464) | medium | MDP + neural greenhouse sim (tomato) |
| S03 | repo | [mpcrl-greenhouse](https://github.com/SamuelMallick/mpcrl-greenhouse) | **high** | Van Henten climate ODEs, vents, RH, CO₂ |
| S04 | repo | [EECi/GES](https://github.com/EECi/GES) | **high** | heat/mass/CO₂ balances, radiation, mat T |
| S05 | repo | [Thermca](https://github.com/steffenschroe/Thermca) | medium | lumped thermal networks (LPTN) toolkit |
| S06 | repo | [thermal-nn](https://github.com/wkirgsn/thermal-nn) | medium | TNN = LPTN + learned params (method) |
| S07 | repo | [OCHRE](https://github.com/NatLabRockies/OCHRE) | low–med | residential HVAC / thermal loads (NREL) |
| S08 | repo | [pyBuildingEnergy](https://github.com/EURAC-EEBgroup/pyBuildingEnergy) | low–med | ISO 52016 hourly building energy |

Priority: `high` | `medium` | `low` | `skip`.

---

## Repositories

### S03 — mpcrl-greenhouse (SamuelMallick)

- **URL:** https://github.com/SamuelMallick/mpcrl-greenhouse
- **Local:** `third_party/mpcrl-greenhouse/`
- **License:** GPL-3.0 upstream
- **Permission (project-specific):** authors contacted; **use allowed if cited in our sources**
  (attribution + keep provenance). Prefer wrapping/adapting with clear credit over silent forks.
- **Language / stack:** Python 3.11, CasADi, gym env, MPC+RL
- **Paper:** Mallick et al., *Reinforcement learning-based model predictive control for greenhouse climate control*, Smart Agricultural Technology 10 (2025)
- **What it models well:**
  - Compact **Van Henten (1994) lettuce greenhouse** dynamics
  - States/outputs: dry weight, indoor CO₂, air T, humidity-related state
  - Fluxes: photosynthesis, ventilation of CO₂/humidity, **transpiration** (`phi_trasnp_h`)
  - Explicit parameter vector `p_scale` (28 physical constants) in `greenhouse/model.py`
  - Euler / RK4 integration steps suitable for our Δt training loop
- **What to ignore / wrong domain:**
  - Full MPC/RL agents (`mpcs/`, `agents/`) — control research, not our first sim target
  - Lettuce crop dry-weight economics as product goal (we care climate + soil for 4 pots)
  - No per-pot substrate moisture / heat mats
- **Parameters or formulas to extract:**
  - `Model.p_scale` physical constants (molar masses, latent-heat-related coeffs, vent coeffs)
  - `phi_vent_c`, `phi_vent_h`, `phi_trasnp_h`, `phi_phot_c` flux structure
  - Input bounds `get_u_min` / `get_u_max` for normalized actuators
- **Maps to our sim:** air T · RH · CO₂ · fan/vent exchange · crop transpiration → chamber humidity · (partial) heater/cool via energy terms
- **Notes:** Best compact ODE reference for *chamber* climate. Scale down from commercial greenhouse to growbox volume.
  **Always cite:** Mallick et al. (2025) + repo link in sim module docstring / SOURCES.

### S04 — GES (EECi / Cambridge)

- **URL:** https://github.com/EECi/GES
- **Local:** `third_party/GES/`
- **License:** MIT (compatible to study and re-use with attribution)
- **Language / stack:** Python 3 + MATLAB; `solve_ivp` BDF
- **Based on:** GDGCM (Pieters & Deltour 2000); Vanthoor PhD (Wageningen 2011)
- **What it models well:**
  - Multi-node temperatures: cover, internal air, vegetation, **growing medium (mat)**, tray, floor, soil layers
  - Convection / conduction / radiation
  - Plant **transpiration** (latent heat + moisture)
  - CO₂ + simple tomato photosynthesis/growth
  - Weather boundary: T, sky T, wind, RH, solar direct/diffuse per surface
  - Rich `parameters.py`: geometry, material properties, ventilation ACH, latent heat `H_fg`, air heat capacity
- **What to ignore / wrong domain:**
  - Commercial glasshouse geometry (250 m² floor, 1000 m³) — rescale to growbox
  - Unheated default demo; we have heaters/coolers/humidifier as actuators
  - Heavy crop-growth focus beyond what we need for ML climate control
- **Parameters or formulas to extract:**
  - `H_fg`, `c_i`, `lam`, Stefan–Boltzmann, sat vapour helpers (`sat_conc`)
  - Soil/mat layer thermal capacities — inspir for pot substrate thermal mass
  - Ventilation rate `R_a_max` style ACH mapping → our `air_leak_rate_ach` + fan
- **Maps to our sim:** air T · RH · CO₂ · light/solar heat · soil/mat T · outside exchange · structure heat loss
- **Notes:** Strongest *energy+mass balance* template. Prefer this for heat-mat / substrate temperature coupling.

### S05 — Thermca (steffenschroe)

- **URL:** https://github.com/steffenschroe/Thermca
- **Local:** `third_party/Thermca/`
- **License:** GPL-3.0 (`LICENSE.rst`) — study patterns; re-implement LPTN graph in our MIT code unless separately cleared
- **Language / stack:** Python package `thermca/`, conda envs, docs
- **What it models well:**
  - General **lumped-parameter thermal network** modeling (cuboid/cylinder bodies, FEM+MOR, simple nodes)
  - Convection / radiation / mass-transport film libraries; adaptive-step simulation
  - Domain-specific scripting for multi-node heat transfer — not horticulture-specific
- **What to ignore / wrong domain:** full FEM meshes for devices; no plant RH/CO₂
- **Parameters or formulas to extract:** LPTN graph construction; convection/radiation coupling patterns
- **Maps to our sim:** air + pot + structure as **thermal nodes** (heat mats, chamber air, substrate)
- **Notes:** Method library for *how* to wire nodes, not greenhouse crop physics. Pair with S04 node list.

### S06 — thermal-nn (Thermal Neural Networks)

- **URL:** https://github.com/wkirgsn/thermal-nn
- **Local:** `third_party/thermal-nn/`
- **License:** see `LICENSE` in clone
- **Paper:** arXiv [2103.16323](https://arxiv.org/abs/2103.16323); ScienceDirect thermal NN LPTN
- **Language / stack:** PyTorch / TensorFlow notebooks; MATLAB port
- **What it models well:**
  - **TNN**: interpretable state-space LPTN whose R/C/power-loss maps are learned MLPs
  - End-to-end differentiable temperature estimation from system excitation
  - Demo on electric-motor temperatures (not greenhouses)
- **What to ignore / wrong domain:** motor dataset; do not train on that data for growbox
- **Parameters or formulas to extract:** hybrid gray-box idea (physics structure + learned coeffs)
- **Maps to our sim:** optional later path: fixed structure (chamber + 4 pots) + learn loss/conductance from real box logs
- **Notes:** Valuable **after** we have a white-box sim and replay data — calibration / residual learning.

### S07 — OCHRE (NREL residential energy)

- **URL:** https://github.com/NatLabRockies/OCHRE (also published as `ochre-nrel`)
- **Local:** `third_party/OCHRE/` (~200 MB shallow clone — heavy)
- **License:** see `LICENSE` in clone
- **What it models well:**
  - Residential building + **HVAC**, water heater, DER flexibility
  - High-resolution thermal/electrical load interactions
- **What to ignore / wrong domain:** whole-home energy, EV/PV/battery, utility co-sim — far from growbox
- **Parameters or formulas to extract:** HVAC actuator → zone air T control patterns; comfort constraints thinking
- **Maps to our sim:** loosely heater/cooler/dehumidifier as “zone HVAC”; not soil/irrigation
- **Notes:** Low priority unless we need HVAC control scheduling patterns. Prefer S03/S04 for climate ODE.

### S08 — pyBuildingEnergy (EURAC)

- **URL:** https://github.com/EURAC-EEBgroup/pyBuildingEnergy
- **Local:** `third_party/pyBuildingEnergy/`
- **License:** see `LICENSE.md` in clone
- **Standard:** ISO 52016-1:2018 hourly heating/cooling need, internal T
- **What it models well:**
  - Building envelope energy need (sensible heating/cooling)
  - Hourly internal temperature calculation
- **What to ignore / wrong domain:** EPBD building compliance; large building envelopes; no plant physiology
- **Parameters or formulas to extract:** hourly energy balance bookkeeping; U-value / thermal mass style terms
- **Maps to our sim:** chamber energy need vs outside; insulation (`heat_loss_w_per_k`) intuition
- **Notes:** Useful for *envelope* terms only. Growbox is closer to a small climate chamber than an apartment.

---

## Papers / articles / books

### S02 — iGrow: Autonomous Greenhouse Control (AAAI 2022)

- **Link / DOI:** https://arxiv.org/abs/2107.05464 · https://doi.org/10.48550/arXiv.2107.05464
- **Local PDF:** `third_party/papers/igrow-2107.05464.pdf` (after fetch script)
- **Key ideas:**
  - Formulates autonomous greenhouse control as **MDP**
  - Neural network simulator of full planting process (tomato pilot) as testbed for control
  - Bi-level optimization with real-world data feedback
  - Real greenhouse: +10% yield / large profit vs experts (paper claim)
- **Assumptions:** large autonomous greenhouse, high-dim sensors, cloud AI — not a small hobby growbox
- **Maps to our sim:** architecture of *sim as training env for control policy*; less direct for lumped ODE coeffs
- **Notes:** Use for **pipeline philosophy** (sim → optimize control), not as primary physics source. Prefer S03/S04 for equations.

---

## Product / hobby tools

### S01 — LetsGrow Greenhouse simulation models (GPE)

- **URL:** https://gpe.letsgrow.com/
- **License / terms:** educational interactive models (LetsGrow.com); not open source
- **Modules:**
  1. Moisture discharge (fan + outdoor air → moisture removal)
  2. Moisture transport (leaf → roof; diffusion vs air movement)
  3. Energy consumption (outside conditions + U-value)
  4. Energy screens
  5. Ventilation rate (T, RH setpoints vs required vent and CO₂ efficiency)
- **What to extract:** qualitative couplings and order-of-magnitude checks (e.g. fan moisture dump, vent vs CO₂)
- **Maps to our sim:** fan · outside T/RH · leak/ACH · humidity balance · CO₂ dilution
- **Notes:** Psychrometric chart at sea-level pressure. Do **not** scrape/port their code — re-derive from first principles + S03/S04.

---

## Datasets / logs from our hardware

| File / session | Conditions | Useful signals | Notes |
|----------------|------------|----------------|-------|
| | | | |

---

## Physics topics checklist

- [x] Chamber energy balance — **S04** primary, S01 secondary
- [x] Moisture balance / psychrometrics — **S01**, S04 `sat_conc`, S03 humidity fluxes
- [x] Latent heat of evaporation — **S04** `H_fg`, S03 transp
- [ ] Substrate water content dynamics — *gap* (neither repo is soil-moisture-first for pots)
- [ ] Per-pot irrigation impulse — *gap* (ours must invent; calibrate later)
- [x] Root-zone / mat temperature — **S04** growing medium + tray nodes
- [ ] Nutrient tank heater — *gap*
- [x] Fan + leak exchange with outside — S03 vents, S04 `R_a_max`, S01
- [x] CO₂ dosing / dilution — S03/S04 (dosing weak in demos; dilution strong)
- [x] Lamp / solar heat — **S04** solar radiation; map to our `lights_active` heat W
- [ ] Cooler / dehumidifier / humidifier maps — *gap* (add actuator efficiency tables later)
- [x] Time constants / integration — S03 Euler/RK4; S04 BDF/ode
- [x] Typical dimensions / power — rescale from S04 geometry; our contract ranges

---

## Decision log

| Date | Decision | Rationale | Sources |
|------|----------|-----------|---------|
| 2026-07-16 | Store research under `third_party/` (not bare `vendor/`) | clearer: study-only external code | — |
| 2026-07-16 | Prefer S03+S04 for equations; S01 qualitative; S02 control framing | license + fidelity fit | S01–S04 |
| 2026-07-16 | S03 (mpcrl-greenhouse): **use OK with attribution** | authors granted permission if cited in sources | S03 |
| 2026-07-16 | Add S05–S08 thermal/building method repos | LPTN toolkit + HVAC/ISO methods | S05–S08 |
| 2026-07-16 | Write FORMULAS.md + SLOT_MAP.md from S03/S04 | extract ODEs and actuator mapping | S03, S04 |

---

## Out of scope for v4 training sim

- CFD / full 3D airflow
- PPFD / spectrum as ML features
- Full tomato crop growth economics (optional later)
- Multi-hectare greenhouse optimization stacks

See also: [PHYSICS_SCOPE.md](PHYSICS_SCOPE.md), [IO_INVENTORY.md](IO_INVENTORY.md).
