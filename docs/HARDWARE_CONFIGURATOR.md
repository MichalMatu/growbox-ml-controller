# Hardware configurator — product assumptions (golden start)

## Why this branch exists

Build a **web editor** so a client describes *their* growbox in **contract v4** language and downloads a JSON file.  
That file later feeds training / board `load_scenario`. **Not in this phase:** 3D twin, serial, teacher, in-browser ML.

## Sparse tree

| On this branch | On `main` (elsewhere) |
|----------------|------------------------|
| `schemas/environment-controller.json` | Full product: firmware, panel, sim, train, CI |
| `docs/*` (this guide set) | Same schema file as SSOT when merged carefully |
| `AGENTS.md`, `README.md` | — |

**Never merge this sparse branch wholesale into `main`.**  
Land FE as a new directory (e.g. `web/`) via PR/cherry-pick of *those* files (+ schema/docs if needed).

## SSOT

| Layer | File |
|-------|------|
| Contract paths, min/max/default, 128 features, 15 outputs | `schemas/environment-controller.json` |
| What each path means (PL) | `docs/SCHEMA_V4_FIELD_GUIDE.md` |
| Example export | `docs/examples/minimal-single-pot.json` |
| Agent / implementer rules | `AGENTS.md` |
| Contract rules (short) | `docs/DATA_CONTRACT.md` |

## Two layers in one JSON file

A full scenario JSON mixes layers. The configurator must **not** blur them in the UI:

| Layer | What it is | Configurator MVP |
|-------|------------|------------------|
| **A. Hardware** | What is installed + limits | **Primary** — validity, available, max_*, cultivation, control_type on pots |
| **B. Process seed** | Current/start sensor readings | Optional; use schema defaults or simple “start climate” |
| **C. Targets** | Setpoints (goals) | Optional climate targets; pot soil targets often with pot card |
| **D. Previous** | Last commands 0–1 | Default **0** for “clean box” export |
| **E. Meta** | e.g. `seed` (RNG / scenario id) | Optional number; **not** an ML feature path |

MVP export = **A solid**, B/C sensible defaults, D zeros, E optional `seed`.

## Scope

### In (now)

- UI groups: Chamber → Sensors → Pots → Outputs → Pseudo (see field guide).
- FE validation: min/max from schema; pot off forces soil validity false and irr/mat available false + zero limits.
- Actuator off: `available=false` and zero dangerous max fields in export.
- Import / export JSON (file, paste, `localStorage`).
- Load schema JSON statically (no backend).

### Out (later / other branches)

- Backend, auth, cloud profiles.
- Board serial / admin panel live control.
- PyVista twin, teacher, training UI.

## Admin panel vs this configurator

| | Board admin panel (`main`) | Hardware configurator (this line) |
|--|----------------------------|-------------------------------------|
| Job | Connect MCU, live I/O, load_scenario | Describe installed hardware |
| Serial | Yes | No (MVP) |
| User | Lab / service | Client / setup |
| Output | Live control + scenario on device | JSON file |

Same **v4 vocabulary**, different product surface.

## Framework

**Not chosen yet.** Prefer the simplest stack that can:

1. Render grouped forms from schema (or a thin form map keyed by `path`).
2. Export/import JSON.
3. Stay easy to cherry-pick onto `main`.

Vanilla, Vite+TS, Svelte, React are all fine — decide after first screen map, not before.

## Delivery sequence

1. ~~Field guide + Agents + example JSON~~ (this docs set).  
2. UI skeleton: Chamber / Sensors / Pots / Outputs.  
3. Export matches `docs/examples/minimal-single-pot.json` shape (4 pots always).  
4. Backend / train / board import later.

## Evolution

Configurator will **drive** schema cleanups (missing labels, bad defaults, confusing names).  
Process:

1. Document the gap in the field guide (or issue).  
2. If contract must change → version bump on `main` + regen.  
3. Then update FE.

Do not silently invent `actuators.lights` or extra ML slots.
