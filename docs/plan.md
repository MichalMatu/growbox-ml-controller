# Plan prac — kontrakt v2 i sterowanie

Żywy dokument: kolejność prac i ustalenia z analizy panelu / symulatora (2026-07).

**Źródło prawdy techniczne:** [`schemas/environment-controller-v1.json`](../schemas/environment-controller-v1.json) (obecnie v1; v2 w przygotowaniu).

**Indeks dokumentacji**

| Plik | Po co |
|------|--------|
| Ten plik | Plan, decyzje, co dalej |
| [IO_MAP.md](IO_MAP.md) | Mapowanie sprzętu → sloty kontraktu |
| [DATA_CONTRACT.md](DATA_CONTRACT.md) | Zasady kontraktu (krótko) |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Warstwy kodu |
| [MODEL_PIPELINE.md](MODEL_PIPELINE.md) | Trening i export (komendy) |
| [PORTING_TO_LITEGRAPH.md](PORTING_TO_LITEGRAPH.md) | Integracja z GrowClip (później) |
| [README.md](../README.md) | Setup, build, panel, serial |

---

## Ustalenia (nie retrenuj v1 na poważnie)

### Jak działa sterowanie

```text
Czujniki + cele + konfiguracja
        → FeatureEncoder (cechy 0..1)
        → ModelRuntime (propozycja raw)
        → SafetySupervisor (safe + powody)
        → mostek / symulator
```

- **Model** tylko proponuje wartości 0–1.
- **Safety** ma twarde reguły niezależne od modelu.
- **Checkbox „w systemie”** (`available`) = urządzenie wyłączone w scenariuszu; model widzi brak, safety wymusza 0.
- **Validity czujnika** = brak odczytu; encoder podstawia default + maskę.

### Co widać na żywo (v1, model `quick`)

| Objaw | Przyczyna |
|-------|-----------|
| Fan ~13% mimo `minimum_command ≈ 0` | Bias wgranej sieci (`raw.fan ≈ 0.13`), nie safety. Test MAE fana ~0.20. |
| Pompa ~9% przy glebie 100% | Ten sam słaby model; teacher przy pełnej glebie daje `irrigation=0`. |
| Mruganie `bez zmian` / `≠` na pompie | Rytm symulatora: model cały czas chce ~9%, co kilka kroków safety puszcza impuls vs `pump_minimum_interval`. |
| `fan min` w ustawieniach nic nie zmienia | Minimum to podłoga; model i tak proponuje ~13%. |

**Wniosek:** teacher i symulator treningowy są sensowne; **wgrany MLP v1 (`quick`) jest za słaby i uczył się na niepełnym kontrakcie**. Retrening na v1 przed domknięciem I/O to zmarnowany effort.

### Luka v1: firmware vs model

| Element | Panel / firmware | Kontrakt ML (40 cech) |
|---------|------------------|------------------------|
| `outside_co2_ppm` | tak | **nie** (CO₂ zewn. w treningu = stałe 420 ppm) |
| osuszacz | nie | nie |
| chłodzenie / klimatyzator | nie | nie |
| blokada pompy przy pełnej glebie | nie | — (brak reguły safety) |

---

## Cel: kontrakt v2 w docelowej formie

Pełny zestaw **nawet gdy sprzętu fizycznie nie ma** — każde urządzenie ma `available`, każdy czujnik ma `validity`. Trening losuje scenariusze włącz/wyłącz, żeby model uczył się obu trybów.

### Czujniki (plan v2)

| Czujnik | v1 | v2 |
|---------|----|----|
| temp / wilgotność / CO₂ / gleba (w środku) | tak | tak |
| temp / wilgotność na zewnątrz | tak | tak |
| CO₂ na zewnątrz | tylko JSON demo | **dodać do modelu** |
| VPD, liść, EC/pH | — | opcjonalnie później (v2.1) |

### Wyjścia (plan v2)

| Wyjście | v1 | v2 | Uwagi |
|---------|----|----|--------|
| grzałka | tak | tak | |
| fan | tak | tak | Jeden logiczny fan; wiele fizycznych → mapowanie w mostku LiteGraph |
| nawilżacz | tak | tak | |
| osuszacz | nie | **tak** | Osobne wyjście |
| chłodzenie (klimatyzator) | nie | **tak** | Osobno od grzałki |
| pompa | tak | tak | `irrigation_pulse_s` tylko po safety, nie w UI na żywo |
| światło | nie | **do decyzji** | Raczej harmonogram Nodeflow, nie ML — patrz pytania otwarte |

### Safety (plan — poza checkboxami)

Reguły „nigdy”, nawet gdy model chce inaczej:

| Reguła | Status v1 | v2 |
|--------|-----------|-----|
| max / alarm temperatury, min fan przy alarmie | tak | utrzymać |
| przerwa między impulsami pompy | tak | utrzymać |
| gleba ≥ cel (lub ≥ 95%) → pompa 0 | **nie** | **dodać** |
| deadband fana (np. raw &lt; 5% → 0) | nie | opcjonalna łata przed retreningiem |
| dwell binarnych (grzałka, nawilżacz, …) | częściowo | rozszerzyć o nowe aktuary |

### Co do ML, co poza ML

| Warstwa | Przykłady |
|---------|-----------|
| **ML** | Balans temp, RH, CO₂, gleby przy wielu dostępnych aktuatorach |
| **Safety** | Alarmy, pełna gleba, niedostępny czujnik, wymuszenie 0 na `available=false` |
| **Harmonogram / Nodeflow** | Światło dzień/noc, tryby użytkownika |
| **Mostek sprzętowy** | 1× `fan` → kilka fizycznych wentylatorów |

---

## Kolejność prac

### Faza 0 — zamrożenie v1 (teraz)

- [x] Zrozumieć objawy na panelu (bias modelu, nie UI)
- [x] Usunąć linię `impuls X s` z karty pompy (duplikat ustawień)
- [ ] **Nie** inwestować w dopieszczanie modelu v1 (`train-full` na starym kontrakcie)

### Faza 1 — spec v2 (krótka)

- [ ] Potwierdzić pytania otwarte (poniżej)
- [ ] Wypełnić [IO_MAP.md](IO_MAP.md) — kolumna „Twój sprzęt”
- [ ] Spisać listę pól w `schemas/environment-controller-v2.json`

### Faza 2 — kontrakt v2 w kodzie (jeden duży PR)

Kolejność wewnątrz fazy:

1. `schemas/environment-controller-v2.json` + generator → `EnvironmentSchema.h`
2. `EnvironmentTypes.h`, `FeatureEncoder`, `SafetySupervisor`
3. Symulator Python (`tools/ml/simulator.py`) + teacher (`teacher.py`) — ta sama fizyka
4. `DummyEnvironmentSimulator.cpp` + wire codec + panel (`form_schema.py`)
5. Testy kontraktu i hosta (wymiary, golden vectors — po retreningu)

### Faza 3 — safety v2

- [ ] Gleba nasączona → blokada pompy
- [ ] Reguły dla osuszacza / chłodzenia (np. wzajemne wykluczenia z grzałką — jeśli potrzebne)
- [ ] Zachowanie przy `validity=false` na krytycznych czujnikach

### Faza 4 — trening v2

- [ ] Dataset: losowe `available` / `validity` (jak dziś, rozszerzone)
- [ ] `make train-full` (nie `--quick`)
- [ ] Sprawdzić MAE per wyjście; odrzucić model z biasem „stałego 13%”
- [ ] Commit: schema + generated headers + golden vectors razem

### Faza 5 — walidacja użytkowa

- [ ] Panel: scenariusze z wyłączonymi aktuatorami
- [ ] Replay na płytce
- [ ] Dopiero potem LiteGraph ([PORTING_TO_LITEGRAPH.md](PORTING_TO_LITEGRAPH.md))

---

## Pytania otwarte (przed Fazą 2)

1. **Światło** — wyjście ML czy tylko harmonogram?
2. **Klimatyzator vs osuszacz** — plan: dwa osobne wyjścia; potwierdź.
3. **Dwa wentylatory** — jedno wyjście `fan` + mapowanie, czy dwa wyjścia ML?

---

## Komendy (bez zmian)

```bash
make panel                    # panel WWW
make train-quick              # tylko smoke CI — nie produkcyjny model
make train-full               # po v2
python tools/schema/generate_environment_schema.py --check
```

---

## Notatka dla treningu v2

Teacher używa dyskretnej siatki akcji (np. fan: 0 / 0.25 / 0.5 / 0.75 / 1.0). Model regresuje na ciągłe sigmoidy — stąd biasy przy słabym treningu. Przy v2 rozważyć: więcej scenariuszy, `train-full`, rozkład `fan_minimum_command` obejmujący ~0, ewentualnie ważenie błędów per wyjście.
