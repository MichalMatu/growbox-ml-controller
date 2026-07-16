# Extracted formulas (S03 Van Henten / mpcrl + S04 GES)

**Status:** research extract for implementing our training simulator.
**Not** drop-in code — re-implement under our MIT tree; **cite sources**.

| ID | Source | Local path | Cite |
|----|--------|------------|------|
| S03 | mpcrl-greenhouse (Van Henten 1994 model) | `third_party/mpcrl-greenhouse/greenhouse/model.py` | Mallick et al. 2025; used with authors’ permission + attribution |
| S04 | EECi/GES | `third_party/GES/python/{functions,parameters}.py` | EECi Cambridge; GDGCM / Vanthoor lineage; MIT |

Companion: [SLOT_MAP.md](SLOT_MAP.md) (S03/S04 ↔ our contract). Full catalog: [SOURCES.md](SOURCES.md).

Refresh clones: `bash scripts/fetch_third_party.sh`

---

## 1. Van Henten / mpcrl-greenhouse (S03)

### 1.1 State, input, disturbance

From `LettuceGreenHouse` (`env.py`): `nx=4`, `nu=3`, `nd=4`, default `ts = 15 min`.

| Symbol | Index | Meaning (model convention) | Typical unit |
|--------|------:|----------------------------|--------------|
| \(x_0\) | 0 | crop dry weight (lettuce) | kg/m² (internal; output ×1e3) |
| \(x_1\) | 1 | indoor CO₂ concentration (mass-related state) | model units |
| \(x_2\) | 2 | indoor air temperature | °C |
| \(x_3\) | 3 | indoor absolute humidity (related state) | model units |
| \(u_0\) | 0 | CO₂ supply rate | [0, 1.2] (model scale; `get_u_max`) |
| \(u_1\) | 1 | ventilation | [0, 7.5] |
| \(u_2\) | 2 | heating | [0, 150] |
| \(d_0\) | 0 | outdoor radiation / light-related disturbance | |
| \(d_1\) | 1 | outdoor CO₂ | |
| \(d_2\) | 2 | outdoor temperature | |
| \(d_3\) | 3 | outdoor humidity | |

Outputs \(y = \mathrm{output}(x)\) (engineering units): yield-related, CO₂ ppm-like, T [°C], RH [%] (see `Model.output`).

Parameters: physical scales in `Model.p_scale` (length 28); normalized multipliers \(p_i\) with true model \(p_i = 1\).

### 1.2 Auxiliary fluxes

Let \(p_i^\* = p_i \cdot p_{\mathrm{scale},i}\).

**Photosynthesis helper** \(\psi\):

\[
\psi(x,d,p) = p_3^\*\, d_0 + \bigl(-p_4^\*\, x_2^2 + p_5^\*\, x_2 - p_6^\*\bigr)\,(x_1 - p_7^\*)
\]

**CO₂ photosynthetic flux** \(\phi_{\mathrm{phot},c}\):

\[
\phi_{\mathrm{phot},c}
=
\frac{
\bigl(1 - e^{-p_2^\* x_0}\bigr)\,
p_3^\*\, d_0\,
\bigl(-p_4^\* x_2^2 + p_5^\* x_2 - p_6^\*\bigr)\,
(x_1 - p_7^\*)
}{\psi(x,d,p)}
\]

**Ventilation of CO₂** \(\phi_{\mathrm{vent},c}\):

\[
\phi_{\mathrm{vent},c}
=
\bigl(u_1\cdot 10^{-3} + p_{10}^\*\bigr)\,(x_1 - d_1)
\]

**Ventilation of humidity** \(\phi_{\mathrm{vent},h}\):

\[
\phi_{\mathrm{vent},h}
=
\bigl(u_1\cdot 10^{-3} + p_{10}^\*\bigr)\,(x_3 - d_3)
\]

**Transpiration → humidity** \(\phi_{\mathrm{transp},h}\):

\[
\phi_{\mathrm{transp},h}
=
p_{20}^\*\,
\bigl(1 - e^{-p_2^\* x_0}\bigr)\,
\left(
\frac{p_{21}^\*}{p_{22}^\*(x_2 + p_{23}^\*)}
\exp\!\left(\frac{p_{24}^\* x_2}{x_2 + p_{25}^\*}\right)
- x_3
\right)
\]

### 1.3 Continuous dynamics \(\dot x = f(x,u,d,p)\)

\[
\begin{aligned}
\dot x_0 &= p_0^\*\,\phi_{\mathrm{phot},c}
  - p_1^\*\, x_0\, 2^{x_2/10 - 5/2} \\[0.4em]
\dot x_1 &= \frac{p_8}{p_{\mathrm{scale},8}}
  \bigl(
    -\phi_{\mathrm{phot},c}
    + p_9^\*\, x_0\, 2^{x_2/10 - 5/2}
    + u_0\cdot 10^{-6}
    - \phi_{\mathrm{vent},c}
  \bigr) \\[0.4em]
\dot x_2 &= \frac{p_{15}}{p_{\mathrm{scale},15}}
  \bigl(
    u_2
    - \bigl(p_{16}^\*\, u_1\cdot 10^{-3} + p_{17}^\*\bigr)\,(x_2 - d_2)
    + p_{18}^\*\, d_0
  \bigr) \\[0.4em]
\dot x_3 &= \frac{p_{19}}{p_{\mathrm{scale},19}}
  \bigl(
    \phi_{\mathrm{transp},h} - \phi_{\mathrm{vent},h}
  \bigr)
\end{aligned}
\]

### 1.4 Discretization

- Euler: \(x_{k+1} = x_k + t_s\, f(x_k,u_k,d_k,p)\)
- RK4: `Model.rk4_step` (optional substeps)
- Env default \(t_s = 900\,\mathrm{s}\) (15 min). Our training often uses \(10\,\mathrm{s}\) — must re-tune / substep.

### 1.5 `p_scale` table (physical constants)

From `Model.p_scale` (index → value). Semantic names are conventional Van Henten / this repo usage (not always labeled in code).

| i | `p_scale[i]` | Role (short) |
|--:|-------------:|--------------|
| 0 | 0.544 | crop growth / phot efficiency scale |
| 1 | 2.65e-7 | respiration scale |
| 2 | 53 | LAI / canopy extinction scale in exp |
| 3 | 3.55e-9 | light × phot term |
| 4–6 | 5.11e-6, 2.3e-4, 6.29e-4 | quadratic T effect on phot |
| 7 | 5.2e-5 | CO₂ compensation-like offset |
| 8 | 4.1 | CO₂ capacity / scale |
| 9 | 4.87e-7 | respiration → CO₂ |
| 10 | 7.5e-6 | leakage ventilation base |
| 11 | 8.31 | gas constant-like in output RH/CO₂ |
| 12 | 273.15 | °C ↔ K |
| 13 | 101325 | atmospheric pressure [Pa] |
| 14 | 0.044 | molar mass CO₂ [kg/mol] |
| 15 | 3e4 | thermal capacity scale (air) |
| 16 | 1290 | heat exchange × vent |
| 17 | 6.1 | heat loss / leak |
| 18 | 0.2 | solar → heat |
| 19 | 4.1 | humidity capacity scale |
| 20 | 0.0036 | transpiration rate scale |
| 21–25 | 9348, 8314, 273.15, 17.4, 239 | Magnus-like sat. vapour terms |
| 26–27 | 17.269, 238.3 | RH output conversion |

**Use in our sim:** port structure of \(\dot x_1,\dot x_2,\dot x_3\) for chamber CO₂ / T / humidity; **drop or optional** \(\dot x_0\) crop dry weight for v1 training.

---

## 2. GES — Greenhouse Energy Simulation (S04)

Based on GDGCM + Vanthoor-style crop modules. **Unheated glasshouse demo** geometry: \(A_f=250\,\mathrm{m}^2\), \(V=1000\,\mathrm{m}^3\). Rescale to growbox.

### 2.1 State vector \(z\) (21 components)

| Index | Symbol | Meaning |
|------:|--------|---------|
| 0 | \(T_c\) | cover temperature [K] |
| 1 | \(T_i\) | **internal air** temperature [K] |
| 2 | \(T_v\) | vegetation temperature [K] |
| 3 | \(T_m\) | **growing medium / mat** temperature [K] |
| 4 | \(T_p\) | tray temperature [K] |
| 5 | \(T_f\) | floor temperature [K] |
| 6–9 | \(T_{s1..4}\) | soil layers [K] |
| 10–11 | \(T_{v,\mathrm{mean}}, T_{v,\mathrm{sum}}\) | crop T filters [K / °C·d] |
| 12 | \(C_w\) | **air moisture content** [kg/m³] |
| 13 | \(C_c\) | **air CO₂ mass concentration** [kg/m³] |
| 14–17 | \(C_{\mathrm{buf,fruit,leaf,stem}}\) | crop C pools |
| 18–20 | \(R_{\mathrm{fruit,leaf,stem}}\) | growth rates |

Public climate sensors for us map mainly to \(T_i\), RH from \(C_w\) + sat, \(C_c\) → ppm, \(T_m\) → soil/mat T.

### 2.2 Building-block transfers

**Convection** (sensible + latent-like):

\[
\mathrm{Gr} = \frac{g\, d^3}{T_1 \nu^2}|T_1-T_2|,\quad
\mathrm{Re} = \frac{u_{\mathrm{air}} d}{\nu}
\]

\[
Q_V = A\, \mathrm{Nu}\, \lambda \frac{T_1-T_2}{d},\quad
Q_P = A\frac{H_{fg}}{\rho c}\frac{\mathrm{Sh}}{\mathrm{Le}}\frac{\lambda}{d}\bigl(C - C_{\mathrm{sat}}(T_2)\bigr)
\]

**Long-wave radiation:**

\[
Q_R = k\, \sigma\, A_1\, F_{12}\,(T_1^4 - T_2^4),\quad
k = \frac{\varepsilon_1\varepsilon_2}{1-\rho_1\rho_2 F_{12}F_{21}}
\]

**Conduction:**

\[
Q_D = \frac{A\,\lambda}{l}(T_1-T_2)
\]

**Saturation moisture content** (`sat_conc`, \(T\) in K, \(T_C=T-273.15\)):

\[
C_{\mathrm{sat}}(T) = e^{11.56 - 4030/(T_C+235)}\,(-0.0046\,T_C + 1.2978)
\]

### 2.3 Ventilation / infiltration

Wind + stack driven crack flow → minimum ACH \(R_{a,\min}\); setpoint boost toward \(R_{a,\max}=30/3600\,\mathrm{s}^{-1}\):

\[
\begin{aligned}
Q_{V,i\rightarrow e} &= R_a\, V\, \rho_i\, c_i\,(T_i - T_{\mathrm{ext}}) \\
Q_{P,i\rightarrow e} &= R_a\, V\, H_{fg}\,(C_w - C_{w,\mathrm{ext}}) \\
\dot m_{w,i\rightarrow e} &= R_a\,(C_w - C_{w,\mathrm{ext}})
\end{aligned}
\]

CO₂ exchange with outside:

\[
\dot m_{c,i\rightarrow e} = R_a\,(C_c - C_{c,e})
\]

Optional CO₂ injection (demo): `added_CO2` during daytime hours.

### 2.4 Core ODEs (climate-relevant)

Capacitances: cover \(A_c c_{d,c}\), air \(V\rho_i c_i\), vegetation \(c_v A_v m_{sd,v}\), mat \(A_m c_m\), …

\[
\begin{aligned}
\frac{dT_c}{dt} &= \frac{1}{A_c c_{d,c}}
  \bigl(Q_{V,i c}+Q_{P,i c}-Q_{R,c f}-Q_{R,c v}-Q_{R,c m}+Q_{V,e c}-Q_{R,c,\mathrm{sky}}+Q_{S,c}\bigr) \\[0.4em]
\frac{dT_i}{dt} &= \frac{1}{V\rho_i c_i}
  \bigl(-Q_{V,i m}-Q_{V,i v}-Q_{V,i f}-Q_{V,i c}-Q_{V,i e}-Q_{V,i p}+Q_{S,i}\bigr) \\[0.4em]
\frac{dT_v}{dt} &= \frac{1}{c_v A_v m_{sd,v}}
  \bigl(Q_{V,i v}-Q_{R,v c}-Q_{R,v m}-Q_{R,v p}+Q_{S,v}^{\mathrm{NIR}}-Q_{T,v i}\bigr) \\[0.4em]
\frac{dT_m}{dt} &= \frac{1}{A_m c_m}
  \bigl(Q_{V,i m}+Q_{P,i m}-Q_{R,m v}-Q_{R,m c}-Q_{R,m p}-Q_{D,m p}+Q_{S,m}^{\mathrm{NIR}}\bigr) \\[0.4em]
\frac{dC_w}{dt} &= \frac{1}{V H_{fg}}
  \bigl(Q_{T,v i}-Q_{P,i c}-Q_{P,i f}-Q_{P,i m}-Q_{P,i p}\bigr)
  - \dot m_{w,i e} + \dot m_{w,\mathrm{dehum}} \\[0.4em]
\frac{dC_c}{dt} &= \dot m_{c,\mathrm{inj}} - \dot m_{c,i e}
  + \frac{M_c}{M_{\mathrm{carb}}}\frac{A_v}{V}(\ldots\text{crop C terms}\ldots)
\end{aligned}
\]

**Transpiration** (Penman-style / stomatal resistance \(r_{st}\)):

\[
Q_{T,v i} = \max\bigl(A_v h_{L,v i}\,(C_{\mathrm{sat}}(T_v)-C_w),\, 0\bigr)
\]

with \(h_{L,v i}\) from LAI, Lewis number, HV convection, \(r_{st}(PAR,T_v,\mathrm{CO}_2,\mathrm{VPD})\).

### 2.5 Key constants (`parameters.py`)

| Symbol | Value | Unit | Use |
|--------|------:|------|-----|
| \(\sigma\) | 5.67e-8 | W/m²/K⁴ | radiation |
| \(c_i\) | 1003.2 | J/kg/K | air heat capacity |
| \(H_{fg}\) | 2.437e6 | J/kg | latent heat |
| \(M_a, M_w, M_c\) | 0.029, 0.018, 0.044 | kg/mol | moist air / CO₂ |
| \(R\) | 8.314 | J/mol/K | gas constant |
| \(R_{a,\max}\) | 30/3600 | 1/s | max ACH |
| \(V, A_f, H\) | 1000, 250, 5 | m³, m², m | **rescale** |
| \(c_m\) | 45050 | J/m²/K | mat thermal capacity (≈25% wet) |
| \(l_m, \lambda_m\) | 0.03 m, 0.5 W/m/K | | mat conduction |

### 2.6 What GES does **not** give us

- Closed-loop **heater / cooler / humidifier** as continuous ML outputs (demo is largely passive + vent + optional CO₂ mass)
- Per-pot **soil moisture %** and irrigation pulses
- Nutrient tank heater

---

## 3. Recommended dynamics for *our* growbox (synthesis)

Minimal **chamber** state for training-grade sim (v1 physics rewrite):

| State | Source of structure |
|-------|---------------------|
| \(T_{\mathrm{air}}\) | S03 \(\dot x_2\) simplified **or** S04 \(dT_i/dt\) reduced |
| \(C_w\) or RH | S04 \(dC_w/dt\) + sat_conc; S03 \(\dot x_3\) as compact alt. |
| \(C_{\mathrm{CO2}}\) / ppm | S03 \(\dot x_1\) or S04 \(dC_c/dt\) without full crop C |
| Per pot \(m_{\mathrm{water},k}\), \(T_{\mathrm{soil},k}\) | **ours** + mat coupling idea from S04 \(T_m\) |

Actuator powers → source terms in energy/moisture/CO₂ ODEs via [SLOT_MAP.md](SLOT_MAP.md).

**Δt:** prefer 10–60 s with Euler/RK4 substeps; do not use 900 s uncritically.

---

## 4. Provenance checklist for implementers

When porting code into `tools/ml/`:

1. Comment: source file + function name + paper/repo.
2. Keep parameter tables with units and original symbol names where possible.
3. S03: attribution to Mallick et al. / mpcrl-greenhouse (permission + citation).
4. S04: attribution to EECi GES (MIT).
5. Do not commit entire OCHRE/pyBuildingEnergy trees; cite if method used later.
