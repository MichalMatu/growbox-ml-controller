# Scientific 3D twin view (PyVista)

**Not a game. Not CFD.** A visual layer on top of the existing lumped growbox simulator.

| Layer | Role |
|-------|------|
| `tools/ml/simulator.py` | Physics (Van Henten + pots) |
| `tools/ml/twin_scene.py` | Geometry + exchange glyphs (no PyVista import) |
| `tools/ml/twin_view.py` | PyVista rendering / CLI |

## What you see

- **Chamber box** — size from `growbox_volume_m3`; color ∝ air **T**; opacity ∝ **RH**
- **Pots** — up to 4 cylinders; color ∝ **soil moisture**
- **Outside climate** — only in HUD text (`outside T` / `RH`), no separate mesh
- **INLET / OUTLET** — two **round wall openings** (rings) on opposite faces; no fan tube mesh
- **Arrows** — only when fan is ON: air **in** at inlet, **out** at outlet
- **Pots** — stocky cylinder; **one active pot is centered** on the floor

Arrows are **illustrative** (port flow / fan command), not CFD.

**Walls vs ports (physics honesty):**

| Through walls | Through inlet / outlet |
|---------------|-------------------------|
| Heat conduction / insulation (`heat_loss`, thermal mass) | **Air** exchange (fan + openings) |
| No bulk airflow drawn as wall arrows | Arrows only when fan drives ports |

Small seal leaks may exist in the ODE (`air_leak_rate_ach`) but are **not** visualized as “air through walls”.

## Install

PyVista is an **optional** dependency (keeps default CI light):

```bash
pip install pyvista
# or from project root:
pip install -e '.[twin]'
```

Headless screenshot may need a virtual framebuffer on Linux (`xvfb-run`) or `PYVISTA_OFF_SCREEN=true`.

## Commands

```bash
# Summary only (no GUI, no PyVista needed for twin_scene tests)
python -m tools.ml.twin_view --steps 30 --fan 0.8 --heater 0.2

# Offline PNG
python -m tools.ml.twin_view --steps 40 --fan 1 --outside-temperature-c 8 \
  --screenshot build/twin-fan.png

# Interactive window after a rollout
python -m tools.ml.twin_view --steps 20 --heater 1 --interactive

# Live 3D (keyboard only — VTK sliders crash on some macOS builds)
python -m tools.ml.twin_view --live
```

### Live keys

| Key | Action |
|-----|--------|
| `s` / space | step simulator (10 s) |
| `r` | reset |
| `1` / `2` | heater on / off |
| `3` / `4` | fan on / off |
| `5` / `6` | humidifier on / off |
| `h` / `H` | heater ±0.25 |
| `f` / `F` | fan ±0.25 |
| `u` / `U` | humidifier ±0.25 |
| `7` | camera isometric |
| `8` | camera top |
| `9` | camera front |
| `0` | camera side |
| orientation cube (UR) | drag faces like Fusion 360 |


## Honest limits

1. Single air node → one chamber color, not a T field on a mesh.
2. Fan glyphs are through-flow heuristics along +X, not measured duct geometry.
3. For a true digital twin: calibrate scalars first ([CALIBRATION.md](CALIBRATION.md)), then drive this view from live sensors.

## Related

- Physics: [PHYSICS_SCOPE.md](PHYSICS_SCOPE.md), [VALIDATION.md](VALIDATION.md)
- Deviations / foresight: `tools/ml/deviations.py`, `foresight.py`
