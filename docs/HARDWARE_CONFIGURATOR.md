# Hardware configurator — product assumptions

Normative stack, gate, and export law: **[`AGENTS.md`](../AGENTS.md)**.
If this file conflicts with `AGENTS.md`, **`AGENTS.md` wins**.

## Why this branch exists

Build a **web editor** so a client describes *their* growbox in **contract v4** language and downloads a JSON file.
That file later feeds training / board `load_scenario`.

**Not in this phase:** serial, teacher, in-browser ML, backend auth, full monorepo twin (PyVista).

**In this phase (partial):** isolated R3F visual playground at `/chamber-3d` (parametric tent only — **not** export SSOT, **not** the training twin).

## Sparse tree

| On this branch | On `main` (elsewhere) |
|----------------|------------------------|
| `schemas/environment-controller.json` | Full product: firmware, panel, sim, train, CI |
| `docs/*` | Same schema file as SSOT when updated carefully |
| `gate/`, root `package.json`, `pnpm-lock.yaml` | — |
| `AGENTS.md`, `README.md`, `.gitignore`, `LICENSE` | — |
| `web/**` | Land via PR of those paths only |

**Never merge this sparse branch wholesale into `main`.**

## SSOT

| Layer | File |
|-------|------|
| Contract paths, min/max/default, 128 features, 15 outputs | `schemas/environment-controller.json` |
| Path meanings | `docs/SCHEMA_V4_FIELD_GUIDE.md` |
| Golden export | `docs/examples/minimal-single-pot.json` |
| Agent / stack / gate law | `AGENTS.md` |
| Short contract rules | `docs/DATA_CONTRACT.md` |

## Layers in one JSON file

Do **not** blur layers in the UI.

| Layer | What it is | Configurator MVP |
|-------|------------|------------------|
| **A. Hardware** | Installed gear + limits | **Primary** — `validity`, `available`, max_*, cultivation, pot `control_type` |
| **B. Process seed** | Start sensor readings | Optional; schema defaults or simple start climate |
| **C. Targets** | Setpoints | Optional climate targets; pot soil targets with pot card |
| **D. Previous** | Last commands 0–1 | **0** for clean hardware-template export |
| **E. Meta (root)** | `seed`, `profile_id`, `title`, optional `enclosure` | Not ML features; see `AGENTS.md` |

MVP export = **A solid**, B/C sensible defaults, D all zeros, E as needed (`enclosure` only if UX stores W×D×H).

**Volume rule:** ML uses `environment.growbox_volume_m3` only. If optional root `enclosure` is present, it has exactly `width_cm`, `depth_cm`, `height_cm` and FE derives `width_cm * depth_cm * height_cm / 1_000_000`; export must contain that same m³ value. Never invent `environment.width_cm` without a schema version bump.

## Scope

### In

- UI groups: Chamber → Sensors → Pots → Outputs → Pseudo (field guide).
- FE validation from schema min/max; unavailable pot-module / actuator zeroing rules (`AGENTS.md`).
- Import / export JSON (file, paste, `localStorage`), with reject-on-invalid v4 import and no legacy migration/fallback.
- Load the shared schema statically from `../schemas` (no copied schema, no backend).
- Root checks: `pnpm gate` (contract + web) and `pnpm test:contract` after gate edits.
- Isolated 3D playground: `web/src/pages/chamber-3d-page.tsx` + `web/src/chamber-3d/**` at route `/chamber-3d` (lazy chunk). Visual experiment only.

### Out (unless human expands scope)

- Backend, auth, cloud profiles.
- Board serial / admin panel live control.
- PyVista twin, teacher, training UI.
- Using the R3F playground as export or ML geometry SSOT.

## Chamber 3D playground (product notes)

Route: **`/chamber-3d`**. Linked from the configurator as “Podgląd 3D”; does **not** read or write v4 JSON.

| Concern | Rule |
|---------|------|
| Dimensions | UX cm inputs (min 40, max 500); same volume formula as optional root `enclosure` |
| Shell | Open front (+Z doorway); exterior nylon + interior foil PBR; black steel frame flush to envelope |
| Colors / materials | CSS `--chamber-*` in `index.css`; R3F bridge + geometry knobs in `scene-tokens.ts` only |
| Rear mesh window | Zipper outline only (no fabric cutout): fixed **30×20 cm**, bottom edge **20 cm** above floor, **dual-sided** (interior + exterior). Shown only when tent **width is 60–120 cm inclusive** |
| Geometry tests | Pure modules under `web/src/chamber-3d/*-geometry.ts` + Vitest |
| Textures | `web/public/textures/growtent/` + `ATTRIBUTION.md` |

## Admin panel vs this configurator

| | Board admin panel (`main`) | Hardware configurator (this line) |
|--|----------------------------|-------------------------------------|
| Job | Connect MCU, live I/O, load_scenario | Describe installed hardware |
| Serial | Yes | No (MVP) |
| User | Lab / service | Client / setup |
| Output | Live control + scenario on device | JSON file |

Same **v4 vocabulary**, different product surface.

## Framework (locked)

See **`AGENTS.md` §3**. Short form:

- **pnpm only** (`pnpm@11.10.0`)
- React + TypeScript + Vite in **`web/`**
- Tailwind + shadcn/ui
- Vitest for domain/export (+ chamber geometry)
- R3F + drei for the optional `/chamber-3d` playground only
- Root gate chains into web gate

Do not reopen stack without editing `AGENTS.md` by human decision.

## Delivery sequence

1. ~~Field guide + Agents + example JSON~~
2. ~~Lock FE stack + root `pnpm gate` + regression tests~~
3. ~~Scaffold `web/` (locked stack) + web `pnpm gate` + extend root gate~~
4. ~~MVP import/export + inactive rules (domain Vitest)~~
5. ~~Isolated R3F chamber playground (`/chamber-3d`)~~
6. UI polish: Chamber / Sensors / Pots / Outputs wizard
7. Export matches golden **structure** on every user path (see `AGENTS.md` §6)
8. Optional: wire enclosure dimensions into export meta; richer 3D vents/mesh
9. Backend / train / board import later

## Evolution

Configurator may expose schema gaps (labels, defaults, names). Process:

1. Document the gap in the field guide (or issue).
2. Contract change → version bump on `main` + regen.
3. Then update FE + golden + gate.

Do not silently invent `actuators.lights` or extra ML slots.
