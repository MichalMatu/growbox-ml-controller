#include "SafetySupervisor.h"

#include <algorithm>
#include <cmath>
#include <cstdint>

namespace growbox {
namespace control {
namespace {

constexpr std::size_t heaterIndex = schema::index(schema::OutputIndex::Heater);
constexpr std::size_t fanIndex = schema::index(schema::OutputIndex::Fan);
constexpr std::size_t humidifierIndex = schema::index(schema::OutputIndex::Humidifier);
constexpr std::size_t irrigationIndex = schema::index(schema::OutputIndex::Irrigation);

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

bool validSensorValue(float value, bool) noexcept {
  return std::isfinite(value);
}

bool safetyInputsFinite(const ControllerInput& input) noexcept {
  const bool sensors_finite =
      validSensorValue(input.sensors.air_temperature_c, input.validity.air_temperature) &&
      validSensorValue(input.sensors.air_humidity_pct, input.validity.air_humidity) &&
      validSensorValue(input.sensors.co2_ppm, input.validity.co2) &&
      validSensorValue(input.sensors.soil_moisture_pct, input.validity.soil_moisture) &&
      validSensorValue(input.sensors.outside_temperature_c, input.validity.outside_temperature) &&
      validSensorValue(input.sensors.outside_humidity_pct, input.validity.outside_humidity);
  const bool capabilities_finite =
      std::isfinite(input.actuators.heater.max_power_w) &&
      std::isfinite(input.actuators.heater.efficiency) &&
      std::isfinite(input.actuators.fan.max_airflow_m3_h) &&
      std::isfinite(input.actuators.fan.minimum_command) &&
      std::isfinite(input.actuators.humidifier.max_output_g_h) &&
      std::isfinite(input.actuators.irrigation_pump.flow_ml_s) &&
      std::isfinite(input.actuators.irrigation_pump.maximum_pulse_s) &&
      std::isfinite(input.actuators.irrigation_pump.minimum_interval_s);
  const bool safety_finite = std::isfinite(input.safety.maximum_air_temperature_c) &&
                             std::isfinite(input.safety.alarm_air_temperature_c) &&
                             std::isfinite(input.safety.alarm_minimum_fan) &&
                             std::isfinite(input.safety.binary_threshold) &&
                             std::isfinite(input.safety.heater_minimum_on_s) &&
                             std::isfinite(input.safety.heater_minimum_off_s) &&
                             std::isfinite(input.safety.humidifier_minimum_on_s) &&
                             std::isfinite(input.safety.humidifier_minimum_off_s);
  const bool environment_finite = std::isfinite(input.environment.growbox_volume_m3) &&
                                  std::isfinite(input.environment.thermal_mass_j_per_k) &&
                                  std::isfinite(input.environment.heat_loss_w_per_k) &&
                                  std::isfinite(input.environment.air_leak_rate_ach);
  const bool cultivation_finite = std::isfinite(input.cultivation.pot_volume_l) &&
                                  std::isfinite(input.cultivation.substrate_water_capacity_ml) &&
                                  std::isfinite(input.cultivation.transpiration_factor);
  const bool targets_finite = std::isfinite(input.targets.air_temperature_c) &&
                              std::isfinite(input.targets.air_humidity_pct) &&
                              std::isfinite(input.targets.co2_ppm) &&
                              std::isfinite(input.targets.soil_moisture_pct);
  const bool previous_finite =
      std::isfinite(input.previous.heater) && std::isfinite(input.previous.fan) &&
      std::isfinite(input.previous.humidifier) && std::isfinite(input.previous.irrigation);
  return sensors_finite && capabilities_finite && safety_finite && environment_finite &&
         cultivation_finite && targets_finite && previous_finite;
}

std::uint64_t durationMs(float seconds) noexcept {
  constexpr float kMaximumSeconds = 86400.0f;
  const float bounded = clampRange(seconds, 0.0f, kMaximumSeconds);
  return static_cast<std::uint64_t>(bounded * 1000.0f);
}

std::uint64_t elapsedMs(std::uint64_t now, std::uint64_t then) noexcept {
  return now >= then ? now - then : 0U;
}

template <typename BinaryRuntime>
void syncBinaryState(BinaryRuntime& runtime, bool on, std::uint64_t now) noexcept {
  if (!runtime.initialized) {
    runtime.initialized = true;
    runtime.has_transition = true;
    runtime.on = on;
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

void forceSafeState(const RawModelDecision& raw, SafetyReason reason, SafeControlDecision& safe,
                    SafetyReport& report) noexcept {
  safe = SafeControlDecision{};
  report = SafetyReport{};
  addReason(report, heaterIndex, reason);
  addReason(report, fanIndex, reason);
  addReason(report, humidifierIndex, reason);
  addReason(report, irrigationIndex, reason);
  report.modified = different(raw.heater, 0.0f) || different(raw.fan, 0.0f) ||
                    different(raw.humidifier, 0.0f) || different(raw.irrigation, 0.0f);
}

void applyEmergencyFan(const ControllerInput& input, const RawModelDecision& raw,
                       SafeControlDecision& safe, SafetyReport& report) noexcept {
  const bool configuration_finite = std::isfinite(input.safety.alarm_air_temperature_c) &&
                                    std::isfinite(input.safety.alarm_minimum_fan) &&
                                    std::isfinite(input.actuators.fan.minimum_command) &&
                                    std::isfinite(input.actuators.fan.max_airflow_m3_h);
  if (!configuration_finite || !input.validity.air_temperature ||
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

} // namespace

void SafetySupervisor::reset() noexcept {
  heater_ = BinaryRuntime{};
  humidifier_ = BinaryRuntime{};
  pump_ = PumpRuntime{};
}

void SafetySupervisor::apply(const ControllerInput& input, const RawModelDecision& raw,
                             SafetyReason upstream_failure, SafeControlDecision& safe,
                             SafetyReport& report) noexcept {
  if (!pump_.initialized) {
    pump_.initialized = true;
    if (std::isfinite(input.previous.irrigation) && input.previous.irrigation > 0.0f) {
      pump_.has_pulse = true;
      pump_.last_pulse_start_ms = input.monotonic_time_ms;
    }
  }

  if (upstream_failure != SafetyReason::None) {
    forceSafeState(raw, upstream_failure, safe, report);
    applyEmergencyFan(input, raw, safe, report);
    syncBinaryState(heater_, false, input.monotonic_time_ms);
    syncBinaryState(humidifier_, false, input.monotonic_time_ms);
    return;
  }

  if (!safetyInputsFinite(input)) {
    forceSafeState(raw, SafetyReason::NonFiniteInput, safe, report);
    applyEmergencyFan(input, raw, safe, report);
    syncBinaryState(heater_, false, input.monotonic_time_ms);
    syncBinaryState(humidifier_, false, input.monotonic_time_ms);
    return;
  }

  if (!std::isfinite(raw.heater) || !std::isfinite(raw.fan) || !std::isfinite(raw.humidifier) ||
      !std::isfinite(raw.irrigation)) {
    forceSafeState(raw, SafetyReason::NonFiniteModelOutput, safe, report);
    applyEmergencyFan(input, raw, safe, report);
    syncBinaryState(heater_, false, input.monotonic_time_ms);
    syncBinaryState(humidifier_, false, input.monotonic_time_ms);
    return;
  }

  report = SafetyReport{};
  safe = SafeControlDecision{};
  safe.heater = clamp01(raw.heater);
  safe.fan = clamp01(raw.fan);
  safe.humidifier = clamp01(raw.humidifier);
  safe.irrigation = clamp01(raw.irrigation);

  if (safe.heater != raw.heater) {
    addReason(report, heaterIndex, SafetyReason::OutputClamped);
  }
  if (safe.fan != raw.fan) {
    addReason(report, fanIndex, SafetyReason::OutputClamped);
  }
  if (safe.humidifier != raw.humidifier) {
    addReason(report, humidifierIndex, SafetyReason::OutputClamped);
  }
  if (safe.irrigation != raw.irrigation) {
    addReason(report, irrigationIndex, SafetyReason::OutputClamped);
    addReason(report, irrigationIndex, SafetyReason::PumpPulseLimited);
  }

  const float threshold = clamp01(input.safety.binary_threshold);
  if (input.actuators.heater.control_type == ActuatorControlType::Binary) {
    safe.heater = enforceBinary(safe.heater, input.previous.heater, threshold,
                                input.safety.heater_minimum_on_s, input.safety.heater_minimum_off_s,
                                input.monotonic_time_ms, heater_, report, heaterIndex);
  }
  safe.humidifier =
      enforceBinary(safe.humidifier, input.previous.humidifier, threshold,
                    input.safety.humidifier_minimum_on_s, input.safety.humidifier_minimum_off_s,
                    input.monotonic_time_ms, humidifier_, report, humidifierIndex);

  const bool heater_control_type_valid =
      input.actuators.heater.control_type == ActuatorControlType::Binary ||
      input.actuators.heater.control_type == ActuatorControlType::Pwm;
  const bool heater_capability_valid = input.actuators.heater.max_power_w > 0.0f &&
                                       input.actuators.heater.efficiency > 0.0f &&
                                       heater_control_type_valid;
  if (!input.actuators.heater.available || !heater_capability_valid) {
    if (safe.heater != 0.0f || raw.heater != 0.0f) {
      addReason(report, heaterIndex,
                input.actuators.heater.available ? SafetyReason::InvalidCapability
                                                 : SafetyReason::ActuatorUnavailable);
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

  const bool fan_capability_valid = input.actuators.fan.max_airflow_m3_h > 0.0f;
  if (!input.actuators.fan.available || !fan_capability_valid) {
    if (safe.fan != 0.0f || raw.fan != 0.0f) {
      addReason(report, fanIndex,
                input.actuators.fan.available ? SafetyReason::InvalidCapability
                                              : SafetyReason::ActuatorUnavailable);
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

  const bool humidifier_capability_valid = input.actuators.humidifier.max_output_g_h > 0.0f;
  if (!input.actuators.humidifier.available || !humidifier_capability_valid) {
    if (safe.humidifier != 0.0f || raw.humidifier != 0.0f) {
      addReason(report, humidifierIndex,
                input.actuators.humidifier.available ? SafetyReason::InvalidCapability
                                                     : SafetyReason::ActuatorUnavailable);
    }
    safe.humidifier = 0.0f;
  }

  const bool pump_capability_valid = input.actuators.irrigation_pump.flow_ml_s > 0.0f &&
                                     input.actuators.irrigation_pump.maximum_pulse_s > 0.0f;
  if (!input.actuators.irrigation_pump.available || !pump_capability_valid) {
    if (safe.irrigation != 0.0f || raw.irrigation != 0.0f) {
      addReason(report, irrigationIndex,
                input.actuators.irrigation_pump.available ? SafetyReason::InvalidCapability
                                                          : SafetyReason::ActuatorUnavailable);
    }
    safe.irrigation = 0.0f;
  } else if (safe.irrigation > 0.0f) {
    const float schema_maximum_pulse =
        schema::kFeatureMaximums[schema::index(schema::FeatureIndex::IrrigationMaximumPulseS)];
    const float maximum_pulse =
        clampRange(input.actuators.irrigation_pump.maximum_pulse_s, 0.0f, schema_maximum_pulse);
    if (maximum_pulse != input.actuators.irrigation_pump.maximum_pulse_s) {
      addReason(report, irrigationIndex, SafetyReason::PumpPulseLimited);
    }
    safe.irrigation_pulse_s = safe.irrigation * maximum_pulse;

    const float schema_maximum_interval =
        schema::kFeatureMaximums[schema::index(schema::FeatureIndex::IrrigationMinimumIntervalS)];
    const float interval_s = clampRange(input.actuators.irrigation_pump.minimum_interval_s, 0.0f,
                                        schema_maximum_interval);
    const std::uint64_t interval_ms = durationMs(interval_s);
    if (pump_.has_pulse &&
        elapsedMs(input.monotonic_time_ms, pump_.last_pulse_start_ms) < interval_ms) {
      safe.irrigation = 0.0f;
      safe.irrigation_pulse_s = 0.0f;
      addReason(report, irrigationIndex, SafetyReason::PumpMinimumInterval);
    } else {
      pump_.has_pulse = true;
      pump_.last_pulse_start_ms = input.monotonic_time_ms;
    }
  }

  syncBinaryState(heater_, safe.heater >= threshold, input.monotonic_time_ms);
  syncBinaryState(humidifier_, safe.humidifier >= threshold, input.monotonic_time_ms);

  report.modified = report.modified || different(raw.heater, safe.heater) ||
                    different(raw.fan, safe.fan) || different(raw.humidifier, safe.humidifier) ||
                    different(raw.irrigation, safe.irrigation) ||
                    ((report.reason_mask & reasonBit(SafetyReason::PumpPulseLimited)) != 0U);
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
  }
  return "unknown";
}

} // namespace control
} // namespace growbox
