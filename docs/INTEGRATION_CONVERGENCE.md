# Repository convergence and cleanup

> **Historical cleanup note:** this document records the repository convergence/branch cleanup. For the current climate-v6 runtime architecture and active development branch, use [CURRENT_STATUS.md](CURRENT_STATUS.md).

The repository has converged onto `main`. Repository cleanup must preserve the two user interfaces and the useful historical recovery points while removing redundant branch names and stale planning material.

## Current source of truth

- `main` — active product/development branch.
- `gh-pages` — generated deployment branch; keep while GitHub Pages depends on it.
- `agent-control` — operational branch used by the repository agent; keep while that workflow is in use.

## User interfaces that must remain

Both interfaces are intentional and must be preserved:

- `tools/panel/` — older Growbox ML laboratory dashboard / JSON scenario configurator used with the Python/serial tooling.
- `web/` — newer React/Vite configurator and `/chamber-3d` UI.

The legacy panel is already preserved on `main`. `tools/panel/static/index.html` has the same Git blob as the version from `feature/sim-twin-pyvista` (`76713f4aa1a43658313826acf713fd2037613343`).

The remaining useful fix from `integration/convergence-2026-08` (`Fix chamber 3D room layout reset`) has also been carried into `main`.

## Branches intended to remain

After branch cleanup the intended branch set is:

- `main`
- `gh-pages`
- `agent-control`
- `archive/pre-squash-history` — disconnected pre-squash history; keep as the long-term historical recovery point.
- `archive/2026-08-21-configurator-v5` — keep one snapshot of the old sparse configurator line because that branch had independent history not represented linearly in `main`.

## Redundant branches safe to remove

These branch names are redundant after the completed convergence and preservation checks:

- `cleanup/repository-2026-08` — merged cleanup work.
- `integration/convergence-2026-08` — its remaining useful 3D reset fix is now in `main`.
- `feature/sku-v1` — fully contained in the history leading to `main`.
- `feature/sim-twin-pyvista` — fully contained in the history leading to `main`; the legacy dashboard is preserved on `main`.
- `feature/growbox-config-v4-docs` — exact snapshot remains as `archive/2026-08-21-configurator-v5`.
- `archive/2026-08-21-main-baseline` — historical ancestor already reachable from `main`.
- `archive/2026-08-21-sku-v1` — duplicate recovery name for work already reachable from `main`.
- `archive/2026-08-21-sim-twin-pyvista` — duplicate recovery name for work already reachable from `main`.
- `archive/2026-08-21-pages-live` — identical to the current `gh-pages` tip at the time of cleanup.

## Cleanup completed on `main`

- removed root `continue_test.md` — old machine/audit handoff notes;
- removed `docs/plan.md` — obsolete v2 planning document;
- removed `docs/REPO.md` — obsolete branch guide;
- fixed `Makefile` so `schema-check` calls the existing `scripts/check_schema.sh`;
- retained both `tools/panel/` and `web/`;
- preserved the chamber 3D room-layout reset fix from the former integration line.


## Contract state

The convergence history includes legacy firmware schema v4 and browser schema v5. New climate
runtime development targets schema v6 (`climate-mvp-v1`, 44 features, 6 ML-controlled climate
outputs). The preserved legacy demo is intentionally not silently rewritten to v6. See
`CURRENT_STATUS.md` for the live migration state.
