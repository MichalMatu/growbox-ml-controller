# Growbox hardware configurator (FE line)

This branch is a **sparse worktree** for the web hardware configurator.

## What stays here

| Path | Role |
|------|------|
| `schemas/environment-controller.json` | Contract **v4** — single shared SSOT with monorepo / board / ML |
| `docs/SCHEMA_V4_FIELD_GUIDE.md` | Field meanings (PL) |
| `docs/HARDWARE_CONFIGURATOR.md` | Product assumptions |
| `docs/DATA_CONTRACT.md` | Short contract rules |
| `AGENTS.md` | Rules for FE work on this branch |
| `LICENSE` | License |

Everything else from `main` (firmware, panel, simulator, twin, tests, …) is **intentionally absent** on this branch.

## Not for wholesale merge into `main`

Do **not** merge this branch as a replace of `main` — it would delete product code.  
Ship FE by adding files under e.g. `web/` then PR **those paths** (or cherry-pick) onto `main`.

## Next

1. Scaffold frontend (framework TBD).  
2. Edit / export JSON shaped by schema v4.  
3. Backend / train / board later — not here yet.
