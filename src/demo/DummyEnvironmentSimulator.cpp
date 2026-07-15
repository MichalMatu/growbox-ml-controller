#include "DummyEnvironmentSimulator.h"

#include <cmath>

namespace growbox {
namespace demo {

namespace {
constexpr float kSecondsPerHour = 3600.0f;
}

DummyEnvironmentSimulator::DummyEnvironmentSimulator() noexcept {
  reset();
}

void DummyEnvironmentSimulator::reset(std::uint32_t seed) noexcept {
  input_ = control::ControllerInput{};
  input_.sensors.air_temperature_c = 22.0f;
  input_.sensors.air_humidity_pct = 58.0f;
  input_.sensors.co2_ppm = 920.0f;
  input_.sensors.soil_moisture_pct = 44.0f;
  input_.sensors.outside_temperature_c = 18.0f;
  input_.sensors.outside_humidity_pct = 52.0f;
  input_.sensors.outside_co2_ppm = 420.0f;
  input_.validity.air_temperature = true;
  input_.validity.air_humidity = true;
  input_.validity.co2 = true;
  input_.validity.soil_moisture = true;
  input_.validity.outside_temperature = true;
  input_.validity.outside_humidity = true;
  input_.validity.outside_co2 = true;

  input_.environment.growbox_volume_m3 = 1.2f;
  input_.environment.thermal_mass_j_per_k = 48000.0f;
  input_.environment.heat_loss_w_per_k = 7.0f;
  input_.environment.air_leak_rate_ach = 0.25f;
  input_.cultivation.pot_volume_l = 12.0f;
  input_.cultivation.substrate_water_capacity_ml = 3600.0f;
  input_.cultivation.transpiration_factor = 1.0f;

  input_.actuators.heater.available = true;
  input_.actuators.heater.max_power_w = 180.0f;
  input_.actuators.heater.efficiency = 0.9f;
  input_.actuators.heater.control_type = control::ActuatorControlType::Binary;
  input_.actuators.fan.available = true;
  input_.actuators.fan.max_airflow_m3_h = 120.0f;
  input_.actuators.fan.minimum_command = 0.2f;
  input_.actuators.fan.control_type = control::ActuatorControlType::Pwm;
  input_.actuators.humidifier.available = true;
  input_.actuators.humidifier.max_output_g_h = 180.0f;
  input_.actuators.humidifier.control_type = control::ActuatorControlType::Binary;
  input_.actuators.irrigation_pump.available = true;
  input_.actuators.irrigation_pump.flow_ml_s = 22.0f;
  input_.actuators.irrigation_pump.maximum_pulse_s = 4.0f;
  input_.actuators.irrigation_pump.minimum_interval_s = 600.0f;
  input_.actuators.irrigation_pump.control_type = control::ActuatorControlType::Binary;

  input_.targets.air_temperature_c = 25.0f;
  input_.targets.air_humidity_pct = 65.0f;
  input_.targets.co2_ppm = 850.0f;
  input_.targets.soil_moisture_pct = 50.0f;
  input_.monotonic_time_ms = 0U;
  setSeed(seed);
  effective_heater_ = 0.0f;
  effective_fan_ = 0.0f;
  effective_humidifier_ = 0.0f;
}

void DummyEnvironmentSimulator::load(const control::ControllerInput& scenario,
                                     std::uint32_t seed) noexcept {
  input_ = scenario;
  input_.monotonic_time_ms = 0U;
  setSeed(seed);
  effective_heater_ = clamp(input_.previous.heater, 0.0f, 1.0f);
  effective_fan_ = clamp(input_.previous.fan, 0.0f, 1.0f);
  effective_humidifier_ = clamp(input_.previous.humidifier, 0.0f, 1.0f);
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
    const control::ActuatorCapabilities& actuators) noexcept {
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

void DummyEnvironmentSimulator::advance(const control::SafeControlDecision& decision,
                                        float step_seconds) noexcept {
  if (!std::isfinite(step_seconds) || step_seconds <= 0.0f) {
    return;
  }

  // First-order actuator response prevents instantaneous state changes.
  const float response = clamp(step_seconds / 30.0f, 0.0f, 1.0f);
  effective_heater_ += response * (clamp(decision.heater, 0.0f, 1.0f) - effective_heater_);
  effective_fan_ += response * (clamp(decision.fan, 0.0f, 1.0f) - effective_fan_);
  effective_humidifier_ +=
      response * (clamp(decision.humidifier, 0.0f, 1.0f) - effective_humidifier_);

  const float volume = clamp(input_.environment.growbox_volume_m3, 0.05f, 100.0f);
  const float thermal_mass = clamp(input_.environment.thermal_mass_j_per_k, 1000.0f, 10000000.0f);
  const float air_changes_per_hour =
      clamp(input_.environment.air_leak_rate_ach, 0.0f, 20.0f) +
      effective_fan_ * clamp(input_.actuators.fan.max_airflow_m3_h, 0.0f, 10000.0f) / volume;
  const float exchange_fraction =
      clamp(air_changes_per_hour * step_seconds / kSecondsPerHour, 0.0f, 0.85f);

  const float heater_w = effective_heater_ * input_.actuators.heater.max_power_w *
                         clamp(input_.actuators.heater.efficiency, 0.0f, 1.0f);
  const float heat_loss_w =
      input_.environment.heat_loss_w_per_k *
      (input_.sensors.air_temperature_c - input_.sensors.outside_temperature_c);
  input_.sensors.air_temperature_c += (heater_w - heat_loss_w) * step_seconds / thermal_mass;
  input_.sensors.air_temperature_c +=
      exchange_fraction * (input_.sensors.outside_temperature_c - input_.sensors.air_temperature_c);

  const float humidifier_gain = effective_humidifier_ * input_.actuators.humidifier.max_output_g_h *
                                step_seconds / kSecondsPerHour / volume * 0.55f;
  const float transpiration_gain = input_.cultivation.transpiration_factor * step_seconds / 300.0f;
  input_.sensors.air_humidity_pct += humidifier_gain + transpiration_gain;
  input_.sensors.air_humidity_pct +=
      exchange_fraction * (input_.sensors.outside_humidity_pct - input_.sensors.air_humidity_pct);

  input_.sensors.co2_ppm += 0.4f * input_.cultivation.transpiration_factor * step_seconds;
  const float outdoor_co2_ppm =
      input_.validity.outside_co2 ? input_.sensors.outside_co2_ppm : 420.0f;
  input_.sensors.co2_ppm += exchange_fraction * (outdoor_co2_ppm - input_.sensors.co2_ppm);

  const float capacity = clamp(input_.cultivation.substrate_water_capacity_ml, 10.0f, 100000.0f);
  const float pulse_seconds =
      clamp(decision.irrigation_pulse_s, 0.0f, input_.actuators.irrigation_pump.maximum_pulse_s);
  const float irrigation_ml = input_.actuators.irrigation_pump.flow_ml_s * pulse_seconds;
  const float soil_gain_pct = irrigation_ml / capacity * 100.0f;
  const float drying_pct =
      (0.004f + 0.003f * effective_fan_) * input_.cultivation.transpiration_factor * step_seconds;
  input_.sensors.soil_moisture_pct += soil_gain_pct - drying_pct;

  // Small deterministic sensor noise; the Python simulator is the training source of truth.
  input_.sensors.air_temperature_c += uniformSigned() * 0.015f;
  input_.sensors.air_humidity_pct += uniformSigned() * 0.04f;
  input_.sensors.co2_ppm += uniformSigned() * 1.5f;
  input_.sensors.soil_moisture_pct += uniformSigned() * 0.015f;

  input_.sensors.air_temperature_c = clamp(input_.sensors.air_temperature_c, -20.0f, 60.0f);
  input_.sensors.air_humidity_pct = clamp(input_.sensors.air_humidity_pct, 0.0f, 100.0f);
  input_.sensors.co2_ppm = clamp(input_.sensors.co2_ppm, 0.0f, 5000.0f);
  input_.sensors.soil_moisture_pct = clamp(input_.sensors.soil_moisture_pct, 0.0f, 100.0f);

  input_.previous.heater = clamp(decision.heater, 0.0f, 1.0f);
  input_.previous.fan = clamp(decision.fan, 0.0f, 1.0f);
  input_.previous.humidifier = clamp(decision.humidifier, 0.0f, 1.0f);
  input_.previous.irrigation = clamp(decision.irrigation, 0.0f, 1.0f);
  input_.monotonic_time_ms += static_cast<std::uint64_t>(step_seconds * 1000.0f);
}

} // namespace demo
} // namespace growbox
