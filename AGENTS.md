# Agent notes — Growbox hardware configurator (FE)

## Branch is sparse

Tracked content is essentially:

- `schemas/environment-controller.json` — **only shared SSOT** with board / ML / `main`
- `docs/` — contract rules, field guide, product assumptions, **examples/**
- `AGENTS.md`, `README.md`, `LICENSE`, `.gitignore`

**Absent by design:** ESP firmware, board admin panel, simulator, twin, teacher, train, monorepo tests/CI scripts.

Full product code: checkout **`main`**.

### Merge policy

- **Never** merge this sparse branch wholesale into `main` (would delete the product tree).
- Land work by adding FE sources (e.g. `web/**`) and PR/cherry-pick **only those paths** (+ docs/schema updates).
- Do not re-commit monorepo trees (`tools/`, `src/`, `tests/`, …) onto this branch.

## Goal

Web **hardware configurator**: client describes installed growbox gear in **v4** terms → **download JSON**.  
No backend required for MVP. Framework not mandated yet.

## SSOT (read before coding)

| Topic | File |
|-------|------|
| Paths, min/max/default, 128 features, 15 outputs | `schemas/environment-controller.json` |
| Path meanings + export rules | `docs/SCHEMA_V4_FIELD_GUIDE.md` |
| Product layers (hardware vs seed vs previous) | `docs/HARDWARE_CONFIGURATOR.md` |
| Short contract rules | `docs/DATA_CONTRACT.md` |
| Golden export shape | `docs/examples/minimal-single-pot.json` |
| Export checklist | `docs/examples/README.md` |

## Implementation rules

1. **Paths English** (`pots[0].irrigation.available`). UI copy may be Polish.
2. **Mix & match:** missing gear → `validity=false` / `available=false` — **never delete slots**; always **4 pots**.
3. Inactive pot export: soil validity false; irr/mat available false; numeric limits **0**; previous **0**.
4. Inactive actuator export: `available=false` and zero max power/flow/dose (and efficiency 0 where used).
5. **No** `actuators.lights` in JSON. Lights schedule = `pseudo.lights_active` only.
6. **No** global `actuators.*.control_type` — not in v4 feature list. Pot irr/mat: only `"binary"` \| `"pwm"`.
7. Numbers: clamp to schema min/max for that `path`.
8. Meta keys allowed: `seed`, `profile_id`, `title` (not ML features).
9. Prefer form state keyed by **path** string.
10. Schema change that adds/renames ML slots = **breaking** → do on `main` with version bump + regen; document first.
11. Code and commit messages: English. User-facing chat: Polish.
12. Backend / serial / train UI: out of scope unless explicitly requested.

## Suggested UI groups

1. Chamber — `environment.*`  
2. Sensors — `sensors.*` + `validity.*`  
3. Pots 1–4 — full pot object  
4. Outputs — `actuators.*`  
5. Pseudo — `lights_active`  
6. Targets / previous — defaults OK for MVP  

## Definition of done (MVP export)

Export deep-equals structure of `docs/examples/minimal-single-pot.json` (same keys/layers; values may differ) and passes the checklist in `docs/examples/README.md`.
