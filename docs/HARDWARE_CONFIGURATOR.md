# Hardware configurator — product assumptions

Normative stack, gate, and export law: **[`AGENTS.md`](../AGENTS.md)**.
If this file conflicts with `AGENTS.md`, **`AGENTS.md` wins**.

## Why this branch exists

Build a **web editor** so a client describes *their* growbox in **contract v4** language and downloads a JSON file.
That file later feeds training / board `load_scenario`.

**Not in this phase:** 3D twin, serial, teacher, in-browser ML, backend auth.

## Sparse tree

| On this branch | On `main` (elsewhere) |
|----------------|------------------------|
| `schemas/environment-controller.json` | Full product: firmware, panel, sim, train, CI |
| `docs/*` | Same schema file as SSOT when updated carefully |
| `gate/`, root `package.json`, `pnpm-lock.yaml` | — |
| `AGENTS.md`, `README.md`, `.gitignore`, `LICENSE` | — |
| `web/**` (later) | Land via PR of those paths only |

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
- Root checks: `pnpm gate` (contract + golden) and `pnpm test:contract` after gate edits.

### Out (unless human expands scope)

- Backend, auth, cloud profiles.
- Board serial / admin panel live control.
- PyVista twin, teacher, training UI.
- Scaffold of `web/` before explicit order.

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
- Vitest for domain/export
- Root gate now; web gate at scaffold

The scaffold commits its generated pnpm lockfile and does not mix Tailwind major-version setup styles.

Do not reopen stack without editing `AGENTS.md` by human decision.

## Delivery sequence

1. ~~Field guide + Agents + example JSON~~
2. ~~Lock FE stack + root `pnpm gate` + regression tests~~
3. Scaffold `web/` (locked stack) + web `pnpm gate` + extend root gate
4. UI: Chamber / Sensors / Pots / Outputs
5. Export matches golden **structure** (see `AGENTS.md` §6)
6. Backend / train / board import later

## Evolution

Configurator may expose schema gaps (labels, defaults, names). Process:

1. Document the gap in the field guide (or issue).
2. Contract change → version bump on `main` + regen.
3. Then update FE + golden + gate.

Do not silently invent `actuators.lights` or extra ML slots.
