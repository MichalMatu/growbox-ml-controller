# Plan prac — kontrakt v2 i sterowanie

Żywy dokument: kolejność prac i ustalenia z analizy panelu / symulatora (2026-07).

**Źródło prawdy techniczne:** v1 w kodzie — [`environment-controller-v1.json`](../schemas/environment-controller-v1.json); **I/O v2 definitywne** — tabelka w [IO_MAP.md](IO_MAP.md) → *Kontrakt v2*.

**Indeks dokumentacji**

| Plik | Po co |
|------|--------|
| Ten plik | Plan, decyzje, co dalej |
| [IO_MAP.md](IO_MAP.md) | Mapowanie sprzętu → sloty kontraktu |
| [DATA_CONTRACT.md](DATA_CONTRACT.md) | Zasady kontraktu (krótko) |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Warstwy kodu |
| [MODEL_PIPELINE.md](MODEL_PIPELINE.md) | Trening, export, **fidelity symulatora** |
| [PORTING_TO_LITEGRAPH.md](PORTING_TO_LITEGRAPH.md) | Integracja z GrowClip (później) |
| [README.md](../README.md) | Setup, build, panel, serial |

---

## Model złożoności — jak nie płatać

Growbox ma **setki** sprzężeń (T, RH, gleba, fan, zewnątrz, lampa, CO₂…). **Nie wypisujemy ich w dokumentacji** ani w kontrakcie JSON — inaczej dokumentacja się nigdy nie kończy i rozjeżdża z kodem.

```text
ZAMKNIĘTE (nie ruszamy bez v2.1)     →  sloty I/O: sensing + 10 wyjść ML  [IO_MAP.md]
JEDNO ŹRÓDŁO PRAWDY FIZYKI         →  tools/ml/simulator.py (+ ten sam model w DummyEnvironmentSimulator)
KRÓTKA LISTA TWARDYCH REGUŁ        →  SafetySupervisor (~10–15 reasonów, nie setki ifów w docs)
HARMONOGRAM / NODEFLOW             →  fotoperiod, opcj. dogrzewanie lampą — poza ML
ML                                 →  uczy się koordynacji z trajektorii symulatora (nie z README)
```

| Pytanie | Odpowiedź |
|---------|-----------|
| Czy muszę opisać każdą zależność, o której pomyślę? | **Nie** — tylko dodać **składnik** do symulatora, jeśli brakuje w trajektoriach. |
| Co robią luźne akapity o lampie / fanie / grzałce w docs? | **Przykłady** kategorii (termika, wymiana z zewnątrz), nie komplet reguł. |
| Skąd wiem, że nic ważnego nie ginie? | Iteracja: symulator → trening → **replay na żywym boxie** → korekta współczynników. |
| Co jest „domknięte” na dziś? | **Sensing** + **wyjścia ML** + mix & match. Reszta = **Faza 2–4 (kod)**. |

**Nie dokładamy** kolejnych akapitów zależności do `IO_MAP.md` — tylko nowe **sloty** (v2.1+). Zachowanie termiczne → symulator + safety + issue/PR, nie kolejna sekcja w mapowaniu sprzętu.

Szkic polityk termicznych (lampa, grzałka, fan vs `outside_*`) — implementacja Fazy 2–3: [poniżej *Symulator — termodynamika*](#symulator--termodynamika-growboxa-trening) i safety; szczegóły w kodzie, nie w checklistie czujników.

---

## Wizja produktu — komercyjny sterownik

Ten projekt nie jest „kontrolerem jednego growboxa użytkownika”. Celem jest **sterownik na sprzedaż**:
konfigurowalny, przewidywalny, z jasnym safety — z opcjonalną warstwą ML jako wartością dodaną.

Repozytorium `growbox-ml-controller` to dziś **rdzeń decyzyjny** (kontrakt, encoder, model, safety, demo).
Produkt końcowy to opakowanie: panel, konfiguracja stref, integracja czujników (np. Tuya Zigbee),
mostek aktuatorów, wsparcie, firmware na ESP — ścieżka GrowClip / LiteGraph ([PORTING_TO_LITEGRAPH.md](PORTING_TO_LITEGRAPH.md)).

### Hobby vs produkt

| Hobby (jedna instalacja) | Produkt komercyjny |
|--------------------------|-------------------|
| Znam swój sprzęt | Klient: **1–4 strefy**, różna konfiguracja, część wyłączona |
| „Działa u mnie” | **Przewidywalne** zachowanie + safety + opis w UI |
| ML można ciągle poprawiać ad hoc | **Jedna linia firmware** + konfiguracja, nie fork na klienta |
| Integracja „u mnie w HA” | Oficjalna ścieżka: czujnik → hub → mostek → sloty kontraktu |
| Brak sprzętu = nie istnieje | **Mix & match:** każdy slot osobno — czujnik `validity: false`, aktuator `available: false`; reszta działa |

### Warstwy produktu

```text
Warstwa klienta      panel / aplikacja — ile stref aktywnych (1–4), cele, safety
Warstwa integracji   Zigbee (Tuya), przekaźniki, pompy — GrowClip / Nodeflow
Warstwa decyzji      FeatureEncoder + ModelRuntime + SafetySupervisor  ← to repo
Warstwa sprzętu      ESP32, GPIO, obudowa, certyfikacja (poza tym repo)
```

- **Safety i reguły** — to, co klient traktuje jako „bezpieczny sterownik”; muszą działać nawet przy słabym ML.
- **ML** — propozycja sterowania klimatem globalnym; w produkcie może być domyślne lub warstwa Pro (decyzja biznesowa później).
- **Symulator / trening** — R&D wewnętrzne: **możliwie wierna termodynamika growboxa** (złożone sprzężenia T↔RH↔gleba); klient widzi kontrakt i zachowanie, nie pipeline Keras.

### SKU i konfiguracja (v2)

| Element produktu | Decyzja techniczna |
|------------------|-------------------|
| Do **4 donic** na jednym sterowniku | Max **4 strefy** w kontrakcie |
| Strefa = donica | **Wilgotność gleby (wym.) + pompa**; temp. gleby **opcjonalna** per strefa |
| Klient ma dziś 1 donicę | Włączona **strefa 1**; 2–4 `available: false` |
| Czujniki gleby | Tanie (tylko wilg.) lub premium (wilg. + temp., np. Tuya) — ten sam kontrakt, różne `validity` |
| Klimat boxa | Globalne: temp / RH / CO₂ — **każdy slot osobno** ☑/☐ (+ zewnątrz, to samo) |
| Enrichment CO₂ | Butla + **zawór dozujący** — osobne wyjście; dozowanie głównie gdy **fan wyłączony** |
| Aktuary globalne | Grzałka, fan, nawilżacz, osuszacz, chłodzenie, **CO₂ zawór** — slot + `available` |

### Wymagania komercyjne (do wdrożenia poza samym ML)

- **Profil konfiguracji** — liczba aktywnych stref bez przebudowy firmware.
- **Profile czujników gleby** — „wilgotność only” vs „wilgotność + temp.”; lista wspieranych integracji (Tuya, ADC, …).
- **Nieaktualne dane Zigbee** — ostatni raport + `validity` / staleness (bateria, raport co kilka minut).
- **Powody safety** w UI (`safety_reason`, `output_reason_masks`) — wsparcie i debug u klienta.
- **Wersja kontraktu / modelu** w logu i panelu — zgodność OTA i support.

### Konsekwencje dla planu prac

1. Kontrakt **v2** projektujemy pod produkt (strefy, pełne sloty, `available`), nie pod jedną instalację.
2. **Nie** dopieszczać modelu v1 — klient dostanie v2 po domknięciu I/O.
3. Panel i JSON scenariusza muszą odzwierciedlać **strefy** i włącz/wyłącz sprzętu jak w finalnym UI.
4. Integracja LiteGraph to **produkcja**, demo UART to **laboratorium**.

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

### Klimat wewnątrz growboxa (plan v2) — zamknięta lista

**Globalne** (jeden zestaw na cały box) — **nic więcej na start v2**:

| Czujnik | v2 | Uwagi |
|---------|-----|--------|
| `air_temperature_c` | **tak** | korona / środek komory |
| `air_humidity_pct` | **tak** | |
| `co2_ppm` | **opcj.** | slot zawsze; `validity: false` bez czujnika (np. profil 2× TP357) |
| `nutrient_solution_temperature_c` | **opcjonalnie** | DS18B20 w zbiorniku odżywki; **≠** temp. gleby w donicy |

Nie dodajemy na v2: **czujnik nasłonecznienia / PPFD** (zastępuje stan lampy), temp. liścia, VPD osobno, EC/pH (v2.1 / hydro). Światło = harmonogram, nie wyjście ML.

**Temp. odżywki vs temp. gleby:** osobne pola. Safety (i opcjonalnie ML) porównuje oba przed podlewaniem — unikaj zimnego nawozu na rozgrzany substrat (konfigurowalny max ΔT lub min. temp. roztworu). Głównie **safety**; ML widzi obie cechy w treningu.

**Zewnątrz** (zamknięte na v2): `outside_temperature_c`, `outside_humidity_pct`, `outside_co2_ppm` — każdy ☑/☐ — [IO_MAP.md](IO_MAP.md) → *Sensing v2*.

**Roadmap** (czujniki, aktuary, safety, poza ML): [IO_MAP.md](IO_MAP.md) → *Świadomie poza v2* oraz sekcja *Roadmap produktu* poniżej.

### Strefy podlewania — max 4 (ustalone 2026-07)

**Jedna strefa = jedna donica w tym samym growboxie** — wspólne powietrze (`air_*`, `co2_ppm`); per donica: czujnik gleby + pompa (indeks 1…4). Podlewanie **zawsze** wpływa na RH (i pośrednio na T) w całej komorze — wielkość efektu zależy od scenariusza; symulator v2 modeluje sprzężenia T↔RH↔gleba↔fan↔zewnątrz. **ML** uczy sterowania w tym układzie, nie zastępuje fizyki w runtime (fizyka = symulator treningowy + reguły safety).

| Per strefa `zones[i]` | Wymagane? | Uwagi |
|----------------------|-----------|--------|
| `soil_moisture_pct` + `validity` | **tak** (gdy strefa aktywna) | Podlewanie; źródło dowolne (ADC, Zigbee, Tuya…) |
| `soil_temperature_c` + `validity` | **nie** | **Osobne, niepowiązane wejście** — np. **DS18B20** (1-Wire) |
| `target_soil_moisture_pct` | tak | cel tej donicy |
| pompa + `available`, parametry | tak | `irrigation_zone_N` |
| `previous_irrigation` | tak | per strefa |

**Wilgotność i temp. gleby = dwa niezależne wejścia** (osobne ścieżki JSON, osobne `validity`, osobni driverzy w mostku). **Brak** założenia „jeden moduł 2-w-1”:

```text
Strefa 1:  soil_moisture ← sonda wilgotności     validity_moisture
           soil_temperature ← DS18B20 w donicy     validity_temperature   (niezależnie!)
```

Przykłady kombinacji:

| Wilgotność | Temp. gleby | validity |
|------------|-------------|----------|
| Tuya Zigbee | brak | moist=true, temp=false |
| ADC / tanie | DS18B20 | oba true, **różne hardware** |
| Tuya 2-w-1 | ten sam moduł | oba true — mostek wypełnia oba sloty |

Szkic pól: [`schemas/environment-controller-v2.json`](../schemas/environment-controller-v2.json) (draft, nie w CI).

Mostek ustawia `validity`; encoder podstawia default + maskę (jak przy innych czujnikach). Safety i podlewanie **nie zależą** od temp. gleby. Reguły na temp. gleby (np. zimna gleba) tylko gdy `soil_temperature_c` valid.

Nieużywane strefy: `zone.available = false`. Trening losuje: strefa z/bez temp. gleby, 1–4 aktywne strefy.

**Wyjścia ML:** `irrigation_zone_1` … `irrigation_zone_4`. Safety: `irrigation_zone_N_pulse_s` per strefa.

### Wyjścia ML v2 (zamknięte — 10 slotów)

Tabela sprzętu: [IO_MAP.md](IO_MAP.md) → *Wyjścia ML*. Szkic: `schemas/environment-controller-v2.json`.

| Wyjście | v1 | v2 | Uwagi |
|---------|----|----|--------|
| `heater` | tak | tak | |
| `fan` | tak | tak | Wymiana powietrza — **konflikt z dozowaniem CO₂** (patrz niżej) |
| `humidifier` | tak | tak | |
| `dehumidifier` | nie | **tak** | Osobne wyjście (potwierdzone) |
| `cooler` | nie | **tak** | Osobno od grzałki i osuszacza (potwierdzone) |
| `co2_doser` | nie | **tak** | Binarny impuls; `available` gdy brak butli |
| `irrigation_zone_1…4` | jedna pompa | **tak** | 0–4 aktywnych; per strefa safety |
| światło | nie | **poza ML** | Harmonogram + `lights_active` jako **wejście**; obciążenie cieplne lampy w symulatorze; OFF przy alarmie T |

### Dozowanie CO₂ z butli (ustalone 2026-07)

**Sprzęt:** butla CO₂ + elektrozawór (on/off). Pomiar `co2_ppm` zostaje **czujnikiem**, zawór to **aktuator**.

**Logika produktowa:** CO₂ dozujemy tylko w „oknie”, gdy wentylacja **nie wyrzuca** gazu — typowo **fan wyłączony** (lub poniżej progu). Wentylator służy do wymiany / chłodzenia; enrichment to osobna faza.

```text
Model / reguła proponuje co2_doser
        → Safety: jeśli safe.fan > próg → co2_doser = 0  (powód: fan_venting_co2)
        → Safety: jeśli co2_ppm ≥ cel → co2_doser = 0
        → Safety: alarm temp. / brak czujnika CO₂ → blokada
        → tylko gdy `lights_active` z harmonogramu (bez czujnika PPFD)
```

| Warstwa | Rola |
|---------|------|
| **Safety (twarde)** | Brak CO₂ przy włączonym wencie; przy CO₂ ≥ cel; przy alarmach |
| **ML (miękkie)** | Kiedy w oknie fan=0 — ile / czy dawkować (jeśli w ogóle w ML) |
| **Konfiguracja** | `co2_doser`: przepływ / czas impulsu, min. przerwa między dawkami, próg „fan uznany za włączony” |

W treningu symulator musi modelować: dawka CO₂ podnosi `co2_ppm`, fan obniża w stronę `outside_co2`. Teacher uczy sekwencji „najpierw fan off, potem doza”.

**Nie mylić:** `co2_ppm` (czujnik) ≠ `co2_doser` (zawór). Cel `target_co2_ppm` już jest w kontrakcie.

### Safety (plan — poza checkboxami)

Reguły „nigdy”, nawet gdy model chce inaczej:

| Reguła | Status v1 | v2 |
|--------|-----------|-----|
| max / alarm temperatury, min fan przy alarmie | tak | utrzymać |
| przerwa między impulsami pompy | jedna pompa | **osobny licznik per strefa** |
| gleba strefy N ≥ cel → pompa N = 0 | **nie** | **dodać (per strefa)** |
| **ΔT roztwór–gleba** zbyt duże → blokada pompy N | nie | **dodać** (gdy oba `valid`) |
| roztwór zbyt zimny → blokada podlewania | nie | **dodać** (próg w `SafetyConfig`) |
| **fan &gt; próg → co2_doser = 0** | nie | **dodać** (`fan_venting_co2` / podobny reason) |
| **co2_ppm ≥ cel → co2_doser = 0** | nie | **dodać** |
| przerwa między dawkami CO₂ | — | jak u pompy — min. interwał |
| deadband fana (np. raw &lt; 5% → 0) | nie | opcjonalna łata przed retreningiem |
| dwell binarnych (grzałka, nawilżacz, …) | częściowo | rozszerzyć o nowe aktuary |

### Co do ML, co poza ML

| Warstwa | Przykłady |
|---------|-----------|
| **ML** | Sterowanie przy **sprzężeniach** T↔RH↔gleba (4 donice)→powietrze↔fan↔zewnątrz↔CO₂ — który aktuator, kiedy i ile; uczenie na symulatorze z tą fizyką |
| **Symulator (trening)** | Dynamika growboxa — **możliwie blisko** realnej termodynamiki komory (patrz sekcja poniżej); źródło trajektorii dla ML i teacher |
| **Safety** | Alarmy, pełna gleba, niedostępny czujnik, wymuszenie 0 na `available=false` |
| **Harmonogram / Nodeflow** | Światło dzień/noc, tryby użytkownika |
| **Mostek sprzętowy** | 1× `fan` → kilka fizycznych wentylatorów |

**Na płytce w runtime:** czujniki dają **stan** (nie ML); ML **proponuje** wyjścia 0–1; safety **tnie**; mostek wykonuje. ML nie liczy fizyki zamiast czujników — ale bez ML trudno sensownie koordynować wiele sprzężonych aktuatorów (np. pompa vs nawilżacz vs fan przy tym samym celu RH).

### Symulator — termodynamika growboxa (trening)

Growbox to **jedna komora** z **wieloma sprzężonymi** procesami: temperatura i wilgotność powietrza wpływają na siebie nawzajem; podlewanie donic zmienia glebę **i** RH w całym boxie; suchość i ciepło przyspieszają parowanie z substratu **nieliniowo**; fan wymienia powietrze z zewnątrz; grzałka, osuszacz, chłodzenie i CO₂ dokładają kolejne pętle. Sterowanie tym regułami if/else jest kruche — dlatego ML uczy się na trajektoriach z symulatora.

**Cel symulatora:** możliwie **blisko** odwzorować realne zachowanie termodynamiczne growboxa — wystarczająco dobrze, żeby teacher i sieć uczyły się **właściwych** zależności przyczynowych (np. pompa vs nawilżacz przy tym samym celu RH). To **nie** CFD ani cyfrowy twin laboratoryjny: model **zgrupowany** (objętość komory, 4 donice, składowe co krok Δt), kalibrowany parametrami scenariusza i iteracyjnie porównywany z żywym boxem.

| Gdzie piszemy co | Zakres |
|------------------|--------|
| **Kontrakt / [IO_MAP.md](IO_MAP.md)** | sloty I/O, mix & match — **bez** równań fizycznych |
| **`tools/ml/simulator.py`** (+ docelowo ten sam model w `DummyEnvironmentSimulator`) | **cała dynamika** — jedyne źródło prawdy sprzężeń |
| **Teacher** | koszt / heurystyki celów na trajektoriach z symulatora |
| **Safety** | twarde granice niezależne od modelu |
| **Runtime na płytce** | **czujniki** = stan; symulator **nie** działa w produkcji |

**Sprzężenia do odwzorowania w v2** (wzory w kodzie, nie lista reguł w dokumentacji):

1. **Donica → powietrze** — **suma po aktywnych strefach** (0–4, nie zawsze cztery): parowanie / transpiracja do wspólnego `air_humidity_pct`; per slot wilgotność gleby, temp. gleby (gdy valid), RH i T powietrza; wyłączona strefa = brak składnika (jak `validity: false` / `zone.available: false`).
2. **T ↔ RH komory** — wymiana z `outside_*` (fan, przecieki), nawilżacz / osuszacz / chłodzenie, **ciepło utajone** parowania (RH ↑ może iść w parze z krótkim T ↓).
3. **Podlewanie** — dyskretny impuls per strefa → gleba N + natychmiastowy i utajony składnik evap.
4. **CO₂** — `co2_doser`, wymiana przez fan w stronę `outside_co2_ppm`, uproszczony metabolizm.
5. **Lampa (`lights_active`)** — gdy true: stałe lub konfigurowalne `lights_max_heat_w` w bilansie T (jak grzałka); wyłączenie lampy przy przekroczeniu progu T → **safety**, nie wyjście ML.
6. **Fan vs `outside_temperature_c`** — wymiana ciepła już w modelu wymiany powietrza; teacher/safety: przy grzaniu i `outside_T` ≪ `inside_T` — nie wietrzyć na max (uchronić ciepło).

v1 (`simulator.py`) ma już nieliniowe prototypy (`vapor_deficit`, `temperature_factor`). **Faza 2** rozszerza o 4 donice, temp. gleby, evap po podlewaniu, **ciepło lampy** i politykę fan/zewnątrz w teacher; **Faza 4** trening na tym symulatorze. Jakość ML = jakość symulatora × teacher.

**Światło — nie tylko symulator:** twarde „za gorąco → lampa OFF” musi być w **SafetySupervisor + mostek** (ochrona roślin). „Za zimno → lampa ON jako dogrzewanie” to **harmonogram / Nodeflow** (opcjonalny tryb), opisane w [IO_MAP.md](IO_MAP.md). Symulator sam nie zastąpi safety — modeluje **skutki**, safety pilnuje **limitów**.

**Brak grzałki / słaba grzałka / lampa / fan vs zewnątrz** — przykłady sprzężeń termicznych; pełna lista = kod symulatora, nie dokumentacja.

**Walidacja:** testy kierunku (sucho+ciepło > wilgotno+zimno), potem replay na prawdziwym sprzęcie i korekta parametrów — bez wypisywania każdej pary zależności w osobnych dokumentach.

---

## Roadmap produktu — świadomie poza v2

Skrót „mentalnego obrazu”: co **jest** w v2, a czego **świadomie nie ma** w kolejnych wersjach (nie przypadkowe luki). Szczegóły slotów: [IO_MAP.md](IO_MAP.md).

### Linia czasu

```text
v2 (teraz)          substrat, 4 strefy, klimat, CO₂ butla, safety per strefa
v2.1                hydro (EC/pH), zalanie, PPFD, opcj. VPD w ML
v2.2+               liść IR, wylot wentylacji, outdoor / premium
poza kontraktem     harmonogram, Nodeflow, interlocki, support, LiteGraph
```

### v2 — zakres zamknięty

| Obszar | W v2 | Poza v2 (świadomie) |
|--------|------|---------------------|
| Czujniki wewnątrz | temp., RH; CO₂ opcj.; opcj. temp. zbiornika; gleba ×4 | PPFD, liść, EC/pH |
| Czujniki zewnątrz | temp., RH; CO₂ opcj. przy wlocie | wylot, stacja pogodowa |
| Aktuary | 6 globalnych + 4 pompy + `co2_doser` | dimmer LED, fan×2 w ML, mata/donica |
| Światło | harmonogram → `lights_active` | wyjście ML, czujnik nasłonecznienia |
| ML | propozycja klimatu + podlewania | VPD jako cecha, retrening v1 |
| Safety | alarmy, pełna gleba, ΔT nawóz, fan↔CO₂ | zalanie (v2.1), dym (hardware) |

### Dlaczego taka kolejność

1. **v2** musi być kompletny SKU „growbox w ziemi” — przewidywalny bez drogich czujników.
2. **v2.1** rozszerza segment (hydro) i safety (zalanie), nie psuje kontraktu substratu.
3. **v2.2+** to upsell diagnostyczny — klient już ma działający rdzeń, dokłada czujniki.
4. **Harmonogram / UI / mostek** nigdy nie wchodzą do wektorów ML — stabilny podział warstw.

### Otwarte na roadmapie (nie blokują v2)

| Temat | Stan | Domyślna decyzja |
|-------|------|------------------|
| Dwa wentylatory fizyczne | pytanie otwarte | 1× `fan` ML + mapowanie w mostku |
| Klimatyzator vs osuszacz | do potwierdzenia | dwa osobne wyjścia (plan v2) |
| ML jako tier Pro | biznes | safety + reguły = zawsze; ML opcjonalnie |

---

## Kolejność prac

### Faza 0 — zamrożenie v1 (teraz)

- [x] Zrozumieć objawy na panelu (bias modelu, nie UI)
- [x] Usunąć linię `impuls X s` z karty pompy (duplikat ustawień)
- [ ] **Nie** inwestować w dopieszczanie modelu v1 (`train-full` na starym kontrakcie)

### Faza 1 — spec v2 (krótka)

- [x] **Sensing v2** — zamknięte ([IO_MAP.md](IO_MAP.md) → *Sensing v2*)
- [x] **Wyjścia ML v2** — zamknięte (10 slotów)
- [ ] Potwierdzić pytania otwarte (poniżej) — tylko cele / wentylatory, nie czujniki
- [ ] Wypełnić [IO_MAP.md](IO_MAP.md) — kolumna „Twój sprzęt” (instalacja użytkownika)
- [ ] Dopisać w `environment-controller-v2.json`: `lights_active`, targets, actuators w `features` (Faza 2)

### Faza 2 — kontrakt v2 w kodzie (jeden duży PR)

Kolejność wewnątrz fazy:

1. `schemas/environment-controller-v2.json` + generator → `EnvironmentSchema.h`
2. `EnvironmentTypes.h`, `FeatureEncoder`, `SafetySupervisor`
3. Symulator Python (`tools/ml/simulator.py`) — **termodynamika v2**; **do 4 slotów** donic (mix & match: `zones[N].available`, `validity`, `irrigation.available` — scenariusze losują 0–4 aktywne); teacher na tych trajektoriach
4. `DummyEnvironmentSimulator.cpp` — **ta sama fizyka** co Python; wire codec + panel (`form_schema.py`)
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

1. ~~**Światło**~~ — **zamknięte:** harmonogram + `lights_active` / readback przekaźnika; **bez** czujnika nasłonecznienia na v2.
2. ~~**Klimatyzator vs osuszacz**~~ — **zamknięte:** `cooler` + `dehumidifier`, dwa osobne wyjścia.
3. **Dwa wentylatory** — domyślnie 1× `fan` ML + mapowanie w mostku (bez drugiego slotu ML).
4. **Cel wilgotności gleby** — jeden wspólny czy osobny per strefa? (plan: per strefa w `zones[i]`)

## Zamknięte decyzje

- Max **4 strefy** podlewania; strefa = czujnik gleby + pompa.
- **Sensing v2 zamknięte:** 15 slotów pomiarowych + `lights_active` — mix & match; lista w [IO_MAP.md](IO_MAP.md) → *Sensing v2*.
- **Wewnątrz boxa (globalnie):** `air_temperature_c`, `air_humidity_pct`, `co2_ppm` — każdy ☑/☐; bez dodatkowych czujników na v2.
- **Temp. gleby opcjonalna** per strefa (`validity` osobno); wilgotność gleby wymagana do logiki podlewania.
- **Temp. roztworu nawozowego** (`nutrient_solution_temperature_c`) — osobne od temp. gleby; DS18B20 w zbiorniku; safety przed „zimnym nawozem na ciepłą ziemię”.
- **CO₂:** czujnik `co2_ppm` **opcjonalny** (`validity: false` bez hardware); aktuator `co2_doser` (`available: false` bez butli); dozowanie zablokowane przy braku valid czujnika, przy wencie fanu lub CO₂ ≥ cel.
- **Światło:** bez PPFD; `lights_active` = wejście ML + termika w symulatorze; sterowanie przekaźnikiem **poza ML** (harmonogram, opcj. dogrzewanie, **safety OFF** przy upale).
- **Zewnątrz boxa:** 3 sloty przy wlocie — każdy ☑/☐ — zestaw zamknięty na v2.
- **Profil prosty:** 2× BLE TP357 (wewn. + zewn.) → 4 pomiary temp./RH, oba CO₂ `validity: false` — [IO_MAP.md](IO_MAP.md).
- **Wejścia czujnikowe v2:** **domknięte** — nie wracamy do listy slotów przed v2.1; roadmap → [IO_MAP.md](IO_MAP.md).
- **Świadomie poza v2:** PPFD, EC/pH, liść IR, zalanie, wylot wentylacji, światło w ML — roadmap v2.1 / v2.2+, nie scope Fazy 2.
- **I/O v2 definitywne (2026-07):** checklista 26 slotów w [IO_MAP.md](IO_MAP.md) → *Mix & match*; bez nowych czujników/wyjść ML w tej wersji.
- **Mix & match:** 26 slotów + opcj. `zones[N].available` — każdy osobno (`validity` / `available`); brak pakietów wymaganych.
- Dokładanie sprzętu = włączenie kolejnego indeksu strefy, bez nowego kontraktu.

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
