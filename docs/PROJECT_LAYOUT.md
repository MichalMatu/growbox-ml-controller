# Project layout

Intentional repository structure. Current climate-v6 status is tracked in `CURRENT_STATUS.md`; legacy v4/v5 assets remain where required for migration/reproducibility.

```text
.
├── README.md                 # project entry
├── LICENSE
├── AGENTS.md                 # agent/UI notes (keep at root for tooling)
├── Makefile                  # developer CLI
├── CMakeLists.txt            # ESP-IDF project root (must stay here)
├── pyproject.toml            # Python package metadata + tooling
├── requirements-lock.txt     # pinned Python deps (pip convention)
├── requirements-dev.txt
│
├── config/                   # build / board configuration
│   └── idf/                  # sdkconfig.defaults* profiles
├── schemas/                  # environment-controller.json (ML + wire contract)
├── docs/                     # human documentation
│   ├── simulator/            # physics research + I/O inventory
│   └── CHANGELOG.md
│
├── tools/                    # host Python (ml, panel, serial, schema, analysis)
├── scripts/                  # shell gates (CI, idf helpers)
├── examples/                 # scenario JSONL samples
├── third_party/              # research clones (see third_party/README.md; not build deps)
│
├── lib/environment_control/  # portable legacy + climate-v6 C++ controller core
├── components/               # ESP-IDF extra components (emlearn)
├── src/                      # ESP-IDF app; legacy demo plus climate-v6 I/O adapters
│
├── test/                     # host CMake / Unity (portable C++)
├── tests/                    # pytest (Python + panel)
│
├── build/                    # local artifacts (gitignored)
└── logs/                     # local captures (gitignored)
```

## What stays at the repository root

| File | Why |
|------|-----|
| `CMakeLists.txt` | ESP-IDF requires project CMake at root |
| `Makefile` | primary developer entrypoint |
| `README.md` / `LICENSE` | GitHub / packaging convention |
| `pyproject.toml` + `requirements-*.txt` | pip / pre-commit / CI cache paths |
| `AGENTS.md` | discovered from repo root by agent tooling |
| `.pre-commit-config.yaml`, `.clang-*`, `.editorconfig` | tool defaults |

## Where to put new work

| Work | Location |
|------|----------|
| Growbox physics / training sim | `tools/ml/` + notes in `docs/simulator/` |
| Panel UI | `tools/panel/` |
| Contract fields | `schemas/` then regenerate headers |
| Board Kconfig defaults | `config/idf/` |
| Docs | `docs/` (not root markdown dumps) |
