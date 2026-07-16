# CONFIG MATRIX — zamknięta lista testów mix & match
**Źródło prawdy dyskretnej.** Agent NIE wybiera podzbioru. Każdy wiersz = 1 konfiguracja sprzętowa.
**Liczba profili w tej matrycy: 59**
Plik maszynowy: `CONFIG_MATRIX.csv` (ten sam katalog).

## Dlaczego nie „każda możliwa” liczba rzeczywista
- Cechy ciągłe (W, m³/h, ml/s, cele, previous…) mają **nieskończenie** wiele wartości → testujemy **siatkę** (min/def/max), nie continuum.
- Pełny iloczyn samych masek: 7 validity × 7 aktuatorów × ~37⁴ stanów donic ≈ **10¹⁰** — nierealne ręcznie/agentem.
- Ta matryca = **zamknięty, skończony** zestaw: SKU produktowe + single-fault + kratka donicy 1 + typy sterowania + pot index.

## Slot checklist (dyskretne) — 43 flagi
### Validity czujników (7)
- [ ] `validity.air_temperature_c` true|false
- [ ] `validity.air_humidity_pct` true|false
- [ ] `validity.co2_ppm` true|false
- [ ] `validity.nutrient_solution_temperature_c` true|false
- [ ] `validity.outside_temperature_c` true|false
- [ ] `validity.outside_humidity_pct` true|false
- [ ] `validity.outside_co2_ppm` true|false

### Aktuatory globalne available (7)
- [ ] `actuators.heater.available` true|false
- [ ] `actuators.fan.available` true|false
- [ ] `actuators.humidifier.available` true|false
- [ ] `actuators.dehumidifier.available` true|false
- [ ] `actuators.cooler.available` true|false
- [ ] `actuators.co2_doser.available` true|false
- [ ] `actuators.nutrient_heater.available` true|false

### Per donica N=1..4 (×4)
- [ ] `pots[N-1].available`
- [ ] `pots[N-1].validity.soil_moisture_pct`
- [ ] `pots[N-1].validity.soil_temperature_c`
- [ ] `pots[N-1].irrigation.available`
- [ ] `pots[N-1].irrigation.control_type` binary|pwm
- [ ] `pots[N-1].heat_mat.available`
- [ ] `pots[N-1].heat_mat.control_type` binary|pwm

### Pseudo
- [ ] `lights_active` true|false (stan runtime scenariusza)

## Wyjścia ML (zawsze 15 slotów; zerowane przez available/safety)
1. `heater`
2. `fan`
3. `humidifier`
4. `dehumidifier`
5. `cooler`
6. `co2_doser`
7. `irrigation_pot_1`
8. `irrigation_pot_2`
9. `irrigation_pot_3`
10. `irrigation_pot_4`
11. `nutrient_heater`
12. `heat_mat_pot_1`
13. `heat_mat_pot_2`
14. `heat_mat_pot_3`
15. `heat_mat_pot_4`

## Ciągłe — reguła testu (NIE pełny produkt kartezjański)
Dla **każdego** aktywnego aktuatora/czujnika w profilu: ustaw parametry na **{min, default, max}** z kontraktu (3 punkty).
Dla previous_*: `{0, 0.5, 1}`.
Dla targets: nominal + skraj (za zimno / za wilgotno / niski CO2).

## Warstwa 2 — ciągłe sweepy (host) + behawior ML (płytka)

CONFIG_MATRIX (59 wierszy) pokrywa **dyskretną konfigurację I/O** (availability, validity, donice, typy sterowania). To **Warstwa 1**.

| Warstwa | Narzędzie | Gdzie | Co testuje |
|---------|-----------|-------|------------|
| **1 — I/O mix & match** | `python -m tools.ml.run_config_matrix` | Host | Encoder 128, safety (Python mirror), krótki sim 5 kroków, sweep min/def/max per profil |
| **2a — wartości ciągłe** | ten sam harness (`check_continuous_sweeps`) | Host | T/RH/CO2/capabilities w siatce 3-punktowej dla każdego aktywnego pola |
| **2b — ML raw/safe + polityka** | `python -m tools.ml.panel_endpoint_audit` | Płytka (po `make flash`) | Sweepy T/RH/CO₂/gleby, heurystyki zimno→heat, overtemperature, `extreme_multi_need` |
| **2c — CONFIG_MATRIX na ESP** | `python -m tools.ml.board_engine_audit --matrix-only` | Płytka | Te same 59 profili: `load_scenario` → `step` → `expected_safe_zero_outputs` + reguły safety |
| **2d — pełna macierz validity** | `python -m tools.ml.validity_matrix_audit` | Płytka | **32 768** masek (2¹⁵): tylko checkboxy validity; stałe odczyty off-target + wszystkie aktuary ON |

**CO₂ w Warstwie 1:** gdy `avail_co2_doser` i `valid_co2_ppm` są true, harness ustawia `sensors.co2_ppm = 500` (poniżej celu 850), żeby testować **dostępność** dosera, a nie regułę „target reached” przy nominalnym 920 ppm.

### Komendy

```bash
# Warstwa 1 (host, bez płytki)
python -m tools.ml.run_config_matrix
# domyślnie: docs/CONFIG_MATRIX.csv → build/audit/CONFIG_MATRIX_RESULTS.csv

# Skrypty serial per profil (do ręcznego replay / audytu)
python -m tools.ml.config_matrix --write-scripts build/matrix-replay

# Warstwa 2c — 59 profili na płytce (wymaga flash + port)
GROWBOX_BOARD_PORT=/dev/cu.usbmodem1101 \
  python -m tools.ml.board_engine_audit --matrix-only \
  --report build/audit/board_config_matrix.json

# Warstwa 2b — sweepy behawioralne (szersza macierz, ~57 case)
python -m tools.panel &   # :8765
python -m tools.ml.panel_endpoint_audit --port /dev/cu.usbmodem1101

# Warstwa 2d — wszystkie kombinacje validity (32 768; checkpoint, wznowienie)
make test-board-validity-matrix
# lub: python -m tools.ml.validity_matrix_audit --port /dev/cu.usbmodem1101
# raport: build/audit/validity_matrix_audit.json
# checkpoint: build/audit/validity_matrix_checkpoint.jsonl
```

### Warstwa 2d — jak czytać wynik validity (32 768)

- **ERRORS** (gate): inference OK, wyjścia w [0,1], safety przy invalid sensor (heater=0 bez T, doser=0 bez CO₂, …), wzajemne wykluczenia.
- **WARNS** (ML policy): tylko gdy czujnik **valid** — przy stałych odczytach zimno/sucho/niski CO₂/sucha gleba model powinien włączyć odpowiedni aktuator (`cold_no_heat`, `dry_no_humidify`, `dry_soil_no_irrigation`).
- **PASS audytu** = `error_count == 0` w raporcie JSON. Warns = lista masek do ręcznej inspekcji / retreningu, nie blokują flashu.
- **Wznowienie**: ponowne uruchomienie pomija maski ze statusem `ok`/`fail` w checkpoint.
- **Smoke na płytce**: `--max-cases 50` (debug); pełny przebieg ~3–5 h @0,35 s/krok.

Stress cases (`board_engine_audit` bez `--matrix-only`) i `panel_endpoint_audit` pozostają **osobną** macierzą behawioralną — uzupełniają CONFIG_MATRIX, nie zastępują.

## Wymagane asercje na profil (agent musi zalogować PASS/FAIL per id)
1. Encoder produkuje wektor 128 finite w [0,1] po normalizacji.
2. ModelRuntime nie crashuje (schema hash OK).
3. Safety: każdy output z `expected_safe_zero_outputs` ma **safe == 0**.
4. Available=false ⇒ safe output 0 (niezależnie od raw ML).
5. Validity=false ⇒ feature mask=0 i wartość = default kontraktu (po clamp).
6. Pot available=false ⇒ irrigation_pot_N i heat_mat_pot_N safe=0.
7. Sim `step` bez NaN; T/RH/CO2/soil w zakresach kontraktu.

## Lista profili (id → name)
| id | name | n_pots | sensors_on | actuators_on |
|----|------|-------:|------------|-------------|
| `P01` | minimal_temp_rh_fan_heater | 1 | air_temperature_c,air_humidity_pct | heater,fan |
| `P02` | hobby_1pot_soil_pump | 1 | air_temperature_c,air_humidity_pct,outside_temperature_c,outside_humidity_pct | heater,fan,humidifier |
| `P03` | hobby_1pot_soil_temp_heatmat | 1 | air_temperature_c,air_humidity_pct,outside_temperature_c,outside_humidity_pct | heater,fan,humidifier |
| `P04` | 2pot_mixed_validity | 2 | air_temperature_c,air_humidity_pct,co2_ppm | heater,fan,humidifier,co2_doser |
| `P05` | 4pot_full_climate_no_cool | 4 | air_temperature_c,air_humidity_pct,co2_ppm,nutrient_solution_temperature_c,outside_temperature_c,outside_humidity_pct,outside_co2_ppm | heater,fan,humidifier,dehumidifier,co2_doser,nutrient_heater |
| `P06` | 4pot_full_sku | 4 | air_temperature_c,air_humidity_pct,co2_ppm,nutrient_solution_temperature_c,outside_temperature_c,outside_humidity_pct,outside_co2_ppm | heater,fan,humidifier,dehumidifier,cooler,co2_doser,nutrient_heater |
| `P07` | climate_only_no_pots | 0 | air_temperature_c,air_humidity_pct,co2_ppm,outside_temperature_c,outside_humidity_pct,outside_co2_ppm | heater,fan,humidifier,dehumidifier,cooler,co2_doser |
| `P08` | irrigation_only_no_climate_actuators | 2 | air_temperature_c,air_humidity_pct | ∅ |
| `P09` | co2_without_sensor_blocked | 0 | air_temperature_c,air_humidity_pct | fan,co2_doser |
| `P10` | pump_without_moisture_blocked | 1 | air_temperature_c | fan |
| `P11` | nutrient_heater_without_tank_sensor | 1 | air_temperature_c,air_humidity_pct | nutrient_heater,heater |
| `P12` | all_sensors_invalid | 1 | ∅ | heater,fan |
| `P13` | all_actuators_unavailable | 1 | air_temperature_c,air_humidity_pct,co2_ppm,nutrient_solution_temperature_c,outside_temperature_c,outside_humidity_pct,outside_co2_ppm | ∅ |
| `P14` | pot_count_1 | 1 | air_temperature_c,air_humidity_pct | heater,fan |
| `P15` | pot_count_2 | 2 | air_temperature_c,air_humidity_pct | heater,fan |
| `P16` | pot_count_3 | 3 | air_temperature_c,air_humidity_pct | heater,fan |
| `P17` | pot_count_4 | 4 | air_temperature_c,air_humidity_pct | heater,fan |
| `P18` | binary_vs_pwm_irrigation | 2 | air_temperature_c | fan |
| `P19` | heat_mat_only_no_irrigation | 1 | air_temperature_c | heater |
| `P20` | outside_only_no_inside_temp | 0 | outside_temperature_c,outside_humidity_pct | fan,heater |
| `S_OFF_air_temperature_c` | single_sensor_invalid__air_temperature_c | 1 | air_humidity_pct,co2_ppm,nutrient_solution_temperature_c,outside_temperature_c,outside_humidity_pct,outside_co2_ppm | heater,fan,humidifier |
| `S_OFF_air_humidity_pct` | single_sensor_invalid__air_humidity_pct | 1 | air_temperature_c,co2_ppm,nutrient_solution_temperature_c,outside_temperature_c,outside_humidity_pct,outside_co2_ppm | heater,fan,humidifier |
| `S_OFF_co2_ppm` | single_sensor_invalid__co2_ppm | 1 | air_temperature_c,air_humidity_pct,nutrient_solution_temperature_c,outside_temperature_c,outside_humidity_pct,outside_co2_ppm | heater,fan,humidifier |
| `S_OFF_nutrient_solution_temperature_c` | single_sensor_invalid__nutrient_solution_temperature_c | 1 | air_temperature_c,air_humidity_pct,co2_ppm,outside_temperature_c,outside_humidity_pct,outside_co2_ppm | heater,fan,humidifier |
| `S_OFF_outside_temperature_c` | single_sensor_invalid__outside_temperature_c | 1 | air_temperature_c,air_humidity_pct,co2_ppm,nutrient_solution_temperature_c,outside_humidity_pct,outside_co2_ppm | heater,fan,humidifier |
| `S_OFF_outside_humidity_pct` | single_sensor_invalid__outside_humidity_pct | 1 | air_temperature_c,air_humidity_pct,co2_ppm,nutrient_solution_temperature_c,outside_temperature_c,outside_co2_ppm | heater,fan,humidifier |
| `S_OFF_outside_co2_ppm` | single_sensor_invalid__outside_co2_ppm | 1 | air_temperature_c,air_humidity_pct,co2_ppm,nutrient_solution_temperature_c,outside_temperature_c,outside_humidity_pct | heater,fan,humidifier |
| `A_OFF_heater` | single_actuator_unavailable__heater | 4 | air_temperature_c,air_humidity_pct,co2_ppm,nutrient_solution_temperature_c,outside_temperature_c,outside_humidity_pct,outside_co2_ppm | fan,humidifier,dehumidifier,cooler,co2_doser,nutrient_heater |
| `A_OFF_fan` | single_actuator_unavailable__fan | 4 | air_temperature_c,air_humidity_pct,co2_ppm,nutrient_solution_temperature_c,outside_temperature_c,outside_humidity_pct,outside_co2_ppm | heater,humidifier,dehumidifier,cooler,co2_doser,nutrient_heater |
| `A_OFF_humidifier` | single_actuator_unavailable__humidifier | 4 | air_temperature_c,air_humidity_pct,co2_ppm,nutrient_solution_temperature_c,outside_temperature_c,outside_humidity_pct,outside_co2_ppm | heater,fan,dehumidifier,cooler,co2_doser,nutrient_heater |
| `A_OFF_dehumidifier` | single_actuator_unavailable__dehumidifier | 4 | air_temperature_c,air_humidity_pct,co2_ppm,nutrient_solution_temperature_c,outside_temperature_c,outside_humidity_pct,outside_co2_ppm | heater,fan,humidifier,cooler,co2_doser,nutrient_heater |
| `A_OFF_cooler` | single_actuator_unavailable__cooler | 4 | air_temperature_c,air_humidity_pct,co2_ppm,nutrient_solution_temperature_c,outside_temperature_c,outside_humidity_pct,outside_co2_ppm | heater,fan,humidifier,dehumidifier,co2_doser,nutrient_heater |
| `A_OFF_co2_doser` | single_actuator_unavailable__co2_doser | 4 | air_temperature_c,air_humidity_pct,co2_ppm,nutrient_solution_temperature_c,outside_temperature_c,outside_humidity_pct,outside_co2_ppm | heater,fan,humidifier,dehumidifier,cooler,nutrient_heater |
| `A_OFF_nutrient_heater` | single_actuator_unavailable__nutrient_heater | 4 | air_temperature_c,air_humidity_pct,co2_ppm,nutrient_solution_temperature_c,outside_temperature_c,outside_humidity_pct,outside_co2_ppm | heater,fan,humidifier,dehumidifier,cooler,co2_doser |
| `POT1_0001` | pot1_combo_m0_t0_i0_h1 | 1 | air_temperature_c,air_humidity_pct | heater,fan |
| `POT1_0010` | pot1_combo_m0_t0_i1_h0 | 1 | air_temperature_c,air_humidity_pct | heater,fan,nutrient_heater |
| `POT1_0011` | pot1_combo_m0_t0_i1_h1 | 1 | air_temperature_c,air_humidity_pct | heater,fan,nutrient_heater |
| `POT1_0100` | pot1_combo_m0_t1_i0_h0 | 1 | air_temperature_c,air_humidity_pct | heater,fan |
| `POT1_0101` | pot1_combo_m0_t1_i0_h1 | 1 | air_temperature_c,air_humidity_pct | heater,fan |
| `POT1_0110` | pot1_combo_m0_t1_i1_h0 | 1 | air_temperature_c,air_humidity_pct | heater,fan,nutrient_heater |
| `POT1_0111` | pot1_combo_m0_t1_i1_h1 | 1 | air_temperature_c,air_humidity_pct | heater,fan,nutrient_heater |
| `POT1_1000` | pot1_combo_m1_t0_i0_h0 | 1 | air_temperature_c,air_humidity_pct | heater,fan |
| `POT1_1001` | pot1_combo_m1_t0_i0_h1 | 1 | air_temperature_c,air_humidity_pct | heater,fan |
| `POT1_1010` | pot1_combo_m1_t0_i1_h0 | 1 | air_temperature_c,air_humidity_pct | heater,fan,nutrient_heater |
| `POT1_1011` | pot1_combo_m1_t0_i1_h1 | 1 | air_temperature_c,air_humidity_pct | heater,fan,nutrient_heater |
| `POT1_1100` | pot1_combo_m1_t1_i0_h0 | 1 | air_temperature_c,air_humidity_pct | heater,fan |
| `POT1_1101` | pot1_combo_m1_t1_i0_h1 | 1 | air_temperature_c,air_humidity_pct | heater,fan |
| `POT1_1110` | pot1_combo_m1_t1_i1_h0 | 1 | air_temperature_c,air_humidity_pct | heater,fan,nutrient_heater |
| `POT1_1111` | pot1_combo_m1_t1_i1_h1 | 1 | air_temperature_c,air_humidity_pct | heater,fan,nutrient_heater |
| `CTRL_binary_binary` | pot1_control_types_irr_binary_heat_binary | 1 | air_temperature_c | fan |
| `CTRL_binary_pwm` | pot1_control_types_irr_binary_heat_pwm | 1 | air_temperature_c | fan |
| `CTRL_pwm_binary` | pot1_control_types_irr_pwm_heat_binary | 1 | air_temperature_c | fan |
| `CTRL_pwm_pwm` | pot1_control_types_irr_pwm_heat_pwm | 1 | air_temperature_c | fan |
| `ONLY_POT_1` | only_pot_1_active | 1 | air_temperature_c,air_humidity_pct | heater,fan |
| `ONLY_POT_2` | only_pot_2_active | 1 | air_temperature_c,air_humidity_pct | heater,fan |
| `ONLY_POT_3` | only_pot_3_active | 1 | air_temperature_c,air_humidity_pct | heater,fan |
| `ONLY_POT_4` | only_pot_4_active | 1 | air_temperature_c,air_humidity_pct | heater,fan |
| `L0` | lights_off_runtime | 1 | air_temperature_c,air_humidity_pct | heater,fan |
| `L1` | lights_on_runtime | 1 | air_temperature_c,air_humidity_pct | heater,fan |

## Prompt dla agenta (wklej 1:1)
```
Przetestuj WSZYSTKIE wiersze z CONFIG_MATRIX.csv (kolumna id).
Zakaz: wybierania podzbioru, pomijania, 'reprezentatywnej próbki'.
Dla każdego id: uruchom encoder+safety(+opcjonalnie sim 5 kroków).
Wynik: plik RESULTS.csv z kolumnami id,pass,fail_reason (fail_reason puste gdy pass).
Koniec pracy = len(RESULTS)==len(CONFIG_MATRIX) oraz wszystkie pass=true
ALBO lista failed id. Nie pisz 'zrobione' bez RESULTS.csv.
```

<!-- generated profiles: 59 -->
