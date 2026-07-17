# Agent notes — Growbox ML

## Priorytet tej linii pracy: konfigurator hardware (web)

**Cel:** frontendowy edytor setupu growboxa oparty o **kontrakt schema v4**, z eksportem JSON.
**Nie cel:** twin 3D, trening ML, teacher, symulator live, rozbudowa panelu board — chyba że użytkownik wyraźnie prosi.

### SSOT

| Co | Gdzie |
|----|--------|
| Pola, min/max, path, outputs | `schemas/environment-controller.json` |
| Krótkie znaczenie pól (PL) | `docs/SCHEMA_V4_FIELD_GUIDE.md` |
| Założenia produktu edytora | `docs/HARDWARE_CONFIGURATOR.md` |
| Kontrakt (skrót) | `docs/DATA_CONTRACT.md` |

### Zasady implementacji FE

1. **Identyfikatory i path JSON — angielski** (`air_temperature_c`, `pots[0].irrigation.available`). Etykiety UI mogą być po polsku.
2. **Mix & match v4:** brak sprzętu = `validity=false` / `available=false` / `pots[N].available=false` — **nie usuwaj slotów** z JSON.
3. Wyłączony aktuator: `available=false` i zeruj niebezpieczne maxy w eksporcie (zgodnie z kontraktem safety).
4. **Nie dodawaj** nowych slotów ML (PPFD, EC, pH, …) bez nowej wersji schema.
5. Framework **nie jest narzucony** — wybór dopiero po mapie ekranów; unikaj ciężkiego stacka bez potrzeby.
6. **Backend nie jest wymagany** na MVP: export/import pliku JSON wystarczy.
7. Panel admin (`tools/panel`) = **inne zadanie** (board). Nie mieszaj flow „Połącz z płytką” z edytorem hardware, chyba że użytkownik każe.
8. Zmiana znaczenia pola w schema = breaking: podnieś `schema_version`, regeneruj artefakty (`tools/schema/generate_environment_schema.py`), nie „cichy rename”.
9. Kod UI i commit messages — angielski; komunikaty do użytkownika w czacie — po polsku (preferencje repo).
10. Ewolucja: konfigurator **może napędzać** poprawki pól; najpierw opisz brak w guide/schema PR, potem UI.

### Proponowane grupy UI (start)

1. Chamber — `environment.*`
2. Sensors + validity — air / outside / nutrient
3. Pots 1–4 — available, soil validity, cultivation, irrigation, heat mat, pot targets
4. Outputs — global actuators + limits
5. Pseudo — `lights_active`
6. Targets (climate) — opcjonalnie w MVP
7. Previous — domyślnie 0 w konfiguratorze „czystego boxa”

### Out of scope (nie rób bez prośby)

- PyVista / `tools/ml/twin`
- `SequentialEnvironmentSimulator` w UI
- Teacher / dataset / train w tym FE
- Nowe dependency ML

### Testy (gdy pojawi się kod FE)

- Export JSON: 4× `pots`, klucze `validity` / `actuators` / `environment` obecne.
- Donica off → validity gleby false, irrigation/heat_mat available false w eksporcie (lub równoważna reguła udokumentowana).
- Nie łam `python tools/schema/generate_environment_schema.py --check` przy zmianach schema.

---

## Panel UI (`tools/panel/static/`) — układ pól

**Dotyczy panelu board/admin, nie konfiguratora hardware.**
**Nie układaj parametrów w mini-kartach jeden pod drugim.** To powtarzający się błąd (donice, uprawa, aktuary).

### Zasada

W kartach **Donica N**, **aktuator**, **cel** itp. pola liczbowe / enum idą **w jednym poziomym rzędzie**, tak jak w reszcie panelu:

| Sekcja | Wzorzec (OK) |
|--------|----------------|
| Czujniki → Donice | `.pot-card-sensors` — siatka 2 kolumny (Wilg. \| Gleba T) |
| Cele → Donice | `.compact-row` + `.mini-cell` |
| Aktuary | `.field-stack` z **poziomym** `flex-direction: row` |
| Parametry growboxa → Donice | `.compact-row` w `.cultivation-pot-card` |

### Antywzorzec (NIE)

- `field-stack` + `flex-direction: column` wewnątrz `.pot-card` / `.cultivation-pot-card`
- pełna szerokość `.mini-cell` (`width: 100%`) w karcie, która ma **kilka** parametrów obok siebie
- osobna pionowa kolumna label+input pod label+input w jednej donicy

Efekt: marnowanie wysokości, brak spójności z Czujnikami i Aktuatorami.

### Przed commitem / po zmianie `form.js` lub `panel.css`

```bash
.venv/bin/python -m pytest tests/test_panel_layout.py -q
```

Testy są źródłem prawdy: `tests/test_panel_layout.py`.

### Układ strony

- **Lewa kolumna** — `card-stack`: Sterowanie, **Czujniki**, **Cele**, **Aktuary** (`#form-sections.card-stack`)
- **Prawa kolumna** — **Na żywo** (tabele czujników + paski aktuatorów + `panel-actions`; **Poprzedni stan** w modalu przez przycisk **Poprzedni**)
- **Panel modal** (`#modal-backdrop` → `.panel-modal.modal--wide`) — jeden przesuwalny modal; widoki z `panel-actions` pod Na żywo (bez zakładek/stopki w modalu)
- Donice w parametrach growboxa (modal **Growbox**): **ta sama szerokość** karty co w Czujnikach (`--pot-card-w`), 3 pola w poziomym gridzie

**Antywzorzec układu strony (puste dziury):**

- `.form-grid` z kartami o różnej wysokości obok siebie (np. Czujniki | Cele)
- `.growbox-params-split` (Obudowa obok Donic) — zostawia pustą przestrzeń
- siatka 2-kolumnowa na Aktuary (Klimat | Pompy), gdy jedna połowa jest niższa

Nie „optymalizuj” na jeden ekran kosztem pustych pól — lepiej zwarty pionowy stos.

### Pliki panelu

- Render: `tools/panel/static/js/form.js` (`renderZoneCultivationCard`, `renderPotCard`, `renderActuatorGroupCell`, …)
- Style: `tools/panel/static/panel.css` (`.card-stack`, `.compact-row`, `.pot-card`, `.cultivation-pot-card`)
- Szkielet: `tools/panel/static/index.html`
