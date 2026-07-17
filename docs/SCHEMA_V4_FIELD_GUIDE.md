# Schema v4 — przewodnik pól (konfigurator)

**Kontrakt:** [`schemas/environment-controller.json`](../schemas/environment-controller.json) (`schema_version` **4**)
**Cel tego pliku:** krótkie znaczenie każdego **logicznego** slotu pod UI edytora hardware / scenariusz.
**Nie zastępuje** schema — zakresy `min`/`max`/`default` i kolejność cech ML są tylko w JSON.

> Opisy po polsku dla UI. Identyfikatory i ścieżki JSON — **po angielsku**, jak w kontrakcie.

## Zasady mix & match (v4)

| Typ | Włączone | Wyłączone |
|-----|----------|-----------|
| Czujnik | `validity.* = true` + realny odczyt | `validity.* = false` — encoder: default + maska (slot **zostaje**) |
| Aktuator | `actuators.*.available = true` | `available = false` — safety wymusza wyjście 0; limity max → 0 |
| Donica | `pots[N].available = true` | `false` — slot donicy zostaje; gleba/pompa/mata nieaktywne w praktyce |
| Pseudo | np. harmonogram lamp | brak integracji → `pseudo.lights_active = false` |

**Nie usuwamy slotów z kontraktu** — tylko flagi. Nowe pomiary/wyjścia ML = nowa wersja schema (breaking).

## Mapa UI → JSON (grupy konfiguratora)

Proponowany układ ekranów (ewoluuje z edytorem):

1. **Komora** — `environment.*`
2. **Klimat wewnątrz / na zewnątrz / zbiornik** — sensory + validity
3. **Donice 1–4** — available, gleba, irygacja, mata, cele gleby
4. **Wyjścia globalne** — heater, fan, humid, dehum, cooler, CO₂, nutrient heater
5. **Światło (pseudo)** — `pseudo.lights_active`
6. **Cele klimatu** — `targets.*` (setpointy, nie pomiary)
7. **Previous** — ostatnie komendy 0–1 (stan startowy / board), nie „czy mam sprzęt”

---

## 1. Environment (parametry komory)

Używane głównie w **symulacji / kalibracji**, nie jako feature ML 1:1 w wektorze w ten sam sposób co sensory — ale są w modelu feature list jako skalary środowiska.

| Path | Znaczenie |
|------|-----------|
| `environment.growbox_volume_m3` | Objętość powietrza komory [m³]. Większa = wolniejsza zmiana klimatu przy tej samej mocy. |
| `environment.thermal_mass_j_per_k` | Bezwładność cieplna [J/K]. Większa = wolniej grzeje/stygnie. |
| `environment.heat_loss_w_per_k` | Straty przez ściany [W/K] do otoczenia. |
| `environment.air_leak_rate_ach` | Nieszczelność [1/h] — naturalna wymiana bez fana. |

---

## 2. Sensory powietrza i validity

### Wewnątrz komory

| Path | Znaczenie |
|------|-----------|
| `sensors.air_temperature_c` | Temperatura powietrza w boxie [°C]. |
| `sensors.air_humidity_pct` | Wilgotność względna w boxie [%]. |
| `sensors.co2_ppm` | CO₂ w boxie [ppm]. |
| `validity.air_temperature_c` | Czy czujnik T powietrza jest zainstalowany / wiarygodny. |
| `validity.air_humidity_pct` | Czy czujnik RH jest zainstalowany. |
| `validity.co2_ppm` | Czy czujnik CO₂ jest zainstalowany. |

### Zbiornik nawozu

| Path | Znaczenie |
|------|-----------|
| `sensors.nutrient_solution_temperature_c` | Temp. roztworu w zbiorniku [°C]. |
| `validity.nutrient_solution_temperature_c` | Czy czujnik zbiornika jest. |

### Na zewnątrz / wlot (boundary)

| Path | Znaczenie |
|------|-----------|
| `sensors.outside_temperature_c` | Temp. powietrza na wlocie / na zewnątrz [°C]. |
| `sensors.outside_humidity_pct` | RH na wlocie / na zewnątrz [%]. |
| `sensors.outside_co2_ppm` | CO₂ na wlocie / na zewnątrz [ppm]. |
| `validity.outside_*` | Czy dany czujnik zewnętrzny jest. |

---

## 3. Pseudo

| Path | Znaczenie |
|------|-----------|
| `pseudo.lights_active` | Czy lampy są włączone wg harmonogramu / readback (nie pomiar PPFD). Wejście ML, nie aktuator 0–1 w wektorze wyjść. |

---

## 4. Donice `pots[0..3]` (UI: Donica 1–4)

Indeks tablicy **0-based**; etykiety UI i feature names często **1-based** (`pot_1_*`).

| Path | Znaczenie |
|------|-----------|
| `pots[N].available` | Czy donica N jest w użyciu (roślina / strefa aktywna). |
| `pots[N].sensors.soil_moisture_pct` | Wilgotność podłoża [%] (wartość procesu). |
| `pots[N].sensors.soil_temperature_c` | Temp. podłoża [°C]. |
| `pots[N].validity.soil_moisture_pct` | Czy czujnik wilgotności gleby jest na tej donicy. |
| `pots[N].validity.soil_temperature_c` | Czy czujnik temp. gleby jest. |
| `pots[N].cultivation.pot_volume_l` | Objętość donicy [L] — parametr uprawy / sim. |
| `pots[N].cultivation.substrate_water_capacity_ml` | Pojemność wodna podłoża [ml]. |
| `pots[N].cultivation.transpiration_factor` | Skala parowania/transpiracji (1 = nominal). |
| `pots[N].targets.soil_moisture_pct` | Cel wilgotności gleby [%] (setpoint). |
| `pots[N].targets.soil_temperature_c` | Cel temp. gleby [°C]. |
| `pots[N].irrigation.available` | Czy pompa irygacji na tej donicy jest. |
| `pots[N].irrigation.flow_ml_s` | Przepływ pompy [ml/s]. |
| `pots[N].irrigation.maximum_pulse_s` | Max czas impulsu [s]. |
| `pots[N].irrigation.minimum_interval_s` | Min. odstęp między impulsami [s]. |
| `pots[N].irrigation.control_type` | Sposób sterowania (np. `binary` / PWM) — meta dla board/UI. |
| `pots[N].heat_mat.available` | Czy mata grzewcza pod donicą jest. |
| `pots[N].heat_mat.max_power_w` | Max moc maty [W]. |
| `pots[N].heat_mat.control_type` | Typ sterowania matą. |
| `pots[N].previous.irrigation` | Ostatnia komenda irygacji 0–1 (stan startowy). |
| `pots[N].previous.heat_mat` | Ostatnia komenda maty 0–1. |

Gdy `pots[N].available = false`: validity gleby i available pomp/mat w praktyce traktuj jako wyłączone; slot JSON zostaje.

---

## 5. Aktuatory globalne `actuators.*`

Wspólne: **`available`** = czy sprzęt jest w setupie.
Limity (`max_*`) = skalowanie komendy 0–1 na fizyczne jednostki (board + sim).

| Path | Znaczenie |
|------|-----------|
| `actuators.heater.available` | Grzałka powietrza. |
| `actuators.heater.max_power_w` | Max moc [W]. |
| `actuators.heater.efficiency` | Sprawność 0–1 (ciepło do powietrza). |
| `actuators.heater.control_type` | np. binary / pwm. |
| `actuators.fan.available` | Wentylator / wymiana. |
| `actuators.fan.max_airflow_m3_h` | Max przepływ [m³/h]. |
| `actuators.fan.minimum_command` | Martwa strefa 0–1 (poniżej = off). |
| `actuators.fan.control_type` | Zwykle pwm. |
| `actuators.humidifier.available` | Nawilżacz. |
| `actuators.humidifier.max_output_g_h` | Max para [g/h]. |
| `actuators.dehumidifier.available` | Osuszacz. |
| `actuators.dehumidifier.max_removal_g_h` | Max usuwanie wilgoci [g/h]. |
| `actuators.cooler.available` | Chłodzenie aktywne. |
| `actuators.cooler.max_cooling_w` | Max moc chłodzenia [W]. |
| `actuators.co2_doser.available` | Dozownik CO₂. |
| `actuators.co2_doser.dose_ppm_per_full_pulse` | Dawka [ppm] przy pełnym impulsie. |
| `actuators.co2_doser.maximum_pulse_s` | Max czas impulsu [s]. |
| `actuators.nutrient_heater.available` | Grzałka zbiornika. |
| `actuators.nutrient_heater.max_power_w` | Max moc [W]. |
| `actuators.nutrient_heater.efficiency` | Sprawność. |

**Lights:** w kontrakcie to **pseudo / non-ML actuator** (ciepło lamp w sim osobno) — nie dokładaj `actuators.lights` jako slotu ML bez zmiany schema.

---

## 6. Cele klimatu `targets.*`

Setpointy dla controllera / teachera — **nie** odczyty czujników.

| Path | Znaczenie |
|------|-----------|
| `targets.air_temperature_c` | Cel T powietrza. |
| `targets.air_humidity_pct` | Cel RH. |
| `targets.co2_ppm` | Cel CO₂. |
| `targets.nutrient_solution_temperature_c` | Cel temp. zbiornika. |

---

## 7. Previous (ostatnie komendy)

| Path | Znaczenie |
|------|-----------|
| `previous.heater` … `previous.nutrient_heater` | Ostatnia komenda 0–1 (kontynuacja stanu / cold start). |
| `pots[N].previous.*` | j.w. per donica. |

W konfiguratorze **sprzętu** często domyślnie 0; w scenariuszu treningowym / board — realny previous.

---

## 8. Wyjścia ML (15) — komendy 0–1

Model przewiduje / steruje (nazwy kontraktowe):

`heater`, `fan`, `humidifier`, `dehumidifier`, `cooler`, `co2_doser`,
`irrigation_pot_1`…`4`, `nutrient_heater`, `heat_mat_pot_1`…`4`.

Konfigurator **nie „usuwa”** wyjścia — ustawia `available` i limity. Safety na boardzie zeruje niedostępne.

---

## Poza v4 (nie dodawać w edytorze jako slot ML)

PPFD, temp. liścia, EC/pH, flood, osobne sensory wylotu, stacja pogodowa — roadmap, nie ta wersja kontraktu. Patrz `sensing_scope.explicitly_not_v2` w schema.

---

## Ewolucja pól

- Konfigurator **może ujawnić** braki (złe defaulty, brak etykiety, myląca nazwa).
- **Breaking** zmiana znaczenia path / nowy slot ML → nowa `schema_version` + regeneracja C++ + retrain.
- Niełamące: opisy w tym pliku, etykiety UI, grupowanie kart, domyślne wartości w szablonie JSON klienta.

## Powiązane

- [DATA_CONTRACT.md](DATA_CONTRACT.md)
- [IO_MAP.md](IO_MAP.md)
- [HARDWARE_CONFIGURATOR.md](HARDWARE_CONFIGURATOR.md) — założenia produktu edytora
