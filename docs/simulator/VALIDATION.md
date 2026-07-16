# Simulator validation (open-loop probe)

**Tool:** `python -m tools.ml.probe_simulator`
**Last run:** 10/10 checks passed (see `build/sim-probe/summary.json` locally after probe).

This is **not** ML training. It is a directional physics gate: heater heats, fan cools toward cold outside, irrigation wets soil, wet pots humidify more, etc.

## How to re-run

```bash
python -m tools.ml.probe_simulator --save-series --out-dir build/sim-probe
# optional CI-style exit code
python -m tools.ml.probe_simulator || echo "probe failed"
```

## Checklist results (human review)

| Check | Verdict | Notes |
|-------|---------|--------|
| Heater vs idle | **OK** | ΔT heat ≈ +2.5 °C / 10 min; idle cools toward outside |
| Fan + cold outside | **OK** | Final T fan < sealed (~24 vs ~26 °C from 28 °C) |
| Irrigation soil | **OK** | Soil 35 → ~59 % with pulses |
| Irrigation RH | **OK-ish** | ΔRH ~20–25 pp after scale fix; still strong for small volume |
| Wet > dry humidify | **OK** | ΔRH wet ~19 vs dry ~8 over ~8 min |
| Heat mat | **OK** | Soil +0.5 °C vs flat idle in 40×60 s |
| CO₂ doser | **OK** | 600 → ~1080 ppm with pulsed dose, fan 0 |
| Lights heat | **OK** | Lit warmer than dark with heater off |
| Humidifier | **OK-ish** | 40 → ~86 % in 5 min at 150 g/h nameplate × 0.55 delivery |
| Mixed bounds | **OK** | No NaN; T/RH/CO₂/soil in physical ranges |
| Determinism | **OK** | Bit-identical trails for same seed |

## Scale judgment (honest)

- **Directions** match growbox intuition → safe enough to train a teacher against.
- **Magnitudes** are still **synthetic**: Van Henten scales come from a commercial greenhouse model mapped into a ~0.8 m³ box; RH capacity is a lumped 20 g/m³ span, not full psychrometrics.
- CO₂ jumps of hundreds of ppm per few pulses are consistent with a high `dose_ppm_per_full_pulse` capability (80–120), not a bug.
- Next calibration should use **real NDJSON** from your box (heater on duration vs ΔT, one irrigation pulse vs RH/soil).

## What is good enough for ML next step

| Use | Ready? |
|-----|--------|
| Teacher rollouts / open-loop cost | **Yes** (directional couplings present) |
| Production climate controller from this sim alone | **No** — needs real-box coefficient fit |
| Unit / regression probe in CI | **Yes** (`probe_simulator` exit code) |

## Related

- Physics: `tools/ml/physics/{van_henten,pots_substrate,actuators}.py`
- Formulas: [FORMULAS.md](FORMULAS.md), [SLOT_MAP.md](SLOT_MAP.md)
