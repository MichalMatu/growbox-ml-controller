# Mapowanie I/O

**Aktywny kontrakt (v4, pots):** [`schemas/environment-controller.json`](../schemas/environment-controller.json)
**Pełna lista cech ML:** [simulator/IO_INVENTORY.md](simulator/IO_INVENTORY.md)
**Research fizyki symulatora:** [simulator/README.md](simulator/README.md)

> Ten plik historycznie mówił o „v2 / strefach”. **Kod i schema używają `pots` (donice).**
> Gdzie poniżej zostaje słowo „strefa” w starych tabelach, czytaj **donica / pot**.

Kontekst produktowy: [plan.md](plan.md) → *Wizja produktu*.

## Sensing — ZAMKNIĘTE (v4)

**Temat czujników domknięty.** Nie dodajemy kolejnych pomiarów bez nowej wersji kontraktu. Każdy slot: **mix & match** (`validity` lub brak integracji przy pseudo-wejściu).

| Grupa | Sloty (15 + 1 pseudo) | W kontrakcie |
|-------|------------------------|--------------|
| **Powietrze w boxie** | `air_temperature_c`, `air_humidity_pct`, `co2_ppm` | tak |
| **Zbiornik nawozu** | `nutrient_solution_temperature_c` | tak |
| **Powietrze przy wlocie** | `outside_temperature_c`, `outside_humidity_pct`, `outside_co2_ppm` | tak |
| **Gleba ×4 donice** | `soil_moisture_pot_1…4_pct`, `soil_temperature_pot_1…4_c` | tak |
| **Pseudo (nie czujnik)** | `lights_active` | tak — harmonogram / readback, nie PPFD |

**Zasady sensing (zamknięte):**

- Jedna komora → **jeden** zestaw `air_*` + `co2_ppm`; donice **nie** mają własnego klimatu powietrza.
- Wilgotność i temp. gleby per donica = **dwa niezależne** sloty (`validity` osobno).
- Temp. powietrza ≠ temp. gleby ≠ temp. roztworu — trzy osobne sloty.
- VPD **nie** jest wejściem ML — wyliczenie w panelu z temp.+RH.
- Brak sprzętu = `validity: false` (encoder: default + maska), nie usuwanie slotu z kontraktu.

**Świadomie poza v2 (nie sensing tej wersji):** PPFD, temp. liścia, EC/pH, zalanie, wylot wentylacji, stacja pogodowa — [roadmap](#świadomie-poza-v2--roadmap-mentalny-obraz).

**Poza zamknięciem sensing (Faza 2+):** `lights_active` i maski `zone_N_available` w `FeatureEncoder`; **staleness** Zigbee (timestamp ostatniego raportu) — integracja mostka, nie nowe sloty pomiarowe.

Szczegóły montażu → sekcje poniżej. **Wyjścia ML** → [Wyjścia ML](#v2--wyjścia-ml-zamknięte-10-slotów).

## Kontrakt v2 — definitywny (I/O)

**Zamknięte 2026-07.** Stała lista slotów — **nie dodajemy** nowych czujników ani wyjść ML w tej wersji.

### Mix & match — każdy slot osobno

W produkcie **każdy wiersz** z checklisty = osobny checkbox w konfiguracji / panelu. Żaden pakiet nie jest wymagany; dowolna kombinacja.

| Typ | Zaznaczone ☑ | Odznaczone ☐ |
|-----|--------------|--------------|
| **Czujnik** | `validity.<slot> = true` + odczyt z mostka | `validity.<slot> = false` — encoder: default + maska |
| **Wyjście ML** | `actuators.<slot>.available = true` | `available = false` — model widzi brak; safety → 0 |
| **Strefa N** | `pots[N].available = true` | strefa wyłączona w profilu (sloty strefy ignorowane) |
| **Światło (pseudo)** | harmonogram / readback → `lights_active` | brak integracji lampy — `lights_active` z planu lub false |

**Checklista v2 (26 slotów + 4× `pots[N].available` opcj.):**

| # | Slot | Grupa | ☐ = |
|---|------|-------|-----|
| 1 | `air_temperature_c` | wewn. | `validity: false` |
| 2 | `air_humidity_pct` | wewn. | `validity: false` |
| 3 | `co2_ppm` | wewn. | `validity: false` |
| 4 | `nutrient_solution_temperature_c` | zbiornik | `validity: false` |
| 5 | `outside_temperature_c` | zewn. | `validity: false` |
| 6 | `outside_humidity_pct` | zewn. | `validity: false` |
| 7 | `outside_co2_ppm` | zewn. | `validity: false` |
| 8 | `soil_moisture_pot_1_pct` | strefa 1 | `validity: false` |
| 9 | `soil_temperature_pot_1_c` | strefa 1 | `validity: false` |
| 10 | `irrigation_pot_1` | strefa 1 | `pots[0].irrigation.available: false` |
| 11 | `soil_moisture_pot_2_pct` | strefa 2 | `validity: false` |
| 12 | `soil_temperature_pot_2_c` | strefa 2 | `validity: false` |
| 13 | `irrigation_pot_2` | strefa 2 | `pots[1].irrigation.available: false` |
| 14 | `soil_moisture_pot_3_pct` | strefa 3 | `validity: false` |
| 15 | `soil_temperature_pot_3_c` | strefa 3 | `validity: false` |
| 16 | `irrigation_pot_3` | strefa 3 | `pots[2].irrigation.available: false` |
| 17 | `soil_moisture_pot_4_pct` | strefa 4 | `validity: false` |
| 18 | `soil_temperature_pot_4_c` | strefa 4 | `validity: false` |
| 19 | `irrigation_pot_4` | strefa 4 | `pots[3].irrigation.available: false` |
| 20 | `lights_active` | pseudo | brak lampy w setupie |
| 21 | `heater` | wyjście | `available: false` |
| 22 | `fan` | wyjście | `available: false` |
| 23 | `humidifier` | wyjście | `available: false` |
| 24 | `dehumidifier` | wyjście | `available: false` |
| 25 | `cooler` | wyjście | `available: false` |
| 26 | `co2_doser` | wyjście | `available: false` |

Opcjonalnie **4×** `pots[N].available` — chowa całą donicę w profilu (nie zastępuje checkboxów wilgotności / pompy).

**Safety przy odznaczonych:** pompa bez valid wilgotności → brak podlewania; `co2_doser` bez valid `co2_ppm` → blokada; brak temp. wewn. → ograniczona regulacja klimatu (alarmy wg `SafetyConfig`).

**Poza checklistą v2:** PPFD, EC/pH, światło jako wyjście ML — [roadmap](#świadomie-poza-v2--roadmap-mentalny-obraz).

### Profil prosty (jedna kombinacja checkboxów)

**2× BLE TP357** (wewn. + zewn.) — zaznaczone tylko: #1, #2, #5, #6; reszta czujników ☐; wyjścia klimatu wg posiadanego sprzętu; #26 `co2_doser` ☐.

## Przepływ

```text
ControllerInput → FeatureEncoder → ModelRuntime → SafetySupervisor → safe_output
```

## Czujniki wewnątrz growboxa — zestaw v2 (zamknięty)

Tylko **pomiary**. Aktuary — sekcja niżej. **Zewnątrz** — następna sekcja. **Roadmap** czujników — na końcu pliku.

| # | Slot kontraktu | Gdzie fizycznie | Mix & match | Osobna `validity` | v1 | Uwagi |
|---|----------------|-----------------|-------------|-------------------|----|--------|
| 1 | `air_temperature_c` | powietrze, wysokość korony | ☑/☐ | tak | tak | jeden na cały box |
| 2 | `air_humidity_pct` | powietrze, przy temp. | ☑/☐ | tak | tak | RH w komorze |
| 3 | `co2_ppm` | powietrze, strefa liści | ☑/☐ | tak | tak | enrichment tylko gdy ☑ + `co2_doser` ☑ |
| 4 | `nutrient_solution_temperature_c` | **zbiornik odżywki** / linia przed pompą | ☑/☐ | tak | nie | **DS18B20**; ≠ temp. gleby |
| 5 | `soil_moisture_pot_1_pct` | substrat, strefa 1 | ☑/☐ | tak | jeden globalny | pompa sensowna gdy ☑ wilgotność |
| 6 | `soil_temperature_pot_1_c` | substrat, strefa 1 | ☑/☐ | tak | nie (v2) | niezależnie od wilgotności |
| 7–10 | wilg. + temp. gleby | strefy 2–4 | ☑/☐ każdy | tak | — | + `pots[N].available` per donica |

**Trzy różne temperatury (nie mylić):**

| Pomiar | Gdzie | Po co |
|--------|--------|--------|
| `air_temperature_c` | powietrze w boxie | klimat, grzałka, fan |
| `soil_temperature_pot_N_c` | donica / substrat | korzenie, stres cieplny gleby |
| `nutrient_solution_temperature_c` | zbiornik nawozu | **nie lać zimnym roztworem na rozgrzaną ziemię** |

Wewnątrz **zamknięte na v2** — bez dalszych czujników w komorze (patrz *Świadomie poza v2*).

**Twój sprzęt (do wypełnienia):**

| Strefa / slot | Model / integracja | Zamontowany |
|---------------|-------------------|-------------|
| temp. powietrza | | |
| wilgotność powietrza | | |
| CO₂ powietrza | | |
| temp. roztworu nawozu (zbiornik) | DS18B20 | wspólny zbiornik |
| gleba 1 — wilgotność | | |
| gleba 1 — temp. | DS18B20 / inny | opcjonalnie, **osobny** od wilgotności |
| gleba 2 — wilgotność | | wyłączona |
| gleba 2 — temp. | | |
| gleba 3 — wilgotność | | |
| gleba 3 — temp. | | |
| gleba 4 — wilgotność | | |
| gleba 4 — temp. | | |

## Czujniki na zewnątrz growboxa — zestaw v2 (zamknięty)

**„Zewnątrz”** = klimat **wlotu** świeżego powietrza (pokój przy namiocie / skrzyni), nie pełna stacja pogodowa — chyba że masz rurę z okna (te same 3 sloty, inny montaż).

| # | Slot kontraktu | Gdzie fizycznie | Mix & match | Osobna `validity` | v1 ML | Uwagi |
|---|----------------|-----------------|-------------|-------------------|-------|--------|
| 1 | `outside_temperature_c` | przy wlocie powietrza | ☑/☐ | tak | tak | np. TP357 zewn. |
| 2 | `outside_humidity_pct` | przy wlocie | ☑/☐ | tak | tak | niezależnie od #1 w UI, zwykle para z czujnika |
| 3 | `outside_co2_ppm` | przy wlocie | ☑/☐ | tak | **nie**³ | tło CO₂ przy wencie gdy ☑ |

³ W panelu/firmware już jest; brakuje tylko w kontrakcie ML v1.

**Zewnątrz zamknięte na v2** — 3 czujniki wystarczą na komercyjny SKU.

**Twój sprzęt (do wypełnienia):**

| Slot | Model / integracja | Zamontowany |
|------|-------------------|-------------|
| temp. zewn. | | |
| wilgotność zewn. | | |
| CO₂ zewn. | | opcjonalnie ten sam moduł co w środku |

## Pseudo-wejście (nie czujnik)

| Sygnał | Źródło | Mix & match |
|--------|--------|-------------|
| `lights_active` | harmonogram + readback przekaźnika LED | ☑ lampa w systemie — **wejście ML** + termika (patrz niżej) |

### `lights_active` — po co w sensing

Wejście ML + **obciążenie cieplne** w symulatorze treningowym. **Nie** wyjście ML — przekaźnik lampy: harmonogram / Nodeflow; przy upale: safety OFF.

Setki sprzężeń (lampa grzeje, fan vs zewnątrz, brak grzałki…) **nie są listą w tym pliku** — [plan.md](plan.md) → *Model złożoności*; implementacja w `simulator.py` i safety.

## v2 — strefy podlewania (max 4)

**Strefa = donica w tym samym growboxie** — nie osobna komora, nie osobny klimat powietrza.

```text
Jeden growbox, jedno powietrze w komorze:
  air_temperature_c, air_humidity_pct, co2_ppm  ← wspólne dla całego boxa

Cztery donice (strefy 1–4) w tym samym boxie:
  per donica: wilgotność gleby ☑/☐, temp. gleby ☑/☐, pompa ☑/☐
  pots[N].available — czy w ogóle masz N-tą donicę (mix & match sprzętu)
```

**Fizyka (nie w tym pliku):** jedna komora; **do 4 slotów** donic w symulatorze — **mix & match** jak w kontrakcie (0–4 aktywne, reszta wyłączona w scenariuszu). Sprzężenia T↔RH↔gleba↔fan → [plan.md](plan.md) → *Symulator — termodynamika growboxa*.

Mix & match dotyczy **które donice i sprzęt** masz w profilu — nie osobnych komór klimatycznych.

## JSON (kierunek v2)

```json
{
  "sensors": {
    "air_temperature_c": 24,
    "air_humidity_pct": 58,
    "co2_ppm": 900
  },
  "validity": {
    "air_temperature_c": true,
    "air_humidity_pct": true,
    "co2_ppm": true
  },
  "pots": [
    {
      "available": true,
      "sensors": { "soil_moisture_pct": 44, "soil_temperature_c": 21.5 },
      "validity": {
        "soil_moisture_pct": true,
        "soil_temperature_c": true
      },
      "targets": { "soil_moisture_pct": 55 },
      "irrigation": {
        "available": true,
        "flow_ml_s": 10,
        "maximum_pulse_s": 4,
        "minimum_interval_s": 600,
        "control_type": "pwm"
      },
      "previous": { "irrigation": 0 }
    }
  ]
}
```

Przykład: tylko wilgotność — `validity.soil_temperature_c: false` (brak DS18B20). Temp. i wilgotność **nie muszą** pochodzić z jednego modułu.

## Wyjścia ML (v4, 15 slotów)

Wartości ciągłe `[0, 1]`. Safety może wymusić 0, skwantować binarnie (`co2_doser`) lub ograniczyć impuls pompy. **Światło nie jest wyjściem ML** — patrz *Poza wyjściami ML*.

### Globalne (7)

| # | Slot | Fizycznie | Mix & match | Uwagi |
|---|------|-----------|-------------|--------|
| 1 | `heater` | grzałka powietrza | ☑/☐ | dwell on/off |
| 2 | `fan` | wentylacja (intake/exhaust) | ☑/☐ | **blokada CO₂** gdy fan &gt; próg |
| 3 | `humidifier` | nawilżacz | ☑/☐ | |
| 4 | `dehumidifier` | osuszacz | ☑/☐ | osobne od `cooler` |
| 5 | `cooler` | klimatyzator / chłodzenie | ☑/☐ | osobne od grzałki i osuszacza |
| 6 | `co2_doser` | elektrozawór butli CO₂ | ☑/☐ | impulsy; sens gdy `co2_ppm` ☑ |
| 7 | `nutrient_heater` | grzałka zbiornika odżywki | ☑/☐ | osobne od temp. gleby |

### Donice — pompy i maty (8)

| # | Slot | Fizycznie | Mix & match | Uwagi |
|---|------|-----------|-------------|--------|
| 8–11 | `irrigation_pot_1…4` | pompa donicy N | ☑/☐ | `pots[N-1].irrigation.available` |
| 12–15 | `heat_mat_pot_1…4` | mata pod donicą N | ☑/☐ | `pots[N-1].heat_mat.available` |

```text
ML (15):     heater, fan, humidifier, dehumidifier, cooler, co2_doser, nutrient_heater
             + irrigation_pot_1…4 + heat_mat_pot_1…4
Poza ML:     lights (harmonogram → lights_active jako wejście)
Mostek:      1× fan → N relay; światło → przekaźnik LED
```

### Poza wyjściami ML (świadomie)

| Element | Gdzie |
|---------|--------|
| **Światło LED** | Nodeflow / harmonogram + readback → `lights_active` |
| **Drugi wentylator** | mostek pod jednym `fan` |
| **Perystaltyka nawozu / EC-pH** | roadmap hydro |

Szkic kontraktu: [`environment-controller.json`](../schemas/environment-controller.json) → `model.outputs`.

## Świadomie poza v2 — roadmap (mentalny obraz)

To **nie braki przypadkowe** — świadoma kolejność produktu. v2 = **substrat**, klimat w boxie, CO₂ z butli, do **4 donic**, jeden sterownik, jedna linia firmware.

```text
v2 (SKU bazowy)     klimat + gleba + CO₂ + 4× podlewanie
    ↓
v2.1 (hydro /+)     EC/pH, zalanie, PPFD, VPD w ML
    ↓
v2.2+ (premium)     liść IR, wylot wentylacji, stacja pogodowa
    ↓
poza ML             harmonogram, interlocki, UI, support
```

### v2 — zamknięte (co jest w kontrakcie)

| Warstwa | Zakres | Status |
|---------|--------|--------|
| **Wejścia** | 15 czujników + `lights_active` — **każdy ☑/☐** | zamknięte |
| **Wyjścia ML** | 10 aktuatorów — **każdy ☑/☐** | zamknięte |
| **Pseudo-wejście** | `lights_active` z harmonogramu / przekaźnika | zamknięte |
| **Wyjścia ML** | 6 globalnych + 4 pompy | **zamknięte** |
| **Poza ML** | światło, mostek fanów | harmonogram / mostek |
| **Safety v2** | pełna gleba → pompa 0; ΔT roztwór–gleba; fan → blok CO₂ | plan v2 (Faza 3) |

### v2 — świadomie NIE ma (i dlaczego)

| Element | Dlaczego nie w v2 |
|---------|-------------------|
| **PPFD / nasłonecznienie** | światło = harmonogram + readback; dimmer to serwis, nie ML |
| **Światło jako wyjście ML** | faza rośliny i fotoperiod w Nodeflow / panelu |
| **EC / pH** | segment hydro (DWC), nie substrat — v2.1 |
| **VPD jako cecha ML** | wystarczy temp.+RH; VPD tylko w UI |
| **Temp. liścia (IR)** | koszt, kalibracja, niszowy ROI — v2.2+ |
| **Czujnik wylotu** (ΔT, ΔRH) | diagnostyka HVAC, nie podstawowy growbox |
| **Drugi fan w ML** | jedno `fan` + mostek na N fizycznych wentylatorów |
| **Mata grzewcza per donica** | tylko globalna grzałka powietrza |
| **Dozowanie nawozu per strefa** (perystaltyka) | osobny produkt / hydro — nie pompa wody |
| **Wiele zbiorników roztworu** | jeden `nutrient_solution_temperature_c` na sterownik |
| **Czujnik zalania** | safety alarmowy — v2.1, poza encoderem ML |
| **Stacja pogodowa** (wiatr, deszcz, ciśnienie) | montaż tunelowy / outdoor — v2.2+ |
| **PM2.5 / VOC** | komfort człowieka, nie agronomia |
| **Retrening / dopieszczanie v1** | zmarnowany effort przed domknięciem I/O |

### v2.1 — hydro / agronomia / safety+

| Element | Po co | Warstwa |
|---------|--------|---------|
| `ec_ms_cm`, `ph` | kultywacja w wodzie, balans składników | wejście ML |
| `ppfd_umol` | weryfikacja lampy, kalibracja dimmera | wejście ML lub UI |
| `vpd_kpa` w encoderze | opcjonalna cecha (wyliczona) | wejście ML |
| czujnik **zalania** | alarm podłogi / przelewania | **safety**, nie ML |
| osobny zbiornik × strefa | wiele `nutrient_solution_temperature_*` | wejście + safety |

### v2.2+ — diagnostyka / premium / outdoor

| Element | Po co |
|---------|--------|
| temp. **liścia** (IR) | stres świetlny, VPD przy liściu |
| czujnik **wylotu** powietrza | sprawność wentylacji, Δ wewn./wewn. |
| **dual CO₂** (różnica wlot–wylot) | wyciek, nieszczelność namiotu |
| **ciśnienie** / wiatr / deszcz | tunel do ogrodu, intake z okna |
| PM2.5 / VOC | jakość powietrza (pokój growera) |
| **dimmer światła** w ML | tylko gdy PPFD + polityka produktu |

### Poza kontraktem ML (zawsze, każda wersja)

| Element | Gdzie działa |
|---------|----------------|
| VPD, wilgotność względna w UI | panel — wyliczenia z czujników |
| harmonogram światła, tryby użytkownika | Nodeflow / panel |
| `available` / `validity` / staleness Zigbee | mostek + encoder |
| `safety_reason`, `output_reason_masks` | SafetySupervisor + UI support |
| wersja kontraktu / modelu w logu | OTA, debug u klienta |
| interlocki obudowy (dym, przepięcie) | hardware, poza tym repo |
| mapowanie 1× `fan` → kilka relay | mostek sprzętowy |
| warstwa ML jako Pro / opcjonalna | decyzja biznesowa, nie slot |

Pełny kontekst produktu i fazy wdrożenia: [plan.md](plan.md) → *Roadmap produktu*.

## v1 (obecny firmware)

Jedna `soil_moisture_pct`, jedno `irrigation` — zastąpione modelem strefowym w v2.

Preset v1: `tools/panel/form_schema.py` (`NOMINAL_PRESET`).
