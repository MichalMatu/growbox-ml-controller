# Integration convergence plan

This document defines a non-destructive path for converging the experimental product lines in this repository.

## Safety rule

Do not delete, force-push, squash, or rewrite any source branch until the convergence branch is validated and the archived snapshots below have been checked.

Snapshot branches created on 2026-08-21:

- `archive/2026-08-21-main-baseline` — exact snapshot of `main`
- `archive/2026-08-21-sku-v1` — exact snapshot of `feature/sku-v1`
- `archive/2026-08-21-sim-twin-pyvista` — exact snapshot of `feature/sim-twin-pyvista`
- `archive/2026-08-21-configurator-v5` — exact snapshot of `feature/growbox-config-v4-docs`
- `archive/2026-08-21-pages-live` — exact snapshot of the currently deployed `gh-pages`
- `archive/pre-squash-history` — existing full history retained from before the v1 baseline squash

The working convergence branch is:

- `integration/convergence-2026-08`

It starts from `feature/sim-twin-pyvista`, because that line already contains the `feature/sku-v1` history plus the later simulator, calibration, profile and PyVista twin work.

## Product lines to preserve

### Firmware / controller baseline

Source: `main`

Preserve the ESP-IDF application, portable C++ controller, generated model runtime, deterministic safety supervisor, UART/NDJSON demo protocol, host tests, Python ML pipeline, board profiles and existing documentation.

### Simulator / calibration / scientific twin

Source: `feature/sim-twin-pyvista`

Preserve calibration tools, deviations/foresight work, GrowboxProfile, PyVista scientific twin, scene/profile tests and related simulator documentation.

### Hardware configurator / browser 3D chamber

Source: `feature/growbox-config-v4-docs`

This is a sparse frontend line and must NOT be merged wholesale because it intentionally removes firmware/product files. Preserve selectively:

- `web/**`
- the schema/configurator docs that are still relevant
- contract validation/gate tooling where useful
- deployment configuration only after replacing branch-specific assumptions

The browser frontend currently contains both the schema-driven JSON configurator and `/chamber-3d` React Three Fiber view.

### Deployed Pages artifact

Source: `gh-pages`

Treat as generated output, not a source branch. Keep the 2026-08-21 archive snapshot until a replacement Pages pipeline from the converged source has been validated externally.

## Known contract split

Do not silently reconcile this during cleanup.

- `main` firmware/controller line currently uses the v4 contract (4 pots, 128 features, 15 outputs).
- the configurator line has evolved to v5 (up to 9 pots, 228 features, 25 outputs), although some branch/file names and README text still say v4.

This mismatch is architectural/product work, not repository cleanup. Keep both states recoverable and label them accurately until a deliberate migration is performed.

## Current preservation inventory

This table records what has already been carried into the convergence branch and what must remain recoverable before source branches can be removed.

| Source / artifact | Status in convergence | Deletion disposition |
|---|---|---|
| `main` firmware/controller tree | Preserved because the twin line descends directly from the v1 baseline | Keep source until full validation; dated snapshot exists |
| `feature/sku-v1` | Fully contained in `feature/sim-twin-pyvista`, therefore also contained in convergence history | Candidate for deletion only after convergence is accepted; dated snapshot exists |
| `feature/sim-twin-pyvista` | Convergence branch is a direct descendant; no history was reconstructed or flattened | Candidate for deletion only after convergence is accepted; dated snapshot exists |
| `web/**` from configurator line | Imported into convergence without merging sparse-branch deletions | Source remains until final web/Pages validation; dated snapshot exists |
| configurator schema v5 | Preserved as `web/schema/environment-controller.v5.json` | Do not replace root firmware v4 schema until an explicit migration |
| configurator golden export | Preserved as `web/schema/examples/minimal-single-pot.v5.json` and used by web tests | Source copy may become redundant after validation; dated snapshot exists |
| current firmware schema v4 | Remains at `schemas/environment-controller.json` unchanged | Required until deliberate firmware contract migration |
| `docs/HARDWARE_CONFIGURATOR.md` on sparse branch | Historically useful design notes, but contains stale v4 assumptions | Preserve in `archive/2026-08-21-configurator-v5`; do not copy as current authority without rewriting |
| `docs/SCHEMA_V4_FIELD_GUIDE.md` on sparse branch | Legacy v4 field guide; conflicts with current web v5 dimensions | Preserve in archive as historical material; do not expose as current v5 documentation |
| `gate/check-contract.mjs` + tests | Valuable independent contract-validator logic, but mixed stale v4 names/comments with actual v5 checks and branch-specific root paths | Keep recoverable in archive; decide later whether to port cleanly under `web/` after CI convergence |
| branch-specific root `AGENTS.md` / root pnpm gate | Sparse-branch operating rules, not safe as monorepo root authority | Preserve in archive; selectively port only rules still valid for converged tree |
| configurator deployment workflow | Branch-specific publisher to `gh-pages` | Keep current deployment unchanged until candidate deployment is verified |
| `gh-pages` generated tree | Current externally verified live build | Keep live plus dated snapshot until replacement deployment is proven |

A source feature branch may be deleted later even when historical notes remain only in a dated archive branch; the archive is deliberately the lossless recovery layer. The active tree should not be polluted with stale documentation merely to make a feature branch deletable.

## Convergence order

1. Keep all source branches and archive snapshots untouched.
2. Use `integration/convergence-2026-08` as the only convergence workspace.
3. Validate the simulator/twin line against its existing tests before importing frontend work.
4. Import the configurator frontend selectively; never merge its sparse branch as a whole.
5. Keep firmware v4 and frontend v5 boundaries explicit until a deliberate schema migration is designed.
6. Add/repair documentation and live-demo links only after the source layout is stable.
7. Build/test firmware, host C++, Python ML/simulator and frontend independently.
8. Deploy a candidate Pages build without deleting the current `gh-pages` history/snapshot.
9. Verify both `/` and `/chamber-3d` externally.
10. Only after all validation passes, decide which feature branches are redundant and may be deleted. Archive snapshots remain available until a later explicit cleanup decision.

## Definition of done before deleting source branches

- firmware build passes for intended ESP32-S3 profile(s)
- portable C++ host tests pass
- Python tests for ML/simulator/profile/twin pass
- frontend typecheck, lint, tests and production build pass
- JSON configurator imports/exports the intended schema correctly
- `/chamber-3d` works from the final Pages URL
- README describes the actual architecture and contract versions without stale feature/output counts
- every useful source-only artifact has an explicit disposition in the preservation inventory
- archive snapshots are confirmed present

Until every relevant item above is true, no historical/product branch is considered disposable.
