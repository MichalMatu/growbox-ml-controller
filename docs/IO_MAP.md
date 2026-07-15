# Mapowanie I/O

**Pełna lista pól, kolejność cech i zakresy:** [`schemas/environment-controller-v1.json`](../schemas/environment-controller-v1.json) (v2 — [`plan.md`](plan.md)).

Nie duplikujemy tu 40+ wierszy tabeli — schema JSON jest jedynym źródłem prawdy dla modelu.

## Przepływ

```text
ControllerInput → FeatureEncoder → ModelRuntime → SafetySupervisor → safe_output
```

Kod: `lib/environment_control/src/` (`EnvironmentTypes.h`, `FeatureEncoder.cpp`, `SafetySupervisor.cpp`).

## v1 — skrót

| Grupa | Liczba | Do modelu? |
|-------|--------|------------|
| czujniki + validity | 6 + 6 | tak |
| environment + cultivation | 4 + 3 | tak |
| aktuary (możliwości) | 4 urządzenia | tak |
| cele | 4 | tak |
| previous | 4 | tak |
| safety + czas | — | **nie** (tylko SafetySupervisor) |

**Wyjścia modelu:** `heater`, `fan`, `humidifier`, `irrigation` (0–1).
**Poza modelem:** `safe.irrigation_pulse_s` (safety).

## Luki względem firmware (do v2)

| Pole | W panelu / serial | W modelu v1 |
|------|-------------------|-------------|
| `outside_co2_ppm` | tak | nie |

Plan rozszerzeń: [plan.md](plan.md) (osuszacz, chłodzenie, …).

## Twój sprzęt — do wypełnienia

| Slot kontraktu | Fizyczne urządzenie / czujnik | Uwagi |
|----------------|------------------------------|-------|
| air_temperature_c | | |
| air_humidity_pct | | |
| co2_ppm | | |
| soil_moisture_pct | | |
| outside_temperature_c | | |
| outside_humidity_pct | | |
| outside_co2_ppm | | v2 |
| heater | | |
| fan | | jeden slot ML → ewent. kilka fanów w mostku |
| humidifier | | |
| dehumidifier | | v2 — plan |
| cooler | | v2 — plan (klimatyzator) |
| irrigation | | |

## JSON (demo / panel)

Grupy: `sensors`, `validity`, `environment`, `cultivation`, `actuators`, `targets`, `previous`, `safety`.

Przykład: preset `NOMINAL_PRESET` w `tools/panel/form_schema.py`.
