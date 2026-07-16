#include "SafetySupervisor.h"

#include <algorithm>
#include <cmath>
#include <cstdint>

namespace growbox {
namespace control {
namespace {

using schema::FeatureIndex;

constexpr std::size_t heaterIndex = schema::index(schema::OutputIndex::Heater);
constexpr std::size_t fanIndex = schema::index(schema::OutputIndex::Fan);
constexpr std::size_t humidifierIndex = schema::index(schema::OutputIndex::Humidifier);
constexpr std::size_t dehumidifierIndex = schema::index(schema::OutputIndex::Dehumidifier);
constexpr std::size_t coolerIndex = schema::index(schema::OutputIndex::Cooler);
constexpr std::size_t co2Index = schema::index(schema::OutputIndex::Co2Doser);
constexpr std::size_t nutrientHeaterIndex = schema::index(schema::OutputIndex::NutrientHeater);

constexpr std::array<schema::OutputIndex, kMaxPots> kIrrigationOutputs{
    schema::OutputIndex::IrrigationPot1, schema::OutputIndex::IrrigationPot2,
    schema::OutputIndex::IrrigationPot3, schema::OutputIndex::IrrigationPot4};

constexpr std::array<schema::OutputIndex, kMaxPots> kHeatMatOutputs{
    schema::OutputIndex::HeatMatPot1, schema::OutputIndex::HeatMatPot2,
    schema::OutputIndex::HeatMatPot3, schema::OutputIndex::HeatMatPot4};

constexpr std::array<FeatureIndex, kMaxPots> kZoneMaxPulseFeatures{
    FeatureIndex::Pot1IrrigationMaximumPulseS, FeatureIndex::Pot2IrrigationMaximumPulseS,
    FeatureIndex::Pot3IrrigationMaximumPulseS, FeatureIndex::Pot4IrrigationMaximumPulseS};
constexpr std::array<FeatureIndex, kMaxPots> kZoneMaxIntervalFeatures{
    FeatureIndex::Pot1IrrigationMinimumIntervalS, FeatureIndex::Pot2IrrigationMinimumIntervalS,
    FeatureIndex::Pot3IrrigationMinimumIntervalS, FeatureIndex::Pot4IrrigationMinimumIntervalS};

float clamp01(float value) noexcept {
  return std::max(0.0f, std::min(1.0f, value));
}

float clampRange(float value, float minimum, float maximum) noexcept {
  return std::max(minimum, std::min(maximum, value));
}

bool different(float first, float second) noexcept {
  return !std::isfinite(first) || first != second;
}

void addReason(SafetyReport& report, std::size_t output_index, SafetyReason reason) noexcept {
  const std::uint32_t bit = reasonBit(reason);
  report.reason_mask |= bit;
  report.output_reason_masks[output_index] |= bit;
}

bool rawOutputsFinite(const RawModelDecision& raw) noexcept {
  for (std::size_t index = 0; index < schema::kOutputCount; ++index) {
    if (!std::isfinite(rawOutputValue(raw, static_cast<schema::OutputIndex>(index)))) {
      return false;
    }
  }
  return true;
}

bool safetyInputsFinite(const ControllerInput& input) noexcept {
  const auto& sensors = input.sensors;
  const auto& validity = input.validity;
  const bool sensors_finite =
      std::isfinite(sensors.air_temperature_c) && std::isfinite(sensors.air_humidity_pct) &&
      std::isfinite(sensors.co2_ppm) && std::isfinite(sensors.nutrient_solution_temperature_c) &&
      std::isfinite(sensors.outside_temperature_c) && std::isfinite(sensors.outside_humidity_pct) &&
      std::isfinite(sensors.outside_co2_ppm);
  (void)validity;
  const auto& actuators = input.actuators;
  const bool capabilities_finite = std::isfinite(actuators.heater.max_power_w) &&
                                   std::isfinite(actuators.heater.efficiency) &&
                                   std::isfinite(actuators.fan.max_airflow_m3_h) &&
                                   std::isfinite(actuators.fan.minimum_command) &&
                                   std::isfinite(actuators.humidifier.max_output_g_h) &&
                                   std::isfinite(actuators.dehumidifier.max_removal_g_h) &&
                                   std::isfinite(actuators.cooler.max_cooling_w) &&
                                   std::isfinite(actuators.co2_doser.dose_ppm_per_full_pulse) &&
                                   std::isfinite(actuators.co2_doser.maximum_pulse_s) &&
                                   std::isfinite(actuators.nutrient_heater.max_power_w) &&
                                   std::isfinite(actuators.nutrient_heater.efficiency);
  for (const PotConfig& pot : input.pots) {
    if (!std::isfinite(pot.sensors.soil_moisture_pct) ||
        !std::isfinite(pot.sensors.soil_temperature_c) ||
        !std::isfinite(pot.cultivation.pot_volume_l) ||
        !std::isfinite(pot.cultivation.substrate_water_capacity_ml) ||
        !std::isfinite(pot.cultivation.transpiration_factor) ||
        !std::isfinite(pot.target_soil_moisture_pct) ||
        !std::isfinite(pot.target_soil_temperature_c) || !std::isfinite(pot.irrigation.flow_ml_s) ||
        !std::isfinite(pot.irrigation.maximum_pulse_s) ||
        !std::isfinite(pot.irrigation.minimum_interval_s) ||
        !std::isfinite(pot.heat_mat.max_power_w) || !std::isfinite(pot.previous_irrigation) ||
        !std::isfinite(pot.previous_heat_mat)) {
      return false;
    }
  }
  const auto& safety = input.safety;
  const bool safety_finite = std::isfinite(safety.maximum_air_temperature_c) &&
                             std::isfinite(safety.alarm_air_temperature_c) &&
                             std::isfinite(safety.alarm_minimum_fan) &&
                             std::isfinite(safety.binary_threshold) &&
                             std::isfinite(safety.co2_doser_minimum_interval_s) &&
                             std::isfinite(safety.fan_venting_co2_threshold) &&
                             std::isfinite(safety.maximum_nutrient_soil_delta_c) &&
                             std::isfinite(safety.minimum_nutrient_solution_temperature_c);
  const auto& environment = input.environment;
  const bool environment_finite = std::isfinite(environment.growbox_volume_m3) &&
                                  std::isfinite(environment.thermal_mass_j_per_k) &&
                                  std::isfinite(environment.heat_loss_w_per_k) &&
                                  std::isfinite(environment.air_leak_rate_ach);
  const auto& targets = input.targets;
  const bool targets_finite =
      std::isfinite(targets.air_temperature_c) && std::isfinite(targets.air_humidity_pct) &&
      std::isfinite(targets.co2_ppm) && std::isfinite(targets.nutrient_solution_temperature_c);
  const auto& previous = input.previous;
  const bool previous_finite =
      std::isfinite(previous.heater) && std::isfinite(previous.fan) &&
      std::isfinite(previous.humidifier) && std::isfinite(previous.dehumidifier) &&
      std::isfinite(previous.cooler) && std::isfinite(previous.co2_doser) &&
      std::isfinite(previous.nutrient_heater);
  return sensors_finite && capabilities_finite && safety_finite && environment_finite &&
         targets_finite && previous_finite;
}

std::uint64_t durationMs(float seconds) noexcept {
  constexpr float kMaximumSeconds = 86400.0f;
  const float bounded = clampRange(seconds, 0.0f, kMaximumSeconds);
  return static_cast<std::uint64_t>(bounded * 1000.0f);
}

std::uint64_t elapsedMs(std::uint64_t now, std::uint64_t then) noexcept {
  return now >= then ? now - then : 0U;
}

void forceSafeState(const RawModelDecision& raw, SafetyReason reason, SafeControlDecision& safe,
                    SafetyReport& report) noexcept {
  safe = SafeControlDecision{};
  report = SafetyReport{};
  for (std::size_t index = 0; index < schema::kOutputCount; ++index) {
    addReason(report, index, reason);
  }
  for (std::size_t index = 0; index < schema::kOutputCount; ++index) {
    if (different(rawOutputValue(raw, static_cast<schema::OutputIndex>(index)), 0.0f)) {
      report.modified = true;
      break;
    }
  }
}

void applyEmergencyFan(const ControllerInput& input, const RawModelDecision& raw,
                       SafeControlDecision& safe, SafetyReport& report) noexcept {
  if (!std::isfinite(input.safety.alarm_air_temperature_c) ||
      !std::isfinite(input.safety.alarm_minimum_fan) ||
      !std::isfinite(input.actuators.fan.minimum_command) ||
      !std::isfinite(input.actuators.fan.max_airflow_m3_h) || !input.validity.air_temperature ||
      !std::isfinite(input.sensors.air_temperature_c) || !input.actuators.fan.available ||
      input.actuators.fan.max_airflow_m3_h <= 0.0f ||
      input.sensors.air_temperature_c < input.safety.alarm_air_temperature_c) {
    return;
  }

  const float alarm_minimum = std::max(clamp01(input.safety.alarm_minimum_fan),
                                       clamp01(input.actuators.fan.minimum_command));
  if (safe.fan < alarm_minimum) {
    safe.fan = alarm_minimum;
    addReason(report, fanIndex, SafetyReason::TemperatureAlarmFan);
    report.modified = report.modified || different(raw.fan, safe.fan);
  }
}

void applyHeaterSafety(const ControllerInput& input, const RawModelDecision& raw,
                       SafeControlDecision& safe, SafetyReport& report) noexcept {
  const bool capability_valid =
      input.actuators.heater.max_power_w > 0.0f && input.actuators.heater.efficiency > 0.0f;
  if (!input.actuators.heater.available || !capability_valid) {
    if (!input.actuators.heater.available) {
      addReason(report, heaterIndex, SafetyReason::ActuatorUnavailable);
    } else if (safe.heater != 0.0f || raw.heater != 0.0f) {
      addReason(report, heaterIndex, SafetyReason::InvalidCapability);
    }
    safe.heater = 0.0f;
  }
  if (!input.validity.air_temperature) {
    addReason(report, heaterIndex, SafetyReason::TemperatureUnavailable);
    safe.heater = 0.0f;
  } else if (input.sensors.air_temperature_c >= input.safety.maximum_air_temperature_c) {
    addReason(report, heaterIndex, SafetyReason::OverTemperature);
    safe.heater = 0.0f;
  }
}

void applyFanSafety(const ControllerInput& input, const RawModelDecision& raw,
                    SafeControlDecision& safe, SafetyReport& report) noexcept {
  const bool capability_valid = input.actuators.fan.max_airflow_m3_h > 0.0f;
  if (!input.actuators.fan.available || !capability_valid) {
    if (!input.actuators.fan.available) {
      addReason(report, fanIndex, SafetyReason::ActuatorUnavailable);
    } else if (safe.fan != 0.0f || raw.fan != 0.0f) {
      addReason(report, fanIndex, SafetyReason::InvalidCapability);
    }
    safe.fan = 0.0f;
  } else if (input.validity.air_temperature &&
             input.sensors.air_temperature_c >= input.safety.alarm_air_temperature_c) {
    const float alarm_minimum = std::max(clamp01(input.safety.alarm_minimum_fan),
                                         clamp01(input.actuators.fan.minimum_command));
    if (safe.fan < alarm_minimum) {
      safe.fan = alarm_minimum;
      addReason(report, fanIndex, SafetyReason::TemperatureAlarmFan);
    }
  }
}

void applyBinaryActuatorSafety(bool available, float capability, float& safe_value, float raw_value,
                               std::size_t output_index, SafetyReport& report) noexcept {
  if (!available || capability <= 0.0f) {
    if (!available) {
      addReason(report, output_index, SafetyReason::ActuatorUnavailable);
    } else if (safe_value != 0.0f || raw_value != 0.0f) {
      addReason(report, output_index, SafetyReason::InvalidCapability);
    }
    safe_value = 0.0f;
  }
}

template <typename BinaryRuntime>
void syncBinaryState(BinaryRuntime& runtime, bool on, std::uint64_t now) noexcept {
  if (!runtime.initialized) {
    runtime.initialized = true;
    runtime.on = on;
    runtime.has_transition = true;
    runtime.last_transition_ms = now;
    return;
  }
  if (runtime.on != on) {
    runtime.on = on;
    runtime.has_transition = true;
    runtime.last_transition_ms = now;
  }
}

template <typename BinaryRuntime>
float enforceBinary(float desired, float previous, float threshold, float minimum_on_s,
                    float minimum_off_s, std::uint64_t now, BinaryRuntime& runtime,
                    SafetyReport& report, std::size_t output_index) noexcept {
  const bool requested_on = desired >= threshold;
  const float thresholded = requested_on ? 1.0f : 0.0f;
  if (desired != thresholded) {
    addReason(report, output_index, SafetyReason::BinaryThreshold);
  }

  if (!runtime.initialized) {
    runtime.initialized = true;
    runtime.has_transition = true;
    runtime.on = previous >= threshold;
    runtime.last_transition_ms = now;
  }

  if (runtime.on == requested_on) {
    return runtime.on ? 1.0f : 0.0f;
  }

  if (runtime.has_transition) {
    const std::uint64_t required = durationMs(runtime.on ? minimum_on_s : minimum_off_s);
    if (elapsedMs(now, runtime.last_transition_ms) < required) {
      addReason(report, output_index,
                runtime.on ? SafetyReason::BinaryMinimumOn : SafetyReason::BinaryMinimumOff);
      return runtime.on ? 1.0f : 0.0f;
    }
  }

  runtime.on = requested_on;
  runtime.has_transition = true;
  runtime.last_transition_ms = now;
  return requested_on ? 1.0f : 0.0f;
}

void applyHumidityDependentSafety(const ControllerInput& input, SafeControlDecision& safe,
                                  SafetyReport& report) noexcept {
  if (input.validity.air_humidity) {
    return;
  }
  if (safe.humidifier != 0.0f) {
    addReason(report, humidifierIndex, SafetyReason::HumidityUnavailable);
    safe.humidifier = 0.0f;
  }
  if (safe.dehumidifier != 0.0f) {
    addReason(report, dehumidifierIndex, SafetyReason::HumidityUnavailable);
    safe.dehumidifier = 0.0f;
  }
}

void applyHeaterCoolerExclusion(const ControllerInput& input, const RawModelDecision& raw,
                                SafeControlDecision& safe, SafetyReport& report) noexcept {
  const float threshold = clamp01(input.safety.binary_threshold);
  if (safe.heater >= threshold && safe.cooler > 0.0f) {
    addReason(report, coolerIndex, SafetyReason::ActuatorConflict);
    safe.cooler = 0.0f;
    report.modified = report.modified || different(raw.cooler, safe.cooler);
  }
  if (safe.cooler >= threshold && safe.heater > 0.0f) {
    addReason(report, heaterIndex, SafetyReason::ActuatorConflict);
    safe.heater = 0.0f;
    report.modified = report.modified || different(raw.heater, safe.heater);
  }
}

void applyHumidityControlExclusion(const ControllerInput& input, const RawModelDecision& raw,
                                   SafeControlDecision& safe, SafetyReport& report) noexcept {
  const float threshold = clamp01(input.safety.binary_threshold);
  if (safe.humidifier >= threshold && safe.dehumidifier > 0.0f) {
    addReason(report, dehumidifierIndex, SafetyReason::ActuatorConflict);
    safe.dehumidifier = 0.0f;
    report.modified = report.modified || different(raw.dehumidifier, safe.dehumidifier);
  }
  if (safe.dehumidifier >= threshold && safe.humidifier > 0.0f) {
    addReason(report, humidifierIndex, SafetyReason::ActuatorConflict);
    safe.humidifier = 0.0f;
    report.modified = report.modified || different(raw.humidifier, safe.humidifier);
  }
}

bool nutrientSolutionTooCold(const ControllerInput& input) noexcept {
  return input.validity.nutrient_solution_temperature &&
         std::isfinite(input.sensors.nutrient_solution_temperature_c) &&
         input.sensors.nutrient_solution_temperature_c <
             input.safety.minimum_nutrient_solution_temperature_c;
}

bool nutrientSoilDeltaExceeded(const ControllerInput& input, const PotConfig& pot) noexcept {
  if (!input.validity.nutrient_solution_temperature || !pot.validity.soil_temperature) {
    return false;
  }
  if (!std::isfinite(input.sensors.nutrient_solution_temperature_c) ||
      !std::isfinite(pot.sensors.soil_temperature_c)) {
    return false;
  }
  const float delta =
      input.sensors.nutrient_solution_temperature_c - pot.sensors.soil_temperature_c;
  return delta < -input.safety.maximum_nutrient_soil_delta_c ||
         delta > input.safety.maximum_nutrient_soil_delta_c;
}

} // namespace

void SafetySupervisor::reset() noexcept {
  heater_ = {};
  nutrient_heater_ = {};
  humidifier_ = {};
  dehumidifier_ = {};
  cooler_ = {};
  irrigation_binary_ = {};
  heat_mat_binary_ = {};
  zone_pumps_ = {};
  co2_doser_ = {};
}

void SafetySupervisor::apply(const ControllerInput& input, const RawModelDecision& raw,
                             SafetyReason upstream_failure, SafeControlDecision& safe,
                             SafetyReport& report) noexcept {
  if (upstream_failure != SafetyReason::None) {
    forceSafeState(raw, upstream_failure, safe, report);
    applyEmergencyFan(input, raw, safe, report);
    return;
  }

  if (!safetyInputsFinite(input)) {
    forceSafeState(raw, SafetyReason::NonFiniteInput, safe, report);
    applyEmergencyFan(input, raw, safe, report);
    return;
  }

  if (!rawOutputsFinite(raw)) {
    forceSafeState(raw, SafetyReason::NonFiniteModelOutput, safe, report);
    applyEmergencyFan(input, raw, safe, report);
    return;
  }

  report = SafetyReport{};
  safe = SafeControlDecision{};
  for (std::size_t index = 0; index < schema::kOutputCount; ++index) {
    const schema::OutputIndex output = static_cast<schema::OutputIndex>(index);
    const float clamped = clamp01(rawOutputValue(raw, output));
    safeOutputValue(safe, output) = clamped;
    if (clamped != rawOutputValue(raw, output)) {
      addReason(report, index, SafetyReason::OutputClamped);
    }
  }

  applyHeaterSafety(input, raw, safe, report);
  applyFanSafety(input, raw, safe, report);
  applyBinaryActuatorSafety(input.actuators.humidifier.available,
                            input.actuators.humidifier.max_output_g_h, safe.humidifier,
                            raw.humidifier, humidifierIndex, report);
  applyBinaryActuatorSafety(input.actuators.dehumidifier.available,
                            input.actuators.dehumidifier.max_removal_g_h, safe.dehumidifier,
                            raw.dehumidifier, dehumidifierIndex, report);
  applyBinaryActuatorSafety(input.actuators.cooler.available, input.actuators.cooler.max_cooling_w,
                            safe.cooler, raw.cooler, coolerIndex, report);
  applyHumidityDependentSafety(input, safe, report);

  const float threshold = clamp01(input.safety.binary_threshold);
  safe.heater = enforceBinary(safe.heater, input.previous.heater, threshold,
                              input.safety.heater_minimum_on_s, input.safety.heater_minimum_off_s,
                              input.monotonic_time_ms, heater_, report, heaterIndex);
  safe.humidifier =
      enforceBinary(safe.humidifier, input.previous.humidifier, threshold,
                    input.safety.humidifier_minimum_on_s, input.safety.humidifier_minimum_off_s,
                    input.monotonic_time_ms, humidifier_, report, humidifierIndex);
  safe.dehumidifier =
      enforceBinary(safe.dehumidifier, input.previous.dehumidifier, threshold,
                    input.safety.dehumidifier_minimum_on_s, input.safety.dehumidifier_minimum_off_s,
                    input.monotonic_time_ms, dehumidifier_, report, dehumidifierIndex);
  safe.cooler = enforceBinary(safe.cooler, input.previous.cooler, threshold,
                              input.safety.cooler_minimum_on_s, input.safety.cooler_minimum_off_s,
                              input.monotonic_time_ms, cooler_, report, coolerIndex);

  applyHeaterCoolerExclusion(input, raw, safe, report);
  applyHumidityControlExclusion(input, raw, safe, report);

  if (!input.actuators.co2_doser.available ||
      input.actuators.co2_doser.dose_ppm_per_full_pulse <= 0.0f) {
    applyBinaryActuatorSafety(input.actuators.co2_doser.available,
                              input.actuators.co2_doser.dose_ppm_per_full_pulse, safe.co2_doser,
                              raw.co2_doser, co2Index, report);
  } else if (!input.validity.co2) {
    if (safe.co2_doser > 0.0f || raw.co2_doser > 0.0f) {
      addReason(report, co2Index, SafetyReason::Co2SensorUnavailable);
    }
    safe.co2_doser = 0.0f;
  } else if (std::isfinite(input.sensors.co2_ppm) && std::isfinite(input.targets.co2_ppm) &&
             input.sensors.co2_ppm >= input.targets.co2_ppm) {
    if (safe.co2_doser > 0.0f || raw.co2_doser > 0.0f) {
      addReason(report, co2Index, SafetyReason::Co2TargetReached);
    }
    safe.co2_doser = 0.0f;
  } else if (safe.fan > clamp01(input.safety.fan_venting_co2_threshold)) {
    if (safe.co2_doser > 0.0f || raw.co2_doser > 0.0f) {
      addReason(report, co2Index, SafetyReason::Co2VentingFan);
    }
    safe.co2_doser = 0.0f;
  } else if (safe.co2_doser > 0.0f) {
    const std::uint64_t interval_ms = durationMs(input.safety.co2_doser_minimum_interval_s);
    if (co2_doser_.has_pulse &&
        elapsedMs(input.monotonic_time_ms, co2_doser_.last_pulse_start_ms) < interval_ms) {
      safe.co2_doser = 0.0f;
      addReason(report, co2Index, SafetyReason::PumpMinimumInterval);
    } else {
      co2_doser_.initialized = true;
      co2_doser_.has_pulse = true;
      co2_doser_.last_pulse_start_ms = input.monotonic_time_ms;
    }
  }

  const float nutrient_heater_capability =
      input.actuators.nutrient_heater.max_power_w * input.actuators.nutrient_heater.efficiency;
  applyBinaryActuatorSafety(input.actuators.nutrient_heater.available, nutrient_heater_capability,
                            safe.nutrient_heater, raw.nutrient_heater, nutrientHeaterIndex, report);
  if (!input.validity.nutrient_solution_temperature) {
    if (safe.nutrient_heater != 0.0f || raw.nutrient_heater != 0.0f) {
      addReason(report, nutrientHeaterIndex, SafetyReason::TemperatureUnavailable);
    }
    safe.nutrient_heater = 0.0f;
  }
  safe.nutrient_heater =
      enforceBinary(safe.nutrient_heater, input.previous.nutrient_heater, threshold,
                    input.safety.heater_minimum_on_s, input.safety.heater_minimum_off_s,
                    input.monotonic_time_ms, nutrient_heater_, report, nutrientHeaterIndex);

  const bool nutrient_cold = nutrientSolutionTooCold(input);
  for (std::size_t pot_index = 0; pot_index < kMaxPots; ++pot_index) {
    const PotConfig& pot = input.pots[pot_index];
    const schema::OutputIndex output = kIrrigationOutputs[pot_index];
    const std::size_t output_index = schema::index(output);
    float& irrigation = safeOutputValue(safe, output);

    const bool capability_valid =
        pot.irrigation.flow_ml_s > 0.0f && pot.irrigation.maximum_pulse_s > 0.0f;
    if (!pot.available || !pot.irrigation.available || !capability_valid) {
      if (!pot.irrigation.available || !pot.available) {
        addReason(report, output_index, SafetyReason::ActuatorUnavailable);
      } else if (irrigation != 0.0f || rawOutputValue(raw, output) != 0.0f) {
        addReason(report, output_index, SafetyReason::InvalidCapability);
      }
      irrigation = 0.0f;
      safe.irrigation_pulse_s[pot_index] = 0.0f;
      continue;
    }

    if (!pot.validity.soil_moisture) {
      if (irrigation > 0.0f || rawOutputValue(raw, output) > 0.0f) {
        addReason(report, output_index, SafetyReason::SoilMoistureUnavailable);
      }
      irrigation = 0.0f;
      safe.irrigation_pulse_s[pot_index] = 0.0f;
      continue;
    }

    if (pot.validity.soil_moisture && std::isfinite(pot.sensors.soil_moisture_pct) &&
        std::isfinite(pot.target_soil_moisture_pct) &&
        pot.sensors.soil_moisture_pct >= pot.target_soil_moisture_pct) {
      if (irrigation > 0.0f || rawOutputValue(raw, output) > 0.0f) {
        addReason(report, output_index, SafetyReason::SoilMoistureSatisfied);
      }
      irrigation = 0.0f;
      safe.irrigation_pulse_s[pot_index] = 0.0f;
      continue;
    }

    if (nutrient_cold) {
      if (irrigation > 0.0f || rawOutputValue(raw, output) > 0.0f) {
        addReason(report, output_index, SafetyReason::NutrientSolutionTooCold);
      }
      irrigation = 0.0f;
      safe.irrigation_pulse_s[pot_index] = 0.0f;
      continue;
    }

    if (nutrientSoilDeltaExceeded(input, pot)) {
      if (irrigation > 0.0f || rawOutputValue(raw, output) > 0.0f) {
        addReason(report, output_index, SafetyReason::NutrientSoilDeltaExceeded);
      }
      irrigation = 0.0f;
      safe.irrigation_pulse_s[pot_index] = 0.0f;
      continue;
    }

    if (pot.irrigation.control_type == ActuatorControlType::Binary) {
      const bool requested_on = irrigation >= threshold;
      const float thresholded = requested_on ? 1.0f : 0.0f;
      if (irrigation != thresholded) {
        addReason(report, output_index, SafetyReason::BinaryThreshold);
      }
      irrigation = thresholded;
    }

    if (irrigation > 0.0f) {
      const float schema_maximum_pulse =
          schema::kFeatureMaximums[schema::index(kZoneMaxPulseFeatures[pot_index])];
      const float maximum_pulse =
          clampRange(pot.irrigation.maximum_pulse_s, 0.0f, schema_maximum_pulse);
      if (maximum_pulse != pot.irrigation.maximum_pulse_s) {
        addReason(report, output_index, SafetyReason::PumpPulseLimited);
      }
      safe.irrigation_pulse_s[pot_index] = irrigation * maximum_pulse;

      PumpRuntime& pump = zone_pumps_[pot_index];
      if (!pump.initialized) {
        pump.initialized = true;
        if (pot.previous_irrigation > 0.0f) {
          pump.has_pulse = true;
          pump.last_pulse_start_ms = input.monotonic_time_ms;
        }
      }
      const float schema_maximum_interval =
          schema::kFeatureMaximums[schema::index(kZoneMaxIntervalFeatures[pot_index])];
      const float interval_s =
          clampRange(pot.irrigation.minimum_interval_s, 0.0f, schema_maximum_interval);
      const std::uint64_t interval_ms = durationMs(interval_s);
      if (pump.has_pulse &&
          elapsedMs(input.monotonic_time_ms, pump.last_pulse_start_ms) < interval_ms) {
        irrigation = 0.0f;
        safe.irrigation_pulse_s[pot_index] = 0.0f;
        addReason(report, output_index, SafetyReason::PumpMinimumInterval);
      } else {
        pump.has_pulse = true;
        pump.last_pulse_start_ms = input.monotonic_time_ms;
      }
    }
  }

  for (std::size_t pot_index = 0; pot_index < kMaxPots; ++pot_index) {
    const PotConfig& pot = input.pots[pot_index];
    const schema::OutputIndex output = kHeatMatOutputs[pot_index];
    const std::size_t output_index = schema::index(output);
    float& heat_mat = safeOutputValue(safe, output);

    applyBinaryActuatorSafety(pot.available && pot.heat_mat.available, pot.heat_mat.max_power_w,
                              heat_mat, rawOutputValue(raw, output), output_index, report);
    if (!pot.validity.soil_temperature) {
      if (heat_mat != 0.0f || rawOutputValue(raw, output) != 0.0f) {
        addReason(report, output_index, SafetyReason::TemperatureUnavailable);
      }
      heat_mat = 0.0f;
      continue;
    }

    if (pot.heat_mat.control_type == ActuatorControlType::Binary) {
      heat_mat =
          enforceBinary(heat_mat, pot.previous_heat_mat, threshold,
                        input.safety.heater_minimum_on_s, input.safety.heater_minimum_off_s,
                        input.monotonic_time_ms, heat_mat_binary_[pot_index], report, output_index);
    }
  }

  report.modified = report.modified || different(raw.heater, safe.heater) ||
                    different(raw.fan, safe.fan) || different(raw.humidifier, safe.humidifier) ||
                    different(raw.dehumidifier, safe.dehumidifier) ||
                    different(raw.cooler, safe.cooler) ||
                    different(raw.co2_doser, safe.co2_doser) ||
                    different(raw.nutrient_heater, safe.nutrient_heater);
  for (std::size_t pot_index = 0; pot_index < kMaxPots; ++pot_index) {
    report.modified =
        report.modified || different(rawOutputValue(raw, kIrrigationOutputs[pot_index]),
                                     safeOutputValue(safe, kIrrigationOutputs[pot_index]));
    report.modified =
        report.modified || different(rawOutputValue(raw, kHeatMatOutputs[pot_index]),
                                     safeOutputValue(safe, kHeatMatOutputs[pot_index]));
  }
}

const char* SafetySupervisor::reasonCode(SafetyReason reason) noexcept {
  switch (reason) {
  case SafetyReason::None:
    return "none";
  case SafetyReason::NonFiniteInput:
    return "non_finite_input";
  case SafetyReason::ModelFailure:
    return "model_failure";
  case SafetyReason::SchemaMismatch:
    return "schema_mismatch";
  case SafetyReason::NonFiniteModelOutput:
    return "non_finite_model_output";
  case SafetyReason::OutputClamped:
    return "output_clamped";
  case SafetyReason::TemperatureUnavailable:
    return "temperature_unavailable";
  case SafetyReason::ActuatorUnavailable:
    return "actuator_unavailable";
  case SafetyReason::OverTemperature:
    return "over_temperature";
  case SafetyReason::TemperatureAlarmFan:
    return "temperature_alarm_fan";
  case SafetyReason::PumpPulseLimited:
    return "pump_pulse_limited";
  case SafetyReason::PumpMinimumInterval:
    return "pump_minimum_interval";
  case SafetyReason::BinaryThreshold:
    return "binary_threshold";
  case SafetyReason::BinaryMinimumOn:
    return "binary_minimum_on";
  case SafetyReason::BinaryMinimumOff:
    return "binary_minimum_off";
  case SafetyReason::InvalidCapability:
    return "invalid_capability";
  case SafetyReason::Co2VentingFan:
    return "co2_venting_fan";
  case SafetyReason::SoilMoistureSatisfied:
    return "soil_moisture_satisfied";
  case SafetyReason::SoilMoistureUnavailable:
    return "soil_moisture_unavailable";
  case SafetyReason::NutrientSoilDeltaExceeded:
    return "nutrient_soil_delta_exceeded";
  case SafetyReason::NutrientSolutionTooCold:
    return "nutrient_solution_too_cold";
  case SafetyReason::Co2TargetReached:
    return "co2_target_reached";
  case SafetyReason::Co2SensorUnavailable:
    return "co2_sensor_unavailable";
  case SafetyReason::HumidityUnavailable:
    return "humidity_unavailable";
  case SafetyReason::ActuatorConflict:
    return "actuator_conflict";
  }
  return "unknown";
}

} // namespace control
} // namespace growbox
