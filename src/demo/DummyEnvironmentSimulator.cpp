#include "DummyEnvironmentSimulator.h"

#include <cmath>

namespace growbox {
namespace demo {
namespace {

constexpr float kSecondsPerHour = 3600.0f;

control::PotConfig makeInactivePot() noexcept {
  control::PotConfig pot{};
  pot.available = false;
  return pot;
}

control::PotConfig makeActiveZone() noexcept {
  control::PotConfig pot{};
  pot.available = true;
  pot.sensors.soil_moisture_pct = 44.0f;
  pot.sensors.soil_temperature_c = 20.0f;
  pot.validity.soil_moisture = true;
  pot.validity.soil_temperature = true;
  pot.cultivation.pot_volume_l = 12.0f;
  pot.cultivation.substrate_water_capacity_ml = 3600.0f;
  pot.cultivation.transpiration_factor = 1.0f;
  pot.target_soil_moisture_pct = 50.0f;
  pot.irrigation.available = true;
  pot.irrigation.flow_ml_s = 22.0f;
  pot.irrigation.maximum_pulse_s = 4.0f;
  pot.irrigation.minimum_interval_s = 600.0f;
  pot.irrigation.control_type = control::ActuatorControlType::Binary;
  return pot;
}

} // namespace

DummyEnvironmentSimulator::DummyEnvironmentSimulator() noexcept {
  reset();
}

void DummyEnvironmentSimulator::reset(std::uint32_t seed) noexcept {
  input_ = control::ControllerInput{};
  input_.sensors.air_temperature_c = 22.0f;
  input_.sensors.air_humidity_pct = 58.0f;
  input_.sensors.co2_ppm = 920.0f;
  input_.sensors.nutrient_solution_temperature_c = 20.0f;
  input_.sensors.outside_temperature_c = 18.0f;
  input_.sensors.outside_humidity_pct = 52.0f;
  input_.sensors.outside_co2_ppm = 420.0f;
  input_.validity.air_temperature = true;
  input_.validity.air_humidity = true;
  input_.validity.co2 = true;
  input_.validity.nutrient_solution_temperature = true;
  input_.validity.outside_temperature = true;
  input_.validity.outside_humidity = true;
  input_.validity.outside_co2 = true;

  input_.pots = {{
      makeActiveZone(),
      makeInactivePot(),
      makeInactivePot(),
      makeInactivePot(),
  }};
  input_.lights_active = false;

  input_.environment.growbox_volume_m3 = 1.2f;
  input_.environment.thermal_mass_j_per_k = 48000.0f;
  input_.environment.heat_loss_w_per_k = 7.0f;
  input_.environment.air_leak_rate_ach = 0.25f;

  input_.actuators.heater.available = true;
  input_.actuators.heater.max_power_w = 180.0f;
  input_.actuators.heater.efficiency = 0.9f;
  input_.actuators.fan.available = true;
  input_.actuators.fan.max_airflow_m3_h = 120.0f;
  input_.actuators.fan.minimum_command = 0.2f;
  input_.actuators.humidifier.available = true;
  input_.actuators.humidifier.max_output_g_h = 180.0f;
  input_.actuators.dehumidifier.available = false;
  input_.actuators.dehumidifier.max_removal_g_h = 80.0f;
  input_.actuators.cooler.available = false;
  input_.actuators.cooler.max_cooling_w = 200.0f;
  input_.actuators.co2_doser.available = false;
  input_.actuators.co2_doser.dose_ppm_per_full_pulse = 120.0f;
  input_.actuators.co2_doser.maximum_pulse_s = 3.0f;

  input_.targets.air_temperature_c = 25.0f;
  input_.targets.air_humidity_pct = 65.0f;
  input_.targets.co2_ppm = 850.0f;
  input_.targets.nutrient_solution_temperature_c = 22.0f;
  input_.monotonic_time_ms = 0U;
  setSeed(seed);
  elapsed_s_ = 0.0f;
  last_irrigation_s_.fill(-1.0e30f);
  effective_heater_ = 0.0f;
  effective_fan_ = 0.0f;
  effective_humidifier_ = 0.0f;
  effective_dehumidifier_ = 0.0f;
  effective_cooler_ = 0.0f;
  effective_nutrient_heater_ = 0.0f;
}

void DummyEnvironmentSimulator::load(const control::ControllerInput& scenario,
                                     std::uint32_t seed) noexcept {
  input_ = scenario;
  input_.monotonic_time_ms = 0U;
  setSeed(seed);
  elapsed_s_ = 0.0f;
  last_irrigation_s_.fill(-1.0e30f);
  effective_heater_ = clamp(input_.previous.heater, 0.0f, 1.0f);
  effective_fan_ = clamp(input_.previous.fan, 0.0f, 1.0f);
  effective_humidifier_ = clamp(input_.previous.humidifier, 0.0f, 1.0f);
  effective_dehumidifier_ = clamp(input_.previous.dehumidifier, 0.0f, 1.0f);
  effective_cooler_ = clamp(input_.previous.cooler, 0.0f, 1.0f);
  effective_nutrient_heater_ = clamp(input_.previous.nutrient_heater, 0.0f, 1.0f);
}

void DummyEnvironmentSimulator::setSeed(std::uint32_t seed) noexcept {
  initial_seed_ = seed == 0U ? 1U : seed;
  rng_state_ = initial_seed_;
}

void DummyEnvironmentSimulator::setSensors(const control::SensorState& sensors,
                                           const control::SensorValidity& validity) noexcept {
  input_.sensors = sensors;
  input_.validity = validity;
}

void DummyEnvironmentSimulator::setTargets(const control::ControlTargets& targets) noexcept {
  input_.targets = targets;
}

void DummyEnvironmentSimulator::setActuators(
    const control::GlobalActuatorCapabilities& actuators) noexcept {
  input_.actuators = actuators;
}

float DummyEnvironmentSimulator::uniformSigned() noexcept {
  rng_state_ = rng_state_ * 1664525U + 1013904223U;
  const float zero_to_one =
      static_cast<float>((rng_state_ >> 8U) & 0x00FFFFFFU) / static_cast<float>(0x01000000U);
  return zero_to_one * 2.0f - 1.0f;
}

float DummyEnvironmentSimulator::clamp(float value, float lower, float upper) noexcept {
  return value < lower ? lower : (value > upper ? upper : value);
}

float DummyEnvironmentSimulator::lag(float previous, float requested, float dt,
                                     float time_constant) noexcept {
  if (time_constant <= 0.0f) {
    return requested;
  }
  const float alpha = 1.0f - std::exp(-dt / time_constant);
  return previous + alpha * (requested - previous);
}

bool DummyEnvironmentSimulator::irrigationReady(std::size_t pot_index) const noexcept {
  if (pot_index >= control::kMaxPots) {
    return false;
  }
  const auto& pot = input_.pots[pot_index];
  return elapsed_s_ - last_irrigation_s_[pot_index] >= pot.irrigation.minimum_interval_s;
}

float DummyEnvironmentSimulator::irrigationCommand(
    std::size_t pot_index, const control::SafeControlDecision& decision) const noexcept {
  switch (pot_index) {
  case 0U:
    return decision.irrigation_pot_1;
  case 1U:
    return decision.irrigation_pot_2;
  case 2U:
    return decision.irrigation_pot_3;
  default:
    return decision.irrigation_pot_4;
  }
}

float DummyEnvironmentSimulator::heatMatCommand(
    std::size_t pot_index, const control::SafeControlDecision& decision) const noexcept {
  switch (pot_index) {
  case 0U:
    return decision.heat_mat_pot_1;
  case 1U:
    return decision.heat_mat_pot_2;
  case 2U:
    return decision.heat_mat_pot_3;
  default:
    return decision.heat_mat_pot_4;
  }
}

float DummyEnvironmentSimulator::zoneEvaporationPctPerSecond(
    std::size_t pot_index, float vapor_deficit, float air_temperature_c) const noexcept {
  if (pot_index >= control::kMaxPots) {
    return 0.0f;
  }
  const auto& pot = input_.pots[pot_index];
  if (!pot.available || !pot.validity.soil_moisture) {
    return 0.0f;
  }

  const float soil_factor = clamp(pot.sensors.soil_moisture_pct / 55.0f, 0.05f, 1.2f);
  float soil_temp_factor = 1.0f;
  if (pot.validity.soil_temperature) {
    soil_temp_factor = clamp((pot.sensors.soil_temperature_c - 5.0f) / 18.0f, 0.2f, 1.8f);
  }
  const float air_temp_factor = clamp((air_temperature_c - 5.0f) / 20.0f, 0.2f, 1.8f);
  const float volume = clamp(input_.environment.growbox_volume_m3, 0.05f, 100.0f);
  const float air_moisture_capacity_g = volume * 20.0f < 1.0f ? 1.0f : volume * 20.0f;
  const float transpiration_ml_s =
      0.00030f *
      (pot.cultivation.transpiration_factor < 0.0f ? 0.0f : pot.cultivation.transpiration_factor) *
      (pot.cultivation.pot_volume_l < 0.5f ? 0.5f : pot.cultivation.pot_volume_l) * vapor_deficit *
      air_temp_factor * soil_factor * soil_temp_factor;
  return transpiration_ml_s * 100.0f / air_moisture_capacity_g;
}

void DummyEnvironmentSimulator::advance(const control::SafeControlDecision& decision,
                                        float step_seconds) noexcept {
  if (!std::isfinite(step_seconds) || step_seconds <= 0.0f) {
    return;
  }

  const float command_heater = clamp(decision.heater, 0.0f, 1.0f);
  const float command_fan = clamp(decision.fan, 0.0f, 1.0f);
  const float command_humidifier = clamp(decision.humidifier, 0.0f, 1.0f);
  const float command_dehumidifier = clamp(decision.dehumidifier, 0.0f, 1.0f);
  const float command_cooler = clamp(decision.cooler, 0.0f, 1.0f);
  const float command_co2_doser = clamp(decision.co2_doser, 0.0f, 1.0f);
  const float command_nutrient_heater = clamp(decision.nutrient_heater, 0.0f, 1.0f);

  effective_heater_ = lag(effective_heater_, command_heater, step_seconds, kHeaterLagS);
  effective_nutrient_heater_ =
      lag(effective_nutrient_heater_, command_nutrient_heater, step_seconds, kHeaterLagS);
  effective_fan_ = lag(effective_fan_, command_fan, step_seconds, kFanLagS);
  effective_humidifier_ =
      lag(effective_humidifier_, command_humidifier, step_seconds, kHumidifierLagS);
  effective_dehumidifier_ =
      lag(effective_dehumidifier_, command_dehumidifier, step_seconds, kDehumidifierLagS);
  effective_cooler_ = lag(effective_cooler_, command_cooler, step_seconds, kCoolerLagS);

  const float volume = clamp(input_.environment.growbox_volume_m3, 0.05f, 100.0f);
  const float thermal_mass = clamp(input_.environment.thermal_mass_j_per_k, 500.0f, 10000000.0f);
  const float fan_airflow =
      effective_fan_ * clamp(input_.actuators.fan.max_airflow_m3_h, 0.0f, 10000.0f);
  const float exchange_ach =
      clamp(input_.environment.air_leak_rate_ach, 0.0f, 20.0f) + fan_airflow / volume;
  const float exchange_rate_s = exchange_ach / kSecondsPerHour;

  const float heater_w = effective_heater_ * input_.actuators.heater.max_power_w *
                         clamp(input_.actuators.heater.efficiency, 0.0f, 1.0f);
  const float cooler_w = effective_cooler_ * input_.actuators.cooler.max_cooling_w;
  const float lights_w = input_.lights_active ? kDefaultLightsHeatW : 0.0f;
  const float passive_heat_w =
      input_.environment.heat_loss_w_per_k *
      (input_.sensors.outside_temperature_c - input_.sensors.air_temperature_c);
  const float air_heat_capacity_j_k = volume * 1.225f * 1005.0f;
  const float exchange_heat_w =
      air_heat_capacity_j_k * exchange_rate_s *
      (input_.sensors.outside_temperature_c - input_.sensors.air_temperature_c);
  const float temperature_delta =
      (heater_w + lights_w - cooler_w + passive_heat_w + exchange_heat_w) * step_seconds /
      thermal_mass;

  const float air_moisture_capacity_g = volume * 20.0f < 1.0f ? 1.0f : volume * 20.0f;
  const float humidity_exchange_pp_s =
      exchange_rate_s * (input_.sensors.outside_humidity_pct - input_.sensors.air_humidity_pct);
  const float humidifier_pp_s = effective_humidifier_ * input_.actuators.humidifier.max_output_g_h /
                                kSecondsPerHour * 100.0f / air_moisture_capacity_g;
  const float dehumidifier_pp_s = -effective_dehumidifier_ *
                                  input_.actuators.dehumidifier.max_removal_g_h / kSecondsPerHour *
                                  100.0f / air_moisture_capacity_g;

  const float vapor_deficit = clamp((100.0f - input_.sensors.air_humidity_pct) / 60.0f, 0.1f, 1.5f);
  float evap_pp_s = 0.0f;
  for (std::size_t pot_index = 0U; pot_index < control::kMaxPots; ++pot_index) {
    evap_pp_s +=
        zoneEvaporationPctPerSecond(pot_index, vapor_deficit, input_.sensors.air_temperature_c);
  }

  const float nutrient_heater_w =
      input_.actuators.nutrient_heater.available
          ? effective_nutrient_heater_ * input_.actuators.nutrient_heater.max_power_w *
                clamp(input_.actuators.nutrient_heater.efficiency, 0.0f, 1.0f)
          : 0.0f;
  constexpr float kNutrientThermalMassJK = 84000.0f;
  constexpr float kNutrientLossWPerK = 3.5f;
  const float nutrient_loss_w =
      kNutrientLossWPerK *
      (input_.sensors.outside_temperature_c - input_.sensors.nutrient_solution_temperature_c);
  const float nutrient_temp_delta =
      (nutrient_heater_w + nutrient_loss_w) * step_seconds / kNutrientThermalMassJK;

  float irrigation_humidity_boost_pp = 0.0f;
  for (std::size_t pot_index = 0U; pot_index < control::kMaxPots; ++pot_index) {
    auto& pot = input_.pots[pot_index];
    if (!pot.available || !pot.irrigation.available) {
      continue;
    }
    const float irrigation_command = irrigationCommand(pot_index, decision);
    if (irrigation_command <= 0.0f || !irrigationReady(pot_index)) {
      continue;
    }

    const float pulse_s =
        clamp(decision.irrigation_pulse_s[pot_index], 0.0f, pot.irrigation.maximum_pulse_s);
    const float irrigation_ml = pot.irrigation.flow_ml_s * pulse_s;
    last_irrigation_s_[pot_index] = elapsed_s_;
    const float water_capacity = pot.cultivation.substrate_water_capacity_ml < 1.0f
                                     ? 1.0f
                                     : pot.cultivation.substrate_water_capacity_ml;
    pot.sensors.soil_moisture_pct = clamp(
        pot.sensors.soil_moisture_pct + irrigation_ml * 100.0f / water_capacity, 0.0f, 100.0f);
    if (pot.validity.soil_temperature && irrigation_ml > 0.0f) {
      const float mix_fraction = clamp(irrigation_ml / water_capacity, 0.0f, 0.35f);
      pot.sensors.soil_temperature_c +=
          (input_.sensors.nutrient_solution_temperature_c - pot.sensors.soil_temperature_c) *
          mix_fraction;
    }
    irrigation_humidity_boost_pp += irrigation_ml * 0.04f * 100.0f / air_moisture_capacity_g;
  }

  const float humidity_delta =
      (humidity_exchange_pp_s + humidifier_pp_s + dehumidifier_pp_s + evap_pp_s) * step_seconds +
      irrigation_humidity_boost_pp;

  const float outdoor_co2_ppm =
      input_.validity.outside_co2 ? input_.sensors.outside_co2_ppm : 420.0f;
  const float co2_exchange_ppm_s = exchange_rate_s * (outdoor_co2_ppm - input_.sensors.co2_ppm);
  float co2_dose_ppm = 0.0f;
  if (command_co2_doser > 0.0f && input_.actuators.co2_doser.available) {
    co2_dose_ppm = command_co2_doser * input_.actuators.co2_doser.dose_ppm_per_full_pulse;
  }
  const float biological_co2_ppm_s = 0.0020f * (850.0f - input_.sensors.co2_ppm);

  for (std::size_t pot_index = 0U; pot_index < control::kMaxPots; ++pot_index) {
    auto& pot = input_.pots[pot_index];
    if (!pot.available || !pot.validity.soil_moisture) {
      continue;
    }
    const float water_capacity = pot.cultivation.substrate_water_capacity_ml < 1.0f
                                     ? 1.0f
                                     : pot.cultivation.substrate_water_capacity_ml;
    const float drying_ml_s =
        0.00010f * (pot.cultivation.pot_volume_l < 0.5f ? 0.5f : pot.cultivation.pot_volume_l) *
        (pot.cultivation.transpiration_factor < 0.0f ? 0.0f
                                                     : pot.cultivation.transpiration_factor) *
        vapor_deficit;
    const float soil_loss_pp = drying_ml_s * step_seconds * 100.0f / water_capacity;
    pot.sensors.soil_moisture_pct =
        clamp(pot.sensors.soil_moisture_pct - soil_loss_pp, 0.0f, 100.0f);
  }

  for (std::size_t pot_index = 0U; pot_index < control::kMaxPots; ++pot_index) {
    auto& pot = input_.pots[pot_index];
    if (!pot.available || !pot.validity.soil_temperature) {
      continue;
    }
    const float heat_mat_command = heatMatCommand(pot_index, decision);
    const float heat_mat_w =
        pot.heat_mat.available ? heat_mat_command * pot.heat_mat.max_power_w : 0.0f;
    const float pot_volume =
        pot.cultivation.pot_volume_l < 0.5f ? 0.5f : pot.cultivation.pot_volume_l;
    const float soil_thermal_mass_j_k =
        pot_volume * 1800.0f < 2000.0f ? 2000.0f : pot_volume * 1800.0f;
    const float air_coupling_w =
        0.35f * (input_.sensors.air_temperature_c - pot.sensors.soil_temperature_c);
    const float soil_temp_delta =
        (heat_mat_w + air_coupling_w) * step_seconds / soil_thermal_mass_j_k;
    pot.sensors.soil_temperature_c =
        clamp(pot.sensors.soil_temperature_c + soil_temp_delta, -10.0f, 50.0f);
  }

  input_.sensors.nutrient_solution_temperature_c =
      clamp(input_.sensors.nutrient_solution_temperature_c + nutrient_temp_delta, 0.0f, 50.0f);
  input_.sensors.air_temperature_c += temperature_delta;
  input_.sensors.air_humidity_pct += humidity_delta;
  input_.sensors.co2_ppm +=
      (co2_exchange_ppm_s + biological_co2_ppm_s) * step_seconds + co2_dose_ppm;

  input_.sensors.air_temperature_c += uniformSigned() * 0.015f;
  input_.sensors.air_humidity_pct += uniformSigned() * 0.04f;
  input_.sensors.co2_ppm += uniformSigned() * 1.5f;
  for (std::size_t pot_index = 0U; pot_index < control::kMaxPots; ++pot_index) {
    if (input_.pots[pot_index].validity.soil_moisture) {
      input_.pots[pot_index].sensors.soil_moisture_pct += uniformSigned() * 0.015f;
    }
    if (input_.pots[pot_index].validity.soil_temperature) {
      input_.pots[pot_index].sensors.soil_temperature_c += uniformSigned() * 0.01f;
    }
  }
  if (input_.validity.nutrient_solution_temperature) {
    input_.sensors.nutrient_solution_temperature_c += uniformSigned() * 0.01f;
  }

  input_.sensors.air_temperature_c = clamp(input_.sensors.air_temperature_c, -30.0f, 70.0f);
  input_.sensors.air_humidity_pct = clamp(input_.sensors.air_humidity_pct, 0.0f, 100.0f);
  input_.sensors.co2_ppm = clamp(input_.sensors.co2_ppm, 250.0f, 5000.0f);
  for (std::size_t pot_index = 0U; pot_index < control::kMaxPots; ++pot_index) {
    input_.pots[pot_index].sensors.soil_moisture_pct =
        clamp(input_.pots[pot_index].sensors.soil_moisture_pct, 0.0f, 100.0f);
    if (input_.pots[pot_index].validity.soil_temperature) {
      input_.pots[pot_index].sensors.soil_temperature_c =
          clamp(input_.pots[pot_index].sensors.soil_temperature_c, -10.0f, 50.0f);
    }
  }
  if (input_.validity.nutrient_solution_temperature) {
    input_.sensors.nutrient_solution_temperature_c =
        clamp(input_.sensors.nutrient_solution_temperature_c, 0.0f, 50.0f);
  }

  input_.previous.heater = command_heater;
  input_.previous.fan = command_fan;
  input_.previous.humidifier = command_humidifier;
  input_.previous.dehumidifier = command_dehumidifier;
  input_.previous.cooler = command_cooler;
  input_.previous.co2_doser = command_co2_doser;
  input_.previous.nutrient_heater = command_nutrient_heater;
  for (std::size_t pot_index = 0U; pot_index < control::kMaxPots; ++pot_index) {
    input_.pots[pot_index].previous_irrigation = irrigationCommand(pot_index, decision);
    input_.pots[pot_index].previous_heat_mat = heatMatCommand(pot_index, decision);
  }

  elapsed_s_ += step_seconds;
  input_.monotonic_time_ms += static_cast<std::uint64_t>(step_seconds * 1000.0f);
}

} // namespace demo
} // namespace growbox
