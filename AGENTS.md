# Agent notes — Growbox hardware configurator (FE)

This file is **normative**. If another doc disagrees with this file on stack, gate, paths, or export rules, **this file wins** until a human updates it.

---

## 1. Branch shape (sparse)

**Tracked now**

| Path | Role |
|------|------|
| `schemas/environment-controller.json` | Only shared SSOT with board / ML / `main` (`schema_version` **4**, 128 features, 15 outputs) |
| `docs/**` | Contract + product + field guide + golden example |
| `gate/check-contract.mjs` + `gate/check-contract.test.mjs` | Root golden gate and dependency-free regression tests (Node) |
| `package.json`, `pnpm-lock.yaml` | Toolchain pin and root quality scripts |
| `web/**` | Hardware configurator SPA (React/Vite/TS/Tailwind/shadcn) |
| `AGENTS.md`, `README.md`, `LICENSE`, `.gitignore` | Policy and entrypoints |

**Not on this branch (by design)**

ESP firmware, board admin panel, simulator, twin, teacher, train, monorepo `tools/` / CI / PlatformIO tree.

Full product: checkout **`main`**.

### Merge policy (hard)

1. **Never** merge this sparse branch wholesale into `main` (would delete the product tree).
2. Land the app by adding **`web/**`** and PR/cherry-pick **only** those paths (+ docs/schema/gate updates as needed).
3. **Never** re-commit monorepo trees (`tools/`, `src/`, `tests/`, firmware, …) onto this branch.

---

## 2. Goal

Web **hardware configurator**: client describes installed growbox gear in **v4** terms → **download one JSON file**.

- MVP: **static SPA**, schema loaded as static JSON, **no backend**.
- Out of MVP unless a human explicitly expands scope: serial, cloud auth, train UI, in-browser ML, PyVista twin.

---

## 3. Locked stack (do not reopen)

| Layer | Mandatory choice |
|-------|------------------|
| Package manager | **pnpm only** — `packageManager`: **`pnpm@11.10.0`** in root `package.json`. No npm, no yarn, no mixing lockfiles. |
| Node | **≥ 20** (`engines` in root `package.json`) |
| App directory | **`web/`** only |
| UI library | **React** (18+ SPA) |
| Language | **TypeScript strict** |
| Bundler | **Vite** |
| CSS | **Tailwind CSS** (major version = whatever **official shadcn/ui Vite+React+TS init** installs at scaffold time; do not mix v3 config file setup with v4 CSS-first setup) |
| Components | **shadcn/ui** (Radix) copied into `web/src/components/ui/` |
| Domain tests | **Vitest** under `web/` |
| 3D (later only) | React Three Fiber + drei — **not** day-0 scaffold |
| SSR / meta-framework | **Forbidden for MVP** (no Next.js, no Remix) |

### Stack non-goals (hard ban)

- Vanilla JS + hand-rolled global CSS
- Svelte / Vue / Angular / Solid for this product line
- Second component library (MUI, Chakra, Ant, Mantine, …) without written human approval in this file
- CSS-in-JS as primary styling (styled-components, Emotion)
- `package-lock.json` / `yarn.lock` in the repo

At first scaffold, run the official shadcn Vite + React + TypeScript initializer exactly once, commit the lockfile it produces, and use frozen-lockfile installs thereafter. Do not reinitialize an existing app or hand-migrate between Tailwind major-version setups.

---

## 4. Path notation (no ambiguity)

| Context | Form | Example |
|---------|------|---------|
| Schema `model.features[].path` | Dot + **numeric segment** for pot index | `pots.0.irrigation.available` |
| Nested export JSON | Array index | `pots[0].irrigation.available` |
| Docs prose | Either, but map 1:1 | `pots[N]` means schema `pots.N` |

Editor state **must** round-trip to schema paths. Prefer storing by schema path string or a typed object that serializes to the golden nested shape.

---

## 5. SSOT map

| Question | File |
|----------|------|
| min / max / default / feature order / hash | `schemas/environment-controller.json` |
| Meaning of each path | `docs/SCHEMA_V4_FIELD_GUIDE.md` |
| Product layers + scope | `docs/HARDWARE_CONFIGURATOR.md` |
| Short mix & match rules | `docs/DATA_CONTRACT.md` |
| Golden export file | `docs/examples/minimal-single-pot.json` |
| Export checklist | `docs/examples/README.md` |
| Stack, gate, agent UI law | **this file** |

**Do not invent ML paths.** If the UI needs a field that is not a `model.features[].path` and not an **allowed root meta key** (below), stop and document — do not ship inventing.

---

## 6. Export contract (hard rules)

1. **Language:** path identifiers English; UI copy may be Polish.
2. **Always exactly 4 pots** in `pots` array. Never delete a slot.
3. **Mix & match:** missing gear → `validity=false` / `available=false` + zero capability fields — slots remain. This applies to global actuators and to `pots[N].irrigation` / `pots[N].heat_mat`, even when the pot itself remains active.
4. **Inactive pot** (`pots[N].available === false`) export **must**:
   - `validity.soil_moisture_pct` = false
   - `validity.soil_temperature_c` = false
   - `irrigation.available` = false; `flow_ml_s`, `maximum_pulse_s`, `minimum_interval_s` = **0**
   - `heat_mat.available` = false; `max_power_w` = **0**
   - `previous.irrigation` = **0**; `previous.heat_mat` = **0**
   - `cultivation.*` **may** keep non-zero template numbers (volume/capacity); do not require zeroing cultivation.
   - `control_type` keys **remain** (`"binary"` or `"pwm"` only).
5. **Inactive global actuator:** `available=false` and zero capability fields (`max_*` / `maximum_*`, dose, and `efficiency` = 0 where the object has efficiency).
6. **Forbidden in export:** `actuators.lights`. Lights schedule = `pseudo.lights_active` only.
7. **Forbidden in export:** any `actuators.<id>.control_type`. Global actuators have **no** control_type in v4 features. Only pot irrigation/mat enums.
8. **Enums:** pot `irrigation.control_type` and `heat_mat.control_type` JSON strings **`"binary"`** \| **`"pwm"`** only (schema encoding binary→0, pwm→1).
9. **Numbers:** clamp to schema min/max for that path.
10. **Previous (hardware template):** all `previous.*` and every per-pot `previous.*` = **0**, regardless of availability.
11. **Schema edits** that add/rename ML slots or change meaning = **breaking** → `schema_version` bump + regen on **`main`** first; document; then FE.
12. **Code / commits:** English. Chat to human: Polish.

### Allowed root keys in export JSON

**Contract layers (required in golden / MVP export shape):**

`environment`, `sensors`, `validity`, `pseudo`, `pots`, `actuators`, `targets`, `previous`

**Root meta (not ML features; allowed):**

| Key | Type | Rule |
|-----|------|------|
| `seed` | number (integer) | Optional for product; present in golden example |
| `profile_id` | string | Optional; present in golden |
| `title` | string | Optional; present in golden |
| `enclosure` | object | **Optional UX only.** If present, it contains exactly positive numeric `width_cm`, `depth_cm`, `height_cm`; `environment.growbox_volume_m3` must equal `width_cm * depth_cm * height_cm / 1_000_000`. **Not** an ML feature. Do not add `environment.width_cm` without a versioned schema change. |

No other root keys without updating this file **and** `gate/check-contract.mjs`.

### Structure equality (MVP definition of done)

Export **structure** matches `docs/examples/minimal-single-pot.json` when:

- same required contract root keys exist,
- `pots.length === 4`,
- every `model.features[].path` resolves on the export,
- no extra nested paths exist outside the allowed root meta shape,
- forbidden keys absent,
- inactive rules hold for off pots/actuators,

Values may differ. Gate enforces this on the golden file; FE tests must enforce the same on the exporter.

### Import / export policy

- Import accepts only a document that passes the same v4 structure, type, range, metadata, and safety rules as an export. Reject invalid input with field errors; do not silently migrate, retain unknown keys, or maintain old-shape fallbacks.
- Export normalization is a pure domain function: clamp numbers from the schema, preserve enum strings, restore exactly four pots, apply unavailable-module zeroing, and zero all `previous` fields before serialization.
- Components only bind editor state. The import, normalization, and export functions receive fixture-based Vitest coverage, including every inactive-pot and inactive-module rule.

---

## 7. Agent UI rules (hard)

1. No freehand global CSS sheet growth (`panel.css` anti-pattern).
2. Layout = Tailwind utilities only (`flex` / `grid` / `gap-*` / scale spacing).
3. Controls = shadcn/ui only; add missing pieces via shadcn CLI into `components/ui/`.
4. Theme = Tailwind + shadcn CSS variables; no random one-off hex in JSX.
5. Prefer vertical stack / wizard steps; no “two uneven columns with empty holes” layout games.
6. No pixel-nudge-only changes (`mt-[13px]`, `top-px`, magic widths) as the fix — fix structure or shared component.
7. Domain logic (export, clamp, inactive rules) = pure TS modules + Vitest; components bind state only.
8. Preview of tent/pots = parametric from numbers; not a library of hundreds of size-specific AI images as the source of truth.
9. Do not drop pot slots or invent actuator paths to “simplify UI”.

---

## 8. Target `web/` layout (scaffolded)

```text
web/
  package.json          # private; scripts: gate, typecheck, lint, test, build
  vite.config.ts
  tsconfig.json
  index.html
  src/
    main.tsx
    App.tsx
    components/ui/      # shadcn only
    components/         # feature UI
    lib/                # cn(), helpers
    domain/             # export/import/clamps (tested)
    index.css           # Tailwind entry + shadcn variables only
```

Schema: static import from the shared `../schemas/environment-controller.json` source (Vite `server.fs.allow` includes the repo root), never a copied contract — **no API**.

---

## 9. Golden gate (normative)

### 9.1 Root gate (exists now — always run)

From repository root:

```bash
pnpm gate
```

Root `pnpm gate` chains the contract validator into the web gate:

```text
node gate/check-contract.mjs && pnpm --dir web gate
```

**Must pass** before any commit that touches:

- `schemas/**`
- `docs/examples/**`
- `gate/**`
- root `package.json`
- or any change that claims export/contract correctness

**Recommended:** run `pnpm gate` before **every** commit on this branch.

Root gate verifies at least:

- `schema_version === 4`, 128 features, 15 outputs, and the pinned v4 model signature (order, names, paths, types, ranges, defaults, enum encoding)
- golden or `--input` export: exact feature-path shape, types/ranges, enum strings, metadata types, 4 pots, unavailable-module/inactive rules, all previous values zero, no `actuators.lights`, no global `control_type`
- root Node/package-manager lock and absence of npm/yarn lockfiles

After changing `gate/**`, also run:

```bash
pnpm test:contract
```

`pnpm check` runs both the golden gate and those regression tests.

### 9.2 Web gate (only after `web/` exists)

From `web/`:

```bash
pnpm gate
```

Must mean **exactly** this sequence (all green):

1. `pnpm typecheck` → `tsc --noEmit`
2. `pnpm lint`
3. `pnpm test` (Vitest)
4. `pnpm build`

Root `package.json` `gate` script must be extended at scaffold time to:

```text
node gate/check-contract.mjs && pnpm --dir web gate
```

until then root gate is contract-only.

The root contract gate enforces that hand-off automatically once `web/` exists: it requires the root chain, a private `web/package.json`, strict TypeScript, the locked core dependencies, and the exact web gate sequence.

### 9.3 Commit blockers (human or agent)

Do **not** commit if any of:

| Check | Fail condition |
|-------|----------------|
| Gate | `pnpm gate` non-zero |
| Contract | Missing feature paths vs schema; not 4 pots |
| Contract | `actuators.lights` or global `control_type` |
| Types (web) | `any` / `@ts-ignore` without human-written justification |
| Styles (web) | New freehand CSS layout system or second UI kit |
| Scope | Monorepo product trees reintroduced on this branch |
| Lockfile | npm/yarn lockfile added; or pnpm lock out of sync after dep change |
| Secrets | `.env` with secrets committed |

### 9.4 Commit messages

English, imperative, scoped. Example: `Harden root gate for inactive pot export rules`.

Never commit: `node_modules/`, `dist/`, secrets, monorepo ghosts.

### 9.5 PR onto `main` (later)

- Add `web/**` (+ docs/schema/gate as needed) only.
- Never replace `main` with this sparse tree.
- CI on `main` should run the same root + web gate for the configurator paths.

---

## 10. UI groups (product)

1. Chamber — `environment.*` (+ optional UX `enclosure` → derive `growbox_volume_m3`)
2. Sensors — `sensors.*` + `validity.*`
3. Pots 1–4 — full pot objects
4. Outputs — `actuators.*`
5. Pseudo — `pseudo.lights_active`
6. Targets / previous — defaults OK for MVP (previous = 0)

---

## 11. Status checklist

| Item | Status |
|------|--------|
| Stack locked | **Yes** (this file) |
| Contract docs + golden JSON | **Yes** |
| Root `pnpm gate` (contract + web chain) | **Yes** — `gate/check-contract.mjs` → `web` gate |
| `web/` app | **Yes** — Vite + React + TS + Tailwind + shadcn MVP shell |
| Web typecheck/lint/test/build gate | **Yes** — `pnpm --dir web gate` |
| Domain Vitest (import/export/inactive) | **Yes** — `web/src/domain/*.test.ts` |

**Next product steps:** polish UX groups (wizard steps), optional enclosure UX fields, richer Polish copy; keep export contract and gate green.
