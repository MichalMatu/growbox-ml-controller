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
      <p>Siedem odczytów w scenariuszu: sześć wejść modelu v1 + CO₂ zewnętrzne (tylko symulacja).</p>
      <ul>
        <li><strong>Wewnętrzne</strong> — T, wilgotność, CO₂, gleba (stan w growboxie, wejścia ML)</li>
        <li><strong>Zewnętrzne</strong> — T, wilgotność i CO₂ na zewnątrz (wpływ na symulację; CO₂ zewn. nie trafia do modelu)</li>
        <li><strong>Checkbox</strong> — ważność odczytu; odznaczony = nieważny (ML: safety; CO₂ zewn.: symulator używa 420 ppm)</li>
      </ul>
    `,
  },
  environment: {
    title: "Parametry growboxa",
    html: `
      <p>Parametry fizyczne obudowy — wpływają na to, jak symulator reaguje na grzałkę, fan i wyciek ciepła.</p>
      <ul>
        <li><strong>Objętość</strong> — kubatura powietrza w m³</li>
        <li><strong>Ciepło J/K</strong> — bezwładność termiczna</li>
        <li><strong>Strata W/K</strong> — utrata ciepła do otoczenia</li>
        <li><strong>Wyciek 1/h</strong> — wymiana powietrza (ACH)</li>
      </ul>
    `,
  },
  cultivation: {
    title: "Uprawa / doniczka",
    html: `
      <p>Parametry rośliny i podłoża w symulacji.</p>
      <ul>
        <li><strong>Don. L</strong> — objętość doniczki</li>
        <li><strong>Woda mL</strong> — pojemność wodna podłoża</li>
        <li><strong>Transp.</strong> — mnożnik transpiracji (wyżej = szybsze suszenie / pobór wody)</li>
      </ul>
    `,
  },
  actuators: {
    title: "Aktuary (możliwości)",
    html: `
      <p>Co jest podłączone w growboxie i jakie ma limity. Checkbox przy nazwie = urządzenie jest w zestawie.</p>
      <ul>
        <li><strong>typ</strong> — <code>bin</code> (wł/wył, próg 50%) lub <code>pwm</code> (0–100%). Po zmianie kliknij <strong>Wyślij</strong>.</li>
        <li><strong>Fan min</strong> — dolna granica PWM przy alarmie temperatury</li>
        <li><strong>Pompa</strong> — przepływ mL/s, <strong>Impuls s</strong> (krótki, np. 4), <strong>Przerwa s</strong> (długi, np. 600 między podlaniami)</li>
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
        <li>Temperatura i wilgotność powietrza</li>
        <li>CO₂</li>
        <li>Wilgotność gleby</li>
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
        <li><strong>Grz./Naw. ON/OFF s</strong> — minimalny czas włączenia/wyłączenia (anty-flapping)</li>
      </ul>
      <p>Po zmianie kliknij <strong>Wyślij</strong>. W JSON decyzji: <code>diagnostics.safety_reason</code>.</p>
    `,
  },
  previous: {
    title: "Poprzedni stan aktuatorów",
    html: `
      <p>Ostatnie wyjścia sterownika w skali 0–1 z poprzedniego kroku.</p>
      <ul>
        <li>Grzałka, fan, nawilżacz, pompa</li>
        <li>Model używa tego jako kontekstu (histereza, płynność sterowania)</li>
      </ul>
      <p>W panelu <strong>Na żywo</strong>, pod paskami aktuatorów. Po <strong>Krok</strong> pokazuje procenty z ostatnich wyjść <strong>Safety</strong> (kontekst modelu na następny krok).</p>
    `,
  },
  live: {
    title: "Na żywo",
    html: `
      <p>Podgląd ostatniej decyzji z firmware po <strong>Krok</strong>: tabelka z 6 czujnikami (odczyt + cel). Numer kroku — badge u góry po prawej. Poniżej pasków: <strong>Poprzedni stan</strong> — wyjścia Safety z ostatniego kroku.</p>
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
  soil_moisture_pct: "Gleba",
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
      ["soil_moisture_pct", "soil_moisture_pct"],
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

const LIVE_SENSOR_GROUPS = [
  {
    title: "Wewnętrzne",
    metrics: [
      { key: "air_temperature_c", targetKey: "air_temperature_c", decimals: 1, unit: "°C" },
      { key: "air_humidity_pct", targetKey: "air_humidity_pct", decimals: 0, unit: "%" },
      { key: "co2_ppm", targetKey: "co2_ppm", decimals: 0, unit: " ppm" },
      { key: "soil_moisture_pct", targetKey: "soil_moisture_pct", decimals: 0, unit: "%" },
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
  "sensors", "validity", "environment", "cultivation", "actuators", "targets", "safety",
];
const ACTUATOR_GROUPS = [
  ["Grzałka", ["heater_available", "heater_max_power_w", "heater_efficiency", "heater_control_type"]],
  ["Fan", ["fan_available", "fan_max_airflow_m3_h", "fan_minimum_command", "fan_control_type"]],
  ["Nawilżacz", ["humidifier_available", "humidifier_max_output_g_h", "humidifier_control_type"]],
  ["Pompa", ["irrigation_available", "irrigation_flow_ml_s", "irrigation_maximum_pulse_s", "irrigation_minimum_interval_s", "irrigation_control_type"]],
];

function isAvailabilityField(name) {
  return name.endsWith("_available");
}

const FIELD_HINTS = {
  irrigation_maximum_pulse_s: "Maks. czas jednego impulsu podlewania (sekundy)",
  irrigation_minimum_interval_s: "Min. przerwa między kolejnymi podlaniami (sekundy)",
  fan_minimum_command: "Min. PWM przy alarmie temperatury (nie przy normalnej pracy)",
  heater_control_type: "bin = przekaźnik wł/wył, pwm = modulacja mocy",
  fan_control_type: "Typowo pwm (regulacja obrotów). bin = wł/wył",
  humidifier_control_type: "Typowo bin (wł/wył). pwm = modulacja",
  irrigation_control_type: "Typowo bin (impuls ON/OFF). pwm = długość impulsu z modelu",
  maximum_air_temperature_c: "Powyżej tej T wewnętrznej grzałka = 0 (niezależnie od modelu)",
  alarm_air_temperature_c: "Od tej T włącza się alarm wentylacji",
  alarm_minimum_fan: "Minimalny fan przy alarmie temperatury (max z Fan min w aktuatorach)",
  binary_threshold: "Próg 0–1: propozycja modelu ≥ próg → ON dla typu bin",
  heater_minimum_on_s: "Min. czas grzałki ON zanim można wyłączyć",
  heater_minimum_off_s: "Min. czas grzałki OFF zanim można włączyć",
  humidifier_minimum_on_s: "Min. czas nawilżacza ON",
  humidifier_minimum_off_s: "Min. czas nawilżacza OFF",
};
const ACTUATOR_AVAILABILITY_PATHS = {
  heater: "actuators.heater.available",
  fan: "actuators.fan.available",
  humidifier: "actuators.humidifier.available",
  irrigation: "actuators.irrigation.available",
};
const SAFETY_REASON_ACTUATOR_UNAVAILABLE = 64;
