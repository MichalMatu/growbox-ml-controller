# Third-party research material (not a product dependency)

Local clones and papers used while designing the growbox **training** simulator.
Nothing under this tree is imported by firmware, panel, or the default ML pipeline.

## Name

**`third_party/`** — external code and literature we *study*, not vendored build deps.
(Prefer this over bare `vendor/`, which usually means linked runtime libraries.)

## Layout

```text
third_party/
  README.md                 # this file
  mpcrl-greenhouse/         # greenhouse ODEs (GPL-3.0; use with attribution)
  GES/                      # greenhouse energy/mass/CO₂ (MIT)
  Thermca/                  # general lumped thermal networks
  thermal-nn/               # thermal neural nets (LPTN + ML)
  OCHRE/                    # NREL residential thermal/HVAC (large)
  pyBuildingEnergy/         # ISO 52016 building energy
  papers/                   # downloaded PDFs (e.g. iGrow arXiv)
```

## Fetch / refresh clones

```bash
bash scripts/fetch_third_party.sh
```

Clones are **shallow** (`--depth 1`) and listed in `.gitignore` so the main repo stays small.
If you need them on another machine, re-run the script.

## License caution

| Tree | License | Implication for our MIT project |
|------|---------|----------------------------------|
| `GES/` | MIT | Reuse OK with MIT attribution |
| `mpcrl-greenhouse/` | **GPL-3.0** upstream | **Project permission:** authors OK’d use **if cited in our sources**. Keep credit in `docs/simulator/SOURCES.md` + module docstrings. Prefer adapted code with clear provenance over silent forks. |
| LetsGrow GPE (web) | proprietary educational | Extract *ideas* / order-of-magnitude checks only; no scrape of code |
| iGrow arXiv PDF | arXiv non-exclusive | Cite paper; do not republish PDF as ours |

Citations for derived physics live in `docs/simulator/SOURCES.md`.

## Primary entry points (after fetch)

| Source | Start here |
|--------|------------|
| mpcrl-greenhouse | `greenhouse/model.py`, `greenhouse/env.py` — **cite when using** |
| GES | `python/parameters.py`, `python/functions.py`, `python/GES_Example.py` |
| Thermca | package `thermca/`, `README.rst` |
| thermal-nn | `TNN_pytorch.ipynb` / `TNN_tensorflow.ipynb` |
| OCHRE | `ochre/` package, docs on ReadTheDocs |
| pyBuildingEnergy | `examples/`, ISO 52016 modules |
| iGrow paper | `papers/igrow-2107.05464.pdf` |
| LetsGrow GPE | https://gpe.letsgrow.com/ (interactive, not cloned) |

Research notes: [docs/simulator/SOURCES.md](../docs/simulator/SOURCES.md).
