# Growbox browser configurator

React + TypeScript + Vite frontend for the Growbox ML Controller project.

This app has two public surfaces:

- `/` — schema-driven hardware / JSON configurator
- `/chamber-3d` — interactive React Three Fiber growbox chamber configurator

Live deployment:

- https://michalmatu.github.io/growbox-ml-controller/
- https://michalmatu.github.io/growbox-ml-controller/chamber-3d

## Contract boundary

The browser application currently uses its own explicit bundled contract snapshot:

`schema/environment-controller.v5.json`

That contract is **schema v5: up to 9 pot slots, 228 model features and 25 outputs**.

Do not replace the repository-root `schemas/environment-controller.json` during convergence. The root contract is still the firmware/controller **v4** contract. Migrating firmware from v4 to v5 is separate architecture work and must be deliberate.

`src/domain/schema.ts` validates the browser-side schema version and dimensions at startup so an accidental contract mismatch fails visibly.

## Stack

- React 19
- TypeScript
- Vite
- Three.js
- React Three Fiber / drei
- Tailwind CSS
- shadcn UI / Radix
- Vitest
- ESLint

## Development

Requires Node.js 22 and pnpm 11.10.0.

```bash
corepack enable
corepack prepare pnpm@11.10.0 --activate
pnpm install --frozen-lockfile
pnpm dev
```

When running commands from the repository root, use:

```bash
pnpm --dir web install --frozen-lockfile
pnpm --dir web dev
```

## Quality gate

```bash
pnpm typecheck
pnpm lint
pnpm test
pnpm build
```

From the repository root:

```bash
pnpm --dir web typecheck
pnpm --dir web lint
pnpm --dir web test
pnpm --dir web build
```

The integration branch runs all four steps as a separate GitHub Actions job so frontend work cannot silently break firmware/controller validation.

## Routing and GitHub Pages

Vite is configured with the repository base path `/growbox-ml-controller/`.

The app uses lightweight client-side routing:

- configurator: `/`
- 3D chamber: `/chamber-3d`

The 3D route is lazy-loaded so React Three Fiber / Three.js do not need to be loaded for the JSON configurator screen.

## 3D chamber

The chamber view contains parametric geometry for the enclosure, pots, lights and fans. Its purpose is to make the hardware configuration understandable and visually test dimensions/layout; it is not a CFD or plant-growth simulation.

The scientific simulator/twin in `tools/ml/twin/` is a separate Python/PyVista engineering tool. The browser chamber view and the scientific twin are complementary rather than duplicate implementations.

## Convergence note

This frontend was imported non-destructively from the former sparse configurator line into `integration/convergence-2026-08`. The source branch and dated snapshot remain available until the complete convergence checklist passes.

See `../docs/INTEGRATION_CONVERGENCE.md` for preservation rules and deletion criteria.
