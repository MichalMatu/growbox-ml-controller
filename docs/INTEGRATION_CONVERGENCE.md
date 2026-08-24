# Repository convergence and cleanup

The repository has already converged onto `main`. Cleanup must preserve recoverability while removing redundant active branches and stale planning material.

## Current source of truth

- `main` — active product/development branch.
- `gh-pages` — generated deployment branch; keep while GitHub Pages depends on it.
- `agent-control` — operational branch used by the repository agent; keep while that workflow is in use.

The old integration branch `integration/convergence-2026-08` is no longer the intended development line. `main` contains the converged firmware, simulator/twin, browser configurator and lab panel.

## Legacy UI that must be preserved

`tools/panel/` is the older Growbox ML laboratory dashboard / JSON scenario configurator. It is intentionally retained in `main`.

The file `tools/panel/static/index.html` in `main` is byte-for-byte the same Git blob as in `feature/sim-twin-pyvista` (`76713f4aa1a43658313826acf713fd2037613343`). Deleting the redundant feature branch therefore does not remove this dashboard.

The newer React configurator remains under `web/`, including the v5 schema snapshot in `web/schema/environment-controller.v5.json`.

## Redundant feature branches

Each branch below has an exact archive snapshot and can be treated as redundant after this cleanup branch is reviewed:

| Feature branch | Exact archive snapshot |
|---|---|
| `feature/sku-v1` | `archive/2026-08-21-sku-v1` |
| `feature/sim-twin-pyvista` | `archive/2026-08-21-sim-twin-pyvista` |
| `feature/growbox-config-v4-docs` | `archive/2026-08-21-configurator-v5` |

The archive comparisons are identical at the commit level.

## Archive branches to keep for now

- `archive/2026-08-21-main-baseline`
- `archive/2026-08-21-sku-v1`
- `archive/2026-08-21-sim-twin-pyvista`
- `archive/2026-08-21-configurator-v5`
- `archive/2026-08-21-pages-live`
- `archive/pre-squash-history`

These are recovery points, not active development branches. They can be reconsidered later after the new architecture and ML contract stabilize.

## Contract state

Do not mix repository cleanup with the ML redesign:

- firmware/controller currently uses schema v4: 4 pots, 128 features, 15 outputs;
- browser tooling carries schema v5: up to 9 pots, 228 features, 25 outputs;
- the next ML architecture may replace this with smaller stateless contracts, but that is a separate product change.

## Cleanup performed on `cleanup/repository-2026-08`

- removed root `continue_test.md` — old machine/audit handoff notes;
- removed `docs/plan.md` — obsolete v2 planning document that conflicts with the current v4/v5 state;
- retained both `tools/panel/` and `web/`;
- reduced this document to the current repository state.

Historical copies of removed material remain recoverable from existing archive/history branches.
