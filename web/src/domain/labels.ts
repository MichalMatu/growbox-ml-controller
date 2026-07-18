import type { FeatureDefinition } from "./types"

const fieldLabels: Record<string, string> = {
  available: "Zainstalowane",
  air_temperature_c: "Temperatura powietrza",
  air_humidity_pct: "Wilgotność powietrza",
  co2_ppm: "Stężenie CO₂",
  nutrient_solution_temperature_c: "Temperatura pożywki",
  outside_temperature_c: "Temperatura zewnętrzna",
  outside_humidity_pct: "Wilgotność zewnętrzna",
  outside_co2_ppm: "CO₂ na zewnątrz",
  soil_moisture_pct: "Wilgotność podłoża",
  soil_temperature_c: "Temperatura podłoża",
  lights_active: "Światło aktywne",
  growbox_volume_m3: "Objętość komory",
  thermal_mass_j_per_k: "Masa termiczna",
  heat_loss_w_per_k: "Strata ciepła",
  air_leak_rate_ach: "Wymiana przez nieszczelności",
  max_power_w: "Maksymalna moc",
  max_airflow_m3_h: "Maksymalny przepływ powietrza",
  minimum_command: "Minimalne sterowanie",
  max_output_g_h: "Maksymalna wydajność",
  max_removal_g_h: "Maksymalne osuszanie",
  max_cooling_w: "Maksymalna moc chłodzenia",
  dose_ppm_per_full_pulse: "Dawka na pełny impuls",
  maximum_pulse_s: "Maksymalny impuls",
  efficiency: "Sprawność",
  pot_volume_l: "Objętość donicy",
  substrate_water_capacity_ml: "Pojemność wodna podłoża",
  transpiration_factor: "Współczynnik transpiracji",
  flow_ml_s: "Przepływ",
  minimum_interval_s: "Minimalny odstęp",
  control_type: "Rodzaj sterowania",
}

const actuatorLabels: Record<string, string> = {
  heater: "Grzałka powietrza",
  fan: "Wentylator",
  humidifier: "Nawilżacz",
  dehumidifier: "Osuszacz",
  cooler: "Chłodzenie",
  co2_doser: "Dozownik CO₂",
  nutrient_heater: "Grzałka pożywki",
}

function startCase(value: string): string {
  return value
    .split("_")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ")
}

export function getFeatureLabel(feature: FeatureDefinition): string {
  const field = feature.path.split(".").at(-1) ?? feature.name
  return fieldLabels[field] ?? startCase(field)
}

export function getActuatorLabel(id: string): string {
  return actuatorLabels[id] ?? startCase(id)
}

export function formatUnit(feature: FeatureDefinition): string {
  return feature.unit === "enum" ? "wybór" : feature.unit
}
