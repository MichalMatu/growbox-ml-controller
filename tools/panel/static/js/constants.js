const SCENARIO_DRAFT_VERSION = 1;
const HELP_TOPICS = {
  app: {
    title: "Panel — sterowanie",
    html: `
      <p>Panel wysyła scenariusz do firmware ESP32 i odczytuje decyzje modelu ML + warstwy safety.</p>
      <h4>Typowa ścieżka (Replay)</h4>
      <p><code>Połącz → Wyślij → ▶ → Krok</code></p>
      <h4>Sterowanie (lewa kolumna)</h4>
      <ul>
        <li><strong>Scenariusz</strong> — <strong>Wyślij</strong> (cały formularz na płytkę), <strong>Domyślne</strong> (reset formularza), <strong>Pobierz</strong> (JSON)</li>
        <li><strong>OK / lokalne</strong> — badge przy Scenariuszu: zgodność formularza ze scenariuszem na płytce</li>
        <li><strong>Praca</strong> — <strong>▶ / ■</strong>, <strong>Replay</strong> / <strong>Loop</strong>, <strong>Krok</strong></li>
        <li><strong>Diag.</strong> — <strong>Status</strong> (odśwież z płytki), <strong>Reset</strong> (symulacja krok 0)</li>
        <li><strong>Seed</strong> — ziarno symulatora; ta sama wartość + te same odczyty = powtarzalna symulacja (wysyłane przy <strong>Wyślij</strong>)</li>
        <li><strong>Połącz / ×</strong> — górny pasek, port USB; badge obok tytułu pokazuje krok, tryb i stan po połączeniu</li>
        <li><strong>Na żywo</strong> — prawa kolumna: tylko podgląd decyzji</li>
      </ul>
    `,
  },
  sensors: {
    title: "Czujniki",
    html: `
      <p>v2: powietrze + gleba w jednej karcie. Checkbox przy polu = czujnik ważny (encoder + safety).</p>
      <ul>
        <li><strong>Wewnętrzne</strong> — T, wilgotność, CO₂, temp. roztworu nawozu + <strong>Lampa</strong> (pseudo: świeci tak/nie, nie odczyt PPFD)</li>
        <li><strong>Zewnętrzne</strong> — T, wilgotność, CO₂ (symulacja, nie ML)</li>
        <li><strong>Donice</strong> — wilgotność i temp. gleby per donica; tick przy polu = czujnik podłączony</li>
        <li><strong>Donica aktywna</strong> — checkbox w nagłówku wiersza = strefa w profilu</li>
      </ul>
    `,
  },
  environment: {
    title: "Parametry growboxa",
    html: `
      <p>Fizyczny model symulacji — obudowa i donice. To nie są odczyty z czujników; wpływają na termikę, wilgotność powietrza i gleby w symulatorze oraz wektorze ML.</p>
      <p><strong>Obudowa</strong></p>
      <ul>
        <li><strong>Obj. m³</strong> — kubatura powietrza</li>
        <li><strong>Ciepło J/K</strong> — bezwładność termiczna</li>
        <li><strong>Strata W/K</strong> — utrata ciepła do otoczenia</li>
        <li><strong>Wyciek 1/h</strong> — wymiana powietrza (ACH)</li>
      </ul>
      <p><strong>Donice</strong> (per donica)</p>
      <ul>
        <li><strong>Don. L</strong> — objętość doniczki</li>
        <li><strong>Woda mL</strong> — pojemność wodna podłoża</li>
        <li><strong>Transp.</strong> — mnożnik transpiracji (wyżej = szybsze suszenie / pobór wody)</li>
      </ul>
      <p>Czujniki gleby, cele i pompy — w sekcjach Czujniki, Cele i Aktuary.</p>
    `,
  },
  actuators: {
    title: "Aktuary",
    html: `
      <p>Co jest podłączone w growboxie i jakie ma limity. Checkbox przy nazwie = urządzenie jest w zestawie.</p>
      <ul>
        <li><strong>Klimat</strong> (6 kart) i <strong>Pompy</strong> (4 karty) — ten sam układ: nazwa, checkbox, parametry w poziomym rzędzie</li>
        <li><strong>typ</strong> — <code>bin</code> / <code>pwm</code> na każdym aktuatorze klimatu i każdej pompie</li>
        <li><strong>Fan min</strong> — dolna granica PWM przy alarmie temperatury</li>
      </ul>
      <p>Checkbox zmienia tylko <strong>formularz lokalny</strong> — na płytkę trafia dopiero po <strong>Wyślij</strong> (badge „lokalne”). Sekcja <strong>Na żywo</strong> pokazuje ostatni krok z płytki, nie podgląd formularza.</p>
      <p>Brak urządzenia (checkbox off) po wysłaniu → model i safety wymuszają 0 na tym wyjściu.</p>
    `,
  },
  targets: {
    title: "Cele",
    html: `
      <p>Wartości zadane — do czego model ma dążyć.</p>
      <ul>
        <li><strong>Powietrze</strong> — temperatura, wilgotność, CO₂ (cały box)</li>
        <li><strong>Donice</strong> — docelowa wilgotność gleby per donica</li>
      </ul>
    `,
  },
  safety: {
    title: "Limity safety",
    html: `
      <p>Deterministyczne reguły <strong>SafetySupervisor</strong> — nie wchodzą do modelu ML, ale korygują <strong>safe_output</strong> (zielone paski).</p>
      <ul>
        <li><strong>T max</strong> — powyżej tej temperatury grzałka jest blokowana</li>
        <li><strong>Alarm T</strong> + <strong>Fan min</strong> — przy alarmie wymuszany minimalny fan</li>
        <li><strong>Próg bin</strong> — próg ON/OFF dla aktuatorów typu bin (domyślnie 0.5)</li>
        <li><strong>Grz./Naw. ON/OFF s</strong> — anty-flapping dla aktuatorów binarnych</li>
        <li><strong>ΔT nawóz–gleba</strong> + <strong>min. temp. roztworu</strong> — blokada podlewania</li>
      </ul>
      <p>Po zmianie kliknij <strong>Wyślij</strong>. W JSON decyzji: <code>diagnostics.safety_reason</code>.</p>
    `,
  },
  previous: {
    title: "Poprzedni stan aktuatorów",
    html: `
      <p>Ostatnie wyjścia sterownika w skali 0–1 z poprzedniego kroku.</p>
      <ul>
        <li>10 wyjść ML (6 globalnych + 4 pompy strefowe)</li>
        <li>Model używa tego jako kontekstu (histereza, płynność sterowania)</li>
      </ul>
      <p>Prawa kolumna, pod <strong>Na żywo</strong>. Po <strong>Krok</strong> wartości uzupełniają się z ostatnich wyjść <strong>Safety</strong> (kontekst modelu na następny krok).</p>
    `,
  },


  live: {
    title: "Na żywo",
    html: `
      <p>Podgląd decyzji po <strong>Krok</strong>: czujniki globalne + 10 wyjść ML. Badge kroku u góry. Edycja <strong>Poprzedni stan</strong> — osobna karta pod tą sekcją (prawa kolumna).</p>
      <p>Każdy aktuator ma <strong>dwa paski</strong>:</p>
      <ul>
        <li><strong>Model</strong> (niebieski) — co proponuje sieć neuronowa (0–100% mocy)</li>
        <li><strong>Safety</strong> (zielony) — co faktycznie idzie na płytkę po regułach bezpieczeństwa</li>
      </ul>
      <p>Pomarańczowa ramka i znak <strong>≠</strong> — tylko tam, gdzie safety <em>tego aktuatora</em> zmieniło wyjście modelu.</p>
      <p>Jeśli oba paski są takie same (np. fan 14% / 14%), karta ma etykietę <strong>bez zmian</strong> — safety przepuściło propozycję modelu.</p>
      <p>Kod safety i czas inferencji — po prawej w legendzie pasków. Pełna diagnostyka w <strong>JSON decyzji</strong>.</p>
    `,
  },
};
const TOOLBAR_STATE_CLASSES = [
  "state-on", "state-on-warn", "state-on-accent", "state-on-danger",
  "state-play", "state-stop",
  "state-off", "state-disabled", "state-error",
];
const LABEL_MAP = {
  air_temperature_c: "Temp",
  air_humidity_pct: "Wilg.",
  co2_ppm: "CO₂",
  nutrient_solution_temperature_c: "Roztwór",
  soil_moisture_pct: "Gleba",
  soil_temperature_c: "Gleba T",
  zone_1_available: "Strefa 1",
  lights_active: "Lampa",
  outside_temperature_c: "Temp",
  outside_humidity_pct: "Wilg.",
  outside_co2_ppm: "CO₂",
  growbox_volume_m3: "Obj. m³",
  thermal_mass_j_per_k: "Ciepło J/K",
  heat_loss_w_per_k: "Strata W/K",
  air_leak_rate_ach: "Wyciek 1/h",
  pot_volume_l: "Don. L",
  substrate_water_capacity_ml: "Woda mL",
  transpiration_factor: "Transp.",
  heater_max_power_w: "W max",
  heater_efficiency: "η",
  heater_control_type: "typ",
  fan_max_airflow_m3_h: "m³/h",
  fan_minimum_command: "min",
  fan_control_type: "typ",
  humidifier_max_output_g_h: "g/h",
  humidifier_control_type: "typ",
  dehumidifier_control_type: "typ",
  cooler_control_type: "typ",
  co2_doser_control_type: "typ",
  irrigation_control_type: "typ",
  irrigation_flow_ml_s: "mL/s",
  irrigation_maximum_pulse_s: "Impuls s",
  irrigation_minimum_interval_s: "Przerwa s",
  target_air_temperature_c: "T °C",
  target_air_humidity_pct: "Wilg %",
  target_co2_ppm: "CO₂",
  target_soil_moisture_pct: "Gleba %",
  maximum_air_temperature_c: "T max",
  alarm_air_temperature_c: "Alarm T",
  alarm_minimum_fan: "Fan min",
  binary_threshold: "Próg bin",
  heater_minimum_on_s: "Grz. ON s",
  heater_minimum_off_s: "Grz. OFF s",
  humidifier_minimum_on_s: "Naw. ON s",
  humidifier_minimum_off_s: "Naw. OFF s",
  previous_heater: "Grzałka",
  previous_fan: "Fan",
  previous_humidifier: "Nawilż.",
  previous_irrigation: "Pompa",
  previous_dehumidifier: "Osusz.",
  previous_cooler: "Chłodz.",
  previous_co2_doser: "CO₂",
  dehumidifier_available: "Osuszacz",
  dehumidifier_max_removal_g_h: "g/h",
  cooler_available: "Chłodzenie",
  cooler_max_cooling_w: "W",
  co2_doser_available: "CO₂",
  co2_doser_dose_ppm_per_full_pulse: "ppm/puls",
  co2_doser_maximum_pulse_s: "Impuls s",
  maximum_nutrient_soil_delta_c: "ΔT max",
  minimum_nutrient_solution_temperature_c: "Min. roztwór",
};

const SIMULATION_SENSOR_FIELDS = {
  outside_co2_ppm: { minimum: 0, maximum: 5000, default: 420 },
};

const SENSOR_GROUPS = [
  {
    title: "Wewnętrzne",
    sensors: [
      ["air_temperature_c", "air_temperature_c"],
      ["air_humidity_pct", "air_humidity_pct"],
      ["co2_ppm", "co2_ppm"],
      ["nutrient_solution_temperature_c", "nutrient_solution_temperature_c"],
    ],
  },
  {
    title: "Zewnętrzne",
    sensors: [
      ["outside_temperature_c", "outside_temperature_c"],
      ["outside_humidity_pct", "outside_humidity_pct"],
      ["outside_co2_ppm", "outside_co2_ppm"],
    ],
  },
];

const POT_SENSOR_ROWS = [
  {
    title: "Donica 1",
    zoneAvailable: "zone_1_available",
    moisture: "soil_moisture_zone_1_pct",
    moistureValid: "soil_moisture_zone_1_valid",
    temp: "soil_temperature_zone_1_c",
    tempValid: "soil_temperature_zone_1_valid",
  },
  {
    title: "Donica 2",
    zoneAvailable: "zone_2_available",
    moisture: "soil_moisture_zone_2_pct",
    moistureValid: "soil_moisture_zone_2_valid",
    temp: "soil_temperature_zone_2_c",
    tempValid: "soil_temperature_zone_2_valid",
  },
  {
    title: "Donica 3",
    zoneAvailable: "zone_3_available",
    moisture: "soil_moisture_zone_3_pct",
    moistureValid: "soil_moisture_zone_3_valid",
    temp: "soil_temperature_zone_3_c",
    tempValid: "soil_temperature_zone_3_valid",
  },
  {
    title: "Donica 4",
    zoneAvailable: "zone_4_available",
    moisture: "soil_moisture_zone_4_pct",
    moistureValid: "soil_moisture_zone_4_valid",
    temp: "soil_temperature_zone_4_c",
    tempValid: "soil_temperature_zone_4_valid",
  },
];

const TARGET_AIR_FIELDS = [
  "target_air_temperature_c",
  "target_air_humidity_pct",
  "target_co2_ppm",
];

const TARGET_SOIL_FIELDS = [
  "zone_1_target_soil_moisture_pct",
  "zone_2_target_soil_moisture_pct",
  "zone_3_target_soil_moisture_pct",
  "zone_4_target_soil_moisture_pct",
];

const PREVIOUS_GLOBAL_FIELDS = [
  "previous_heater",
  "previous_fan",
  "previous_humidifier",
  "previous_dehumidifier",
  "previous_cooler",
  "previous_co2_doser",
];

const PREVIOUS_PUMP_FIELDS = [
  "zone_1_previous_irrigation",
  "zone_2_previous_irrigation",
  "zone_3_previous_irrigation",
  "zone_4_previous_irrigation",
];

const LIVE_SENSOR_GROUPS = [
  {
    title: "Wewnętrzne",
    metrics: [
      { key: "air_temperature_c", targetKey: "air_temperature_c", decimals: 1, unit: "°C" },
      { key: "air_humidity_pct", targetKey: "air_humidity_pct", decimals: 0, unit: "%" },
      { key: "co2_ppm", targetKey: "co2_ppm", decimals: 0, unit: " ppm" },
      { key: "nutrient_solution_temperature_c", targetKey: null, decimals: 1, unit: "°C" },
    ],
  },
  {
    title: "Zewnętrzne",
    metrics: [
      { key: "outside_temperature_c", targetKey: null, decimals: 1, unit: "°C" },
      { key: "outside_humidity_pct", targetKey: null, decimals: 0, unit: "%" },
      { key: "outside_co2_ppm", targetKey: null, decimals: 0, unit: " ppm", simulationOnly: true },
    ],
  },
];

var SCENARIO_SYNC_KEYS = [
  "sensors", "validity", "zones", "pseudo", "environment", "actuators", "targets", "safety", "previous",
];
const ACTUATOR_CLIMATE_GROUPS = [
  ["Grzałka", ["heater_available", "heater_max_power_w", "heater_efficiency", "heater_control_type"]],
  ["Fan", ["fan_available", "fan_max_airflow_m3_h", "fan_minimum_command", "fan_control_type"]],
  ["Nawilżacz", ["humidifier_available", "humidifier_max_output_g_h", "humidifier_control_type"]],
  ["Osuszacz", ["dehumidifier_available", "dehumidifier_max_removal_g_h", "dehumidifier_control_type"]],
  ["Chłodzenie", ["cooler_available", "cooler_max_cooling_w", "cooler_control_type"]],
  ["CO₂", ["co2_doser_available", "co2_doser_dose_ppm_per_full_pulse", "co2_doser_maximum_pulse_s", "co2_doser_control_type"]],
];

const ACTUATOR_PUMP_GROUPS = [
  ["Pompa 1", ["zone_1_irrigation_available", "zone_1_irrigation_flow_ml_s", "zone_1_irrigation_maximum_pulse_s", "zone_1_irrigation_minimum_interval_s", "zone_1_irrigation_control_type"]],
  ["Pompa 2", ["zone_2_irrigation_available", "zone_2_irrigation_flow_ml_s", "zone_2_irrigation_maximum_pulse_s", "zone_2_irrigation_minimum_interval_s", "zone_2_irrigation_control_type"]],
  ["Pompa 3", ["zone_3_irrigation_available", "zone_3_irrigation_flow_ml_s", "zone_3_irrigation_maximum_pulse_s", "zone_3_irrigation_minimum_interval_s", "zone_3_irrigation_control_type"]],
  ["Pompa 4", ["zone_4_irrigation_available", "zone_4_irrigation_flow_ml_s", "zone_4_irrigation_maximum_pulse_s", "zone_4_irrigation_minimum_interval_s", "zone_4_irrigation_control_type"]],
];

const OUTPUT_LABELS = {
  heater: "Grzałka",
  fan: "Fan",
  humidifier: "Nawilżacz",
  dehumidifier: "Osuszacz",
  cooler: "Chłodzenie",
  co2_doser: "CO₂",
  irrigation_zone_1: "Pompa 1",
  irrigation_zone_2: "Pompa 2",
  irrigation_zone_3: "Pompa 3",
  irrigation_zone_4: "Pompa 4",
  zone_1_target_soil_moisture_pct: "Donica 1",
  zone_2_target_soil_moisture_pct: "Donica 2",
  zone_3_target_soil_moisture_pct: "Donica 3",
  zone_4_target_soil_moisture_pct: "Donica 4",
};

function isAvailabilityField(name) {
  return name.endsWith("_available");
}

const FIELD_HINTS = {
  air_temperature_c: "Temperatura powietrza w growboxie (wejście modelu ML)",
  air_humidity_pct: "Wilgotność powietrza w growboxie (wejście ML)",
  co2_ppm: "Stężenie CO₂ w growboxie (wejście ML)",
  soil_moisture_pct: "Wilgotność podłoża w doniczce (wejście ML)",
  outside_temperature_c: "Temperatura na zewnątrz (wpływa na symulację, nie trafia do ML)",
  outside_humidity_pct: "Wilgotność na zewnątrz (wpływa na symulację)",
  outside_co2_ppm: "CO₂ na zewnątrz — tylko symulacja; nie trafia do modelu ML",
  growbox_volume_m3: "Kubatura powietrza w growboxie (m³)",
  thermal_mass_j_per_k: "Bezwładność termiczna — jak szybko zmienia się temperatura",
  heat_loss_w_per_k: "Strata ciepła do otoczenia (W/K)",
  air_leak_rate_ach: "Wymiana powietrza — air changes per hour (1/h)",
  pot_volume_l: "Objętość doniczki (litry)",
  substrate_water_capacity_ml: "Pojemność wodna podłoża (mL)",
  transpiration_factor: "Mnożnik transpiracji — wyżej = szybsze suszenie i pobór wody",
  heater_available: "Grzałka w zestawie — odznaczone = wyjście zawsze 0 po wysłaniu",
  heater_max_power_w: "Maksymalna moc grzałki (W)",
  heater_efficiency: "Sprawność grzałki (0–1) — ułamek mocy idącej do powietrza",
  fan_available: "Wentylator w zestawie — odznaczone = wyjście zawsze 0 po wysłaniu",
  fan_max_airflow_m3_h: "Maks. przepływ wentylatora (m³/h)",
  humidifier_available: "Nawilżacz w zestawie — odznaczone = wyjście zawsze 0 po wysłaniu",
  humidifier_max_output_g_h: "Maks. wydajność nawilżacza (g/h)",
  irrigation_available: "Pompa w zestawie — odznaczone = wyjście zawsze 0 po wysłaniu",
  irrigation_flow_ml_s: "Przepływ pompy podlewania (mL/s)",
  irrigation_maximum_pulse_s: "Maks. czas jednego impulsu podlewania (sekundy)",
  irrigation_minimum_interval_s: "Min. przerwa między kolejnymi podlaniami (sekundy)",
  fan_minimum_command: "Min. PWM przy alarmie temperatury (nie przy normalnej pracy)",
  heater_control_type: "bin = przekaźnik wł/wył, pwm = modulacja mocy",
  fan_control_type: "Typowo pwm (regulacja obrotów). bin = wł/wył",
  humidifier_control_type: "Typowo bin (wł/wył). pwm = modulacja",
  dehumidifier_control_type: "Typowo bin (wł/wył). pwm = modulacja mocy",
  cooler_control_type: "Typowo bin (wł/wył). pwm = modulacja mocy",
  co2_doser_control_type: "Typowo bin (impuls ON/OFF). pwm = modulacja długości impulsu",
  irrigation_control_type: "Typowo bin (impuls ON/OFF). pwm = długość impulsu z modelu",
  target_air_temperature_c: "Docelowa temperatura powietrza w growboxie",
  target_air_humidity_pct: "Docelowa wilgotność powietrza",
  target_co2_ppm: "Docelowe stężenie CO₂",
  target_soil_moisture_pct: "Docelowa wilgotność gleby",
  maximum_air_temperature_c: "Powyżej tej T wewnętrznej grzałka = 0 (niezależnie od modelu)",
  alarm_air_temperature_c: "Od tej T włącza się alarm wentylacji",
  alarm_minimum_fan: "Minimalny fan przy alarmie temperatury (max z Fan min w aktuatorach)",
  binary_threshold: "Próg 0–1: propozycja modelu ≥ próg → ON dla typu bin",
  heater_minimum_on_s: "Min. czas grzałki ON zanim można wyłączyć",
  heater_minimum_off_s: "Min. czas grzałki OFF zanim można włączyć",
  humidifier_minimum_on_s: "Min. czas nawilżacza ON",
  humidifier_minimum_off_s: "Min. czas nawilżacza OFF",
};

function validityHint(sensorKey) {
  if (sensorKey === "outside_co2_ppm") {
    return "Odznaczony = symulator używa 420 ppm CO₂ zewnętrznego";
  }
  return "Odznaczony = odczyt nieważny (ML i safety ignorują)";
}
const ACTUATOR_AVAILABILITY_PATHS = {
  heater: "actuators.heater.available",
  fan: "actuators.fan.available",
  humidifier: "actuators.humidifier.available",
  dehumidifier: "actuators.dehumidifier.available",
  cooler: "actuators.cooler.available",
  co2_doser: "actuators.co2_doser.available",
  irrigation_zone_1: "zones.0.irrigation.available",
  irrigation_zone_2: "zones.1.irrigation.available",
  irrigation_zone_3: "zones.2.irrigation.available",
  irrigation_zone_4: "zones.3.irrigation.available",
};
const SAFETY_REASON_ACTUATOR_UNAVAILABLE = 64;
