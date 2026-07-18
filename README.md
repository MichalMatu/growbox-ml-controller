# Growbox hardware configurator (FE line)

Sparse branch: **contract v4 + docs + root golden gate + `web/` SPA**.
Static hardware editor: describe installed gear → download one v4 JSON file.

Normative rules: [`AGENTS.md`](AGENTS.md).

## Tree

```text
schemas/environment-controller.json   # SSOT contract v4 (128 features, 15 outputs)
docs/
  DATA_CONTRACT.md
  HARDWARE_CONFIGURATOR.md
  SCHEMA_V4_FIELD_GUIDE.md
  examples/
    README.md
    minimal-single-pot.json           # Golden export shape
gate/
  check-contract.mjs                  # Root contract gate
  check-contract.test.mjs             # Gate regression tests (Node built-in)
package.json                          # pnpm@11.10.0, gate/check/test:contract scripts
pnpm-lock.yaml
web/                                  # React + Vite + TS + Tailwind + shadcn SPA
AGENTS.md
README.md
LICENSE
.gitignore
```

Full monorepo (firmware, board panel, simulator, training) lives on **`main`**.

## Do not merge this branch as a whole into `main`

That would delete product code.
Land work by PR/cherry-pick of **`web/**`** (+ docs/schema/gate if needed).

## Read order

1. [`AGENTS.md`](AGENTS.md) — stack, gate, export law (wins on conflict)
2. [`docs/HARDWARE_CONFIGURATOR.md`](docs/HARDWARE_CONFIGURATOR.md) — product
3. [`docs/DATA_CONTRACT.md`](docs/DATA_CONTRACT.md) — mix & match
4. [`docs/SCHEMA_V4_FIELD_GUIDE.md`](docs/SCHEMA_V4_FIELD_GUIDE.md) — fields
5. [`docs/examples/minimal-single-pot.json`](docs/examples/minimal-single-pot.json) — export target

## Stack (locked)

**pnpm only** · React · Vite · TypeScript · Tailwind · shadcn/ui · Vitest — app under **`web/`**.
Details: [`AGENTS.md`](AGENTS.md).

## Setup

Requires **Node ≥ 20** and **pnpm 11.10.0** (see `packageManager` in root `package.json`).

```bash
corepack enable
corepack prepare pnpm@11.10.0 --activate

# Root has no app deps; install the SPA toolchain under web/:
pnpm --dir web install

# Dev server
pnpm --dir web dev
```

## Contract + app checks (run before commits)

```bash
# Root: contract validator, then web typecheck + lint + test + build
pnpm gate

# After changing gate/**; also part of hand-off:
pnpm test:contract

# Shorthand: full gate + contract regression tests
pnpm check
```

`pnpm gate` must exit 0. Domain import/export rules are covered by Vitest under `web/src/domain/`.

### Git hooks (pre-commit)

This branch ships [`.pre-commit-config.yaml`](.pre-commit-config.yaml) for the **web/FE line** (not main’s firmware gate).

```bash
# once per clone
pre-commit install

# manual
pre-commit run --all-files
```

| When | What runs |
|------|-----------|
| `git commit` | hygiene + `pnpm test:contract` + web typecheck/lint/test |
| `git push` | full `pnpm check` (contract + web gate including build) |

## 3D playground

Optional visual experiment (not export SSOT):

```bash
pnpm --dir web dev
# open http://127.0.0.1:5173/chamber-3d
```

Parametric grow tent (W×D×H cm). Code: `web/src/chamber-3d/`. Product notes: [`docs/HARDWARE_CONFIGURATOR.md`](docs/HARDWARE_CONFIGURATOR.md) § Chamber 3D playground.

## Next engineering step

UX polish (wizard steps, optional root `enclosure` wired to export volume), keep schema import as SSOT, never invent ML paths.
