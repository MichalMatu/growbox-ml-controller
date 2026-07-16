# Repozytorium — gałęzie i porządek

## Gałęzie

| Gałąź | Rola |
|-------|------|
| **`main`** | **v1 baseline** — jeden commit, zamrożona baza kodu |
| **`feature/sku-v1`** | Praca nad wąskim SKU (stałe wejścia/wyjścia, bez konfiguracji sprzętu) |
| **`archive/pre-squash-history`** | Pełna stara historia git (168 commitów) — tylko archiwum |

### Stan v1 baseline (świadome ograniczenia)

Kod na `main` to **uniwersalny kontrakt** (128 cech, 15 wyjść, mix & match I/O w panelu).
Okazało się to **ślepą uliczką** dla skutecznego treningu ML i testów kombinatorycznych.
**Nie kasujemy kodu** — encoder, safety i panel zostają jako baza; produkt v1 dopracowujemy na
`feature/sku-v1` (zamrożony zestaw czujników i aktuatorów pod jeden growbox).

Domyślna gałąź na GitHub: **`main`**.

## Sync Mac + Raspberry Pi

```bash
git checkout main
git pull
make setup          # lub setup-dev
```

Jedna maszyna robi zmiany → `commit` → `push` → druga `pull`. Nie kopiuj `build/`, `.venv/`, `sdkconfig` między maszynami.

## Co jest w git / czego nie commituj

| W git | Lokalnie (`.gitignore`) |
|-------|-------------------------|
| Źródła, schema, wygenerowany model C w `lib/.../generated/` | `build/`, `logs/`, `datasets/` |
| `docs/CONFIG_MATRIX.csv`, testy | `.venv/`, `sdkconfig`, `*.keras` |
| `continue_test.md` — audyt na Pi | `build/audit/*.jsonl` (checkpointy) |

## Narzędzia testowe (nie mylić)

| Narzędzie | Gdzie | Po co |
|-----------|-------|-------|
| `run_config_matrix` | Host | 59 profili I/O, encoder + safety (bez inference ML) |
| `board_engine_audit --matrix-only` | Płytka | Te same 59 na ESP |
| `panel_endpoint_audit` | Płytka + panel | Sweepy behawioralne ML |
| `exhaustive_board_audit` | Płytka | Siatki wartości × previous (~460k case) |
| `validity_matrix_audit` | Płytka | 32k masek validity |
| `probe_simulator` | Host | Fizyka symulatora (kierunki) |

Stary `io_ladder_audit.py` — eksperyment; nie jest w Makefile. Można usunąć w osobnym commicie.

## Kontynuacja audytu exhaustive

Zobacz [continue_test.md](../continue_test.md) w katalogu głównym repo.
