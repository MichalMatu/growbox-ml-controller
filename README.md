# Growbox hardware configurator (FE line)

Sparse branch: **contract v4 + documentation only** — foundation for the web hardware editor.

## Tree

```text
schemas/environment-controller.json   # SSOT contract v4
docs/
  DATA_CONTRACT.md                    # Short rules
  HARDWARE_CONFIGURATOR.md            # Product assumptions
  SCHEMA_V4_FIELD_GUIDE.md            # Every path explained (PL sense / EN path)
  examples/
    README.md
    minimal-single-pot.json           # Golden export shape
AGENTS.md                             # Rules for implementers / agents
README.md
LICENSE
.gitignore
```

Full monorepo (firmware, board panel, simulator, training) lives on **`main`**.

## Do not merge this branch as a whole into `main`

That would delete product code.  
Add frontend under e.g. `web/`, then open a PR that only adds those files (+ docs/schema if needed).

## Read order (start here)

1. [`docs/HARDWARE_CONFIGURATOR.md`](docs/HARDWARE_CONFIGURATOR.md) — what we build  
2. [`docs/DATA_CONTRACT.md`](docs/DATA_CONTRACT.md) — mix & match rules  
3. [`docs/SCHEMA_V4_FIELD_GUIDE.md`](docs/SCHEMA_V4_FIELD_GUIDE.md) — fields  
4. [`docs/examples/minimal-single-pot.json`](docs/examples/minimal-single-pot.json) — export target  
5. [`AGENTS.md`](AGENTS.md) — coding / agent constraints  

## Next engineering step

Scaffold FE (framework TBD) that edits hardware flags/limits and **exports JSON matching the example shape**.
