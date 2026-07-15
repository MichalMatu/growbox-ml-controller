# Mapa wejść i wyjść v1 (robocza)

Źródło prawdy: [`schemas/environment-controller-v1.json`](../schemas/environment-controller-v1.json)

Ten plik jest do **Twojej pracy** — uzupełniaj kolumnę „Twój sprzęt / źródło” i „Uwagi”.

---

## Przepływ w skrócie

```text
ControllerInput (C++ struct + JSON w demo)
        │
        ▼
FeatureEncoder  →  40 liczb znormalizowanych do [0, 1]
        │
        ▼
ModelRuntime    →  sieć MLP 40 → 32 → 32 → 4  (propozycja)
        │
        ▼
SafetySupervisor → 4 liczby bezpieczne + irrigation_pulse_s
        │
        ▼
ControllerOutput: raw_output + safe_output
```

Jeden punkt wejścia w kodzie: `EnvironmentController::process(ControllerInput, ControllerOutput)`.

Pliki:
- typy wejścia/wyjścia: `lib/environment_control/src/EnvironmentTypes.h`
- logika: `lib/environment_control/src/EnvironmentController.cpp`
- encoder: `lib/environment_control/src/FeatureEncoder.cpp`
- model: `lib/environment_control/src/ModelRuntime.cpp`
- safety: `lib/environment_control/src/SafetySupervisor.cpp`

---

## Wejście: `ControllerInput` (grupy)

| Grupa w C++ | Pola | Liczba pól | Trafia do modelu? |
|-------------|------|------------|-------------------|
| `SensorState sensors` | 6 pomiarów | 6 | tak (+ 6 masek validity) |
| `SensorValidity validity` | 6 masek OK/brak | 6 | tak |
| `EnvironmentConfig environment` | parametry skrzyni | 4 | tak |
| `CultivationConfig cultivation` | doniczka / substrat | 3 | tak |
| `ActuatorCapabilities actuators` | 4 urządzenia × możliwości | 13 | tak |
| `ControlTargets targets` | 4 cele | 4 | tak |
| `PreviousControlState previous` | 4 poprzednie stany | 4 | tak |
| `SafetyConfig safety` | limity temperatury, dwell | — | **nie** — tylko SafetySupervisor |
| `monotonic_time_ms` | czas kroku | — | **nie** do modelu — safety + dwell |

**Razem do sieci: 40 cech** (`kFeatureCount = 40`).

---

## Tabela 40 cech → mózg (kolejność stała)

Kolejność **nie wolno zmieniać** bez nowego kontraktu i retreningu.

| # | Nazwa cechy | Ścieżka JSON (demo) | Pole C++ (`ControllerInput`) | Jednostka | Min | Max | Domyślna | Twój sprzęt / źródło | Uwagi |
|---|-------------|---------------------|------------------------------|-----------|-----|-----|----------|----------------------|-------|
| 0 | air_temperature_c | sensors.air_temperature_c | sensors.air_temperature_c | °C | -20 | 60 | 24 | | |
| 1 | air_humidity_pct | sensors.air_humidity_pct | sensors.air_humidity_pct | % | 0 | 100 | 60 | | |
| 2 | co2_ppm | sensors.co2_ppm | sensors.co2_ppm | ppm | 0 | 5000 | 850 | | |
| 3 | soil_moisture_pct | sensors.soil_moisture_pct | sensors.soil_moisture_pct | % | 0 | 100 | 50 | | |
| 4 | outside_temperature_c | sensors.outside_temperature_c | sensors.outside_temperature_c | °C | -40 | 60 | 20 | | |
| 5 | outside_humidity_pct | sensors.outside_humidity_pct | sensors.outside_humidity_pct | % | 0 | 100 | 50 | | |
| 6 | air_temperature_valid | validity.air_temperature_c | validity.air_temperature | mask 0/1 | 0 | 1 | 0 | | false = brak czujnika |
| 7 | air_humidity_valid | validity.air_humidity_pct | validity.air_humidity | mask 0/1 | 0 | 1 | 0 | | |
| 8 | co2_valid | validity.co2_ppm | validity.co2 | mask 0/1 | 0 | 1 | 0 | | |
| 9 | soil_moisture_valid | validity.soil_moisture_pct | validity.soil_moisture | mask 0/1 | 0 | 1 | 0 | | |
| 10 | outside_temperature_valid | validity.outside_temperature_c | validity.outside_temperature | mask 0/1 | 0 | 1 | 0 | | |
| 11 | outside_humidity_valid | validity.outside_humidity_pct | validity.outside_humidity | mask 0/1 | 0 | 1 | 0 | | |
| 12 | growbox_volume_m3 | environment.growbox_volume_m3 | environment.growbox_volume_m3 | m³ | 0.05 | 100 | 1 | | konfiguracja stała |
| 13 | thermal_mass_j_per_k | environment.thermal_mass_j_per_k | environment.thermal_mass_j_per_k | J/K | 1000 | 10M | 100000 | | |
| 14 | heat_loss_w_per_k | environment.heat_loss_w_per_k | environment.heat_loss_w_per_k | W/K | 0 | 5000 | 30 | | |
| 15 | air_leak_rate_ach | environment.air_leak_rate_ach | environment.air_leak_rate_ach | 1/h | 0 | 20 | 1 | | |
| 16 | pot_volume_l | cultivation.pot_volume_l | cultivation.pot_volume_l | L | 0.1 | 100 | 10 | | |
| 17 | substrate_water_capacity_ml | cultivation.substrate_water_capacity_ml | cultivation.substrate_water_capacity_ml | mL | 10 | 100000 | 3000 | | |
| 18 | transpiration_factor | cultivation.transpiration_factor | cultivation.transpiration_factor | ratio | 0 | 10 | 1 | | |
| 19 | heater_available | actuators.heater.available | actuators.heater.available | mask 0/1 | 0 | 1 | 0 | | false = brak grzałki |
| 20 | heater_max_power_w | actuators.heater.max_power_w | actuators.heater.max_power_w | W | 0 | 10000 | 0 | | |
| 21 | heater_efficiency | actuators.heater.efficiency | actuators.heater.efficiency | ratio | 0 | 1 | 0 | | |
| 22 | heater_control_type | actuators.heater.control_type | actuators.heater.control_type | enum | 0 | 1 | 0 | | 0=binary, 1=pwm |
| 23 | fan_available | actuators.fan.available | actuators.fan.available | mask 0/1 | 0 | 1 | 0 | | jeden logiczny wentylator |
| 24 | fan_max_airflow_m3_h | actuators.fan.max_airflow_m3_h | actuators.fan.max_airflow_m3_h | m³/h | 0 | 10000 | 0 | | |
| 25 | fan_minimum_command | actuators.fan.minimum_command | actuators.fan.minimum_command | ratio | 0 | 1 | 0 | | min. PWM gdy włączony |
| 26 | humidifier_available | actuators.humidifier.available | actuators.humidifier.available | mask 0/1 | 0 | 1 | 0 | | nawilżacz, nie osuszacz |
| 27 | humidifier_max_output_g_h | actuators.humidifier.max_output_g_h | actuators.humidifier.max_output_g_h | g/h | 0 | 10000 | 0 | | |
| 28 | irrigation_available | actuators.irrigation.available | actuators.irrigation_pump.available | mask 0/1 | 0 | 1 | 0 | | |
| 29 | irrigation_flow_ml_s | actuators.irrigation.flow_ml_s | actuators.irrigation_pump.flow_ml_s | mL/s | 0 | 1000 | 0 | | |
| 30 | irrigation_maximum_pulse_s | actuators.irrigation.maximum_pulse_s | actuators.irrigation_pump.maximum_pulse_s | s | 0 | 600 | 0 | | |
| 31 | irrigation_minimum_interval_s | actuators.irrigation.minimum_interval_s | actuators.irrigation_pump.minimum_interval_s | s | 0 | 86400 | 0 | | |
| 32 | target_air_temperature_c | targets.air_temperature_c | targets.air_temperature_c | °C | -20 | 60 | 25 | | cel użytkownika |
| 33 | target_air_humidity_pct | targets.air_humidity_pct | targets.air_humidity_pct | % | 0 | 100 | 65 | | |
| 34 | target_co2_ppm | targets.co2_ppm | targets.co2_ppm | ppm | 0 | 5000 | 850 | | |
| 35 | target_soil_moisture_pct | targets.soil_moisture_pct | targets.soil_moisture_pct | % | 0 | 100 | 50 | | |
| 36 | previous_heater | previous.heater | previous.heater | ratio 0–1 | 0 | 1 | 0 | | readback z mostka |
| 37 | previous_fan | previous.fan | previous.fan | ratio 0–1 | 0 | 1 | 0 | | |
| 38 | previous_humidifier | previous.humidifier | previous.humidifier | ratio 0–1 | 0 | 1 | 0 | | |
| 39 | previous_irrigation | previous.irrigation | previous.irrigation | ratio 0–1 | 0 | 1 | 0 | | |

Encoder: clamp do [min, max], potem `(wartość - min) / (max - min)` → [0, 1].

---

## Mózg (model)

| Parametr | Wartość v1 |
|----------|------------|
| Architektura | MLP 40 → 32 → 32 → 4 |
| Aktywacja wyjść | sigmoid → [0, 1] |
| Plik modelu (MCU) | `lib/environment_control/src/generated/EnvironmentModel.h` |
| Trening (PC) | `python -m tools.ml.pipeline --quick` |
| Wersja w logu | pole `model_version` w NDJSON (np. `environment-mlp-v1-quick-…`) |

---

## Wyjścia: 4 urządzenia

| # | Nazwa | Pole `raw_output` | Pole `safe_output` | Zakres | Znaczenie | Twój sprzęt fizyczny | Uwagi |
|---|-------|-------------------|--------------------|--------|-----------|----------------------|-------|
| 0 | heater | raw.heater | safe.heater | 0–1 | moc grzałki | | binary: safety progowe 0.5 |
| 1 | fan | raw.fan | safe.fan | 0–1 | wentylacja | | alarm temp → min ~0.6 |
| 2 | humidifier | raw.humidifier | safe.humidifier | 0–1 | nawilżanie | | brak osuszacza w v1 |
| 3 | irrigation | raw.irrigation | safe.irrigation | 0–1 | pompa | | + `safe.irrigation_pulse_s` |

Dodatkowe pole po safety (nie z modelu): `safe_output.irrigation_pulse_s` — długość impulsu pompy [s].

---

## Safety — co zmienia wyjście (poza modelem)

Te pola **nie wchodzą do sieci**, ale wpływają na `safe_output`:

| Pole `SafetyConfig` | Domyślnie | Efekt |
|---------------------|-----------|--------|
| maximum_air_temperature_c | 35 °C | blokuje grzałkę |
| alarm_air_temperature_c | 32 °C | wymusza min. wentylator |
| alarm_minimum_fan | 0.6 | min. fan przy alarmie |
| binary_threshold | 0.5 | grzałka/nawilżacz ON/OFF |
| heater_minimum_on_s / off_s | 30 s | anty-flapping grzałki |
| humidifier_minimum_on_s / off_s | 15 s | anty-flapping nawilżacza |

Typowe `safety_reason` w logu: `over_temperature`, `temperature_alarm_fan`, `actuator_unavailable`, `pump_minimum_interval`, `binary_threshold`.

---

## JSON w demo (serial / scenariusze)

Przykład `load_scenario` — grupy jak w tabeli:

```json
{
  "command": "load_scenario",
  "seed": 104,
  "sensors": { "air_temperature_c": 22.0, "air_humidity_pct": 58.0, "co2_ppm": 920.0, "soil_moisture_pct": 44.0, "outside_temperature_c": 18.0, "outside_humidity_pct": 52.0 },
  "validity": { "air_temperature_c": true, "air_humidity_pct": true, "co2_ppm": true, "soil_moisture_pct": true, "outside_temperature_c": true, "outside_humidity_pct": true },
  "environment": { "growbox_volume_m3": 1.2, "thermal_mass_j_per_k": 48000, "heat_loss_w_per_k": 7, "air_leak_rate_ach": 0.25 },
  "cultivation": { "pot_volume_l": 12, "substrate_water_capacity_ml": 3600, "transpiration_factor": 1.0 },
  "actuators": {
    "heater": { "available": true, "max_power_w": 180, "efficiency": 0.9, "control_type": "binary" },
    "fan": { "available": true, "max_airflow_m3_h": 120, "minimum_command": 0.2 },
    "humidifier": { "available": true, "max_output_g_h": 180 },
    "irrigation": { "available": true, "flow_ml_s": 22, "maximum_pulse_s": 4, "minimum_interval_s": 600 }
  },
  "targets": { "air_temperature_c": 25, "air_humidity_pct": 65, "co2_ppm": 850, "soil_moisture_pct": 50 },
  "previous": { "heater": 0, "fan": 0, "humidifier": 0, "irrigation": 0 }
}
```

Odpowiedź `decision`: `sensors`, `targets`, `raw_output`, `safe_output`, `diagnostics`.

---

## Planowane rozszerzenia (v2) — do wypełnienia

| Potrzebuję | Obecny slot v1 | Wymaga v2? | Notatka |
|------------|----------------|------------|---------|
| osuszacz | — | tak | albo reguła Nodeflow bez ML |
| 2. wentylator | fan (mapowanie) | nie / tak | mapowanie w LiteGraph vs osobne wyjście |
| wentylator wewnętrzny | fan | nie | proporcja w mostku |
| dodatkowy czujnik | — | tak | nowa cecha + retrening |
| | | | |
| | | | |

---

## Szybkie komendy

```bash
# trening + regeneracja modelu
python -m tools.ml.pipeline --quick

# scenariusz na płytce
python -m tools.serial.replay \
  --port /dev/cu.usbmodem1101 \
  --scenario examples/scenarios/nominal.jsonl \
  --output logs/nominal.ndjson
```