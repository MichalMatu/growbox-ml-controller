# Agent notes — Growbox ML

## Panel UI (`tools/panel/static/`) — układ pól

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
- **Prawa kolumna** — **Na żywo** (tabele czujników + paski aktuatorów + `panel-actions`), **Poprzedni stan** (tylko odczyt)
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
