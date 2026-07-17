# Agent notes — Growbox hardware configurator (FE branch)

## Ten branch jest sparse

W git na tej linii pracy są głównie:

- `schemas/environment-controller.json` (kontrakt **v4** — jedyny most do monorepo / board / ML)
- `docs/` (guide pól + założenia konfiguratora + DATA_CONTRACT)
- `AGENTS.md`, `README.md`, `LICENSE`, `.gitignore`

**Nie ma tu:** firmware ESP, panel board, simulator, twin PyVista, teacher, train, testów monorepo.

Pełny kod produktu: branch **`main`** (i inne feature branche).  
**Nigdy** nie merguj tego sparse brancha w całości do `main` — skasowałby produkt.  
FE dodawaj jako nowy katalog; na `main` wjeżdżaj cherry-pickiem / PR tylko tych plików (+ schema/docs gdy trzeba).

## Cel

Frontendowy edytor setupu growboxa (hardware) + **eksport JSON** zgodny z v4.  
Bez backendu na start. Framework — do wyboru później.

## SSOT

| Co | Gdzie |
|----|--------|
| Pola, min/max, path, outputs | `schemas/environment-controller.json` |
| Znaczenie pól (PL) | `docs/SCHEMA_V4_FIELD_GUIDE.md` |
| Założenia produktu | `docs/HARDWARE_CONFIGURATOR.md` |
| Skrót kontraktu | `docs/DATA_CONTRACT.md` |

## Zasady FE

1. Path JSON i identyfikatory — **angielski**; etykiety UI mogą być po polsku.
2. Mix & match: brak sprzętu = `validity=false` / `available=false` / `pots[N].available=false` — **nie usuwaj slotów**.
3. Aktuator off → `available=false` + zeruj niebezpieczne maxy w eksporcie.
4. Bez nowych slotów ML (PPFD, EC, …) bez nowej `schema_version`.
5. Backend opcjonalny później; MVP = plik JSON.
6. Panel board / serial — nie na tym branchu.
7. Commit messages i kod — angielski; czat z użytkownikiem — po polsku.
8. Konfigurator może napędzać ewolucję pól — najpierw guide/schema, potem UI.

## Grupy UI (start)

1. Chamber — `environment.*`
2. Sensors + validity
3. Pots 1–4
4. Outputs (global actuators + limits)
5. Pseudo `lights_active`
6. Targets / previous — opcjonalnie w MVP

## Out of scope

- Odtwarzanie monorepo (ESP, panel, twin, ML) na tym branchu
- Sim / twin / train / teacher w UI
- CI ESP/pytest monorepo na tym tree
