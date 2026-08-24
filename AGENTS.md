# Agent notes — Growbox ML

## Local Agent v4.6 — repository workflow

This repository is registered in the shared `MichalMatu/local-agent` v4.6 multi-repository supervisor.

Repository identity:

- repository: `MichalMatu/growbox-ml-controller`
- local-agent repository id: `growbox-ml-controller`
- control branch: `agent-control`
- default source branch: `main`
- execution model: one shared supervisor across repositories, with at most one local task executing at a time

### New chat bootstrap

When starting work on this repository in a new chat/session:

1. Read this `AGENTS.md` and the current `README.md` before proposing or executing changes.
2. Inspect the current GitHub state of the repository and the branch relevant to the requested work. Do not assume `main` is always the correct work branch; the README may identify an active integration branch.
3. Use this repository's own `agent-control` branch for Local Agent tasks. Never send Growbox tasks through another repository's control branch (for example LiteGraph).
4. Submit task requests under `.agent/tasks/<task-id>.json` on `agent-control`.
5. Follow execution through `.agent/runs/<task-id>.json` and `.agent/status/daemon.json`.
6. Read the terminal result from `.agent/results/<task-id>.json` before reporting completion.
7. Prefer remote status/results from GitHub over asking the user to copy local terminal logs when Local Agent can provide the state directly.
8. Keep repository workspaces isolated. A task for this repository must not read, modify, checkpoint, or publish results through another repository's Local Agent workspace.

### Control branch contract

`agent-control` is a control plane, not a development branch. Product/source changes belong on the requested source/work branch. The control branch is reserved for Local Agent queue, status, run, result, and daemon-control files under `.agent/`.

The canonical Local Agent implementation and operational documentation live in `MichalMatu/local-agent`. If the control protocol changes, update this bootstrap section so future chats do not depend on remembered conversation context.

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
