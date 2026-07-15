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

constexpr std::array<schema::OutputIndex, kMaxZones> kIrrigationOutputs{
    schema::OutputIndex::IrrigationZone1, schema::OutputIndex::IrrigationZone2,
    schema::OutputIndex::IrrigationZone3, schema::OutputIndex::IrrigationZone4};

constexpr std::array<FeatureIndex, kMaxZones> kZoneMaxPulseFeatures{
    FeatureIndex::Zone1IrrigationMaximumPulseS, FeatureIndex::Zone2IrrigationMaximumPulseS,
    FeatureIndex::Zone3IrrigationMaximumPulseS, FeatureIndex::Zone4IrrigationMaximumPulseS};
constexpr std::array<FeatureIndex, kMaxZones> kZoneMaxIntervalFeatures{
    FeatureIndex::Zone1IrrigationMinimumIntervalS, FeatureIndex::Zone2IrrigationMinimumIntervalS,
    FeatureIndex::Zone3IrrigationMinimumIntervalS, FeatureIndex::Zone4IrrigationMinimumIntervalS};

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
                                   std::isfinite(actuators.co2_doser.maximum_pulse_s);
  for (const ZoneConfig& zone : input.zones) {
    if (!std::isfinite(zone.sensors.soil_moisture_pct) ||
        !std::isfinite(zone.sensors.soil_temperature_c) ||
        !std::isfinite(zone.cultivation.pot_volume_l) ||
        !std::isfinite(zone.cultivation.substrate_water_capacity_ml) ||
        !std::isfinite(zone.cultivation.transpiration_factor) ||
        !std::isfinite(zone.target_soil_moisture_pct) ||
        !std::isfinite(zone.irrigation.flow_ml_s) ||
        !std::isfinite(zone.irrigation.maximum_pulse_s) ||
        !std::isfinite(zone.irrigation.minimum_interval_s) ||
        !std::isfinite(zone.previous_irrigation)) {
      return false;
    }
  }
  const auto& safety = input.safety;
  const bool safety_finite = std::isfinite(safety.maximum_air_temperature_c) &&
                             std::isfinite(safety.alarm_air_temperature_c) &&
                             std::isfinite(safety.alarm_minimum_fan) &&
                             std::isfinite(safety.binary_threshold) &&
                             std::isfinite(safety.co2_doser_minimum_interval_s) &&
                             std::isfinite(safety.fan_venting_co2_threshold);
  const auto& environment = input.environment;
  const bool environment_finite = std::isfinite(environment.growbox_volume_m3) &&
                                  std::isfinite(environment.thermal_mass_j_per_k) &&
                                  std::isfinite(environment.heat_loss_w_per_k) &&
                                  std::isfinite(environment.air_leak_rate_ach);
  const auto& targets = input.targets;
  const bool targets_finite = std::isfinite(targets.air_temperature_c) &&
                              std::isfinite(targets.air_humidity_pct) &&
                              std::isfinite(targets.co2_ppm);
  const auto& previous = input.previous;
  const bool previous_finite = std::isfinite(previous.heater) && std::isfinite(previous.fan) &&
                               std::isfinite(previous.humidifier) &&
                               std::isfinite(previous.dehumidifier) &&
                               std::isfinite(previous.cooler) && std::isfinite(previous.co2_doser);
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

} // namespace

void SafetySupervisor::reset() noexcept {
  irrigation_binary_ = {};
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

  if (!input.actuators.co2_doser.available ||
      input.actuators.co2_doser.dose_ppm_per_full_pulse <= 0.0f) {
    applyBinaryActuatorSafety(input.actuators.co2_doser.available,
                              input.actuators.co2_doser.dose_ppm_per_full_pulse, safe.co2_doser,
                              raw.co2_doser, co2Index, report);
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

  const float threshold = clamp01(input.safety.binary_threshold);
  for (std::size_t zone_index = 0; zone_index < kMaxZones; ++zone_index) {
    const ZoneConfig& zone = input.zones[zone_index];
    const schema::OutputIndex output = kIrrigationOutputs[zone_index];
    const std::size_t output_index = schema::index(output);
    float& irrigation = safeOutputValue(safe, output);

    const bool capability_valid =
        zone.irrigation.flow_ml_s > 0.0f && zone.irrigation.maximum_pulse_s > 0.0f;
    if (!zone.available || !zone.irrigation.available || !capability_valid) {
      if (!zone.irrigation.available || !zone.available) {
        addReason(report, output_index, SafetyReason::ActuatorUnavailable);
      } else if (irrigation != 0.0f || rawOutputValue(raw, output) != 0.0f) {
        addReason(report, output_index, SafetyReason::InvalidCapability);
      }
      irrigation = 0.0f;
      safe.irrigation_pulse_s[zone_index] = 0.0f;
      continue;
    }

    if (zone.irrigation.control_type == ActuatorControlType::Binary) {
      const bool requested_on = irrigation >= threshold;
      const float thresholded = requested_on ? 1.0f : 0.0f;
      if (irrigation != thresholded) {
        addReason(report, output_index, SafetyReason::BinaryThreshold);
      }
      irrigation = thresholded;
    }

    if (irrigation > 0.0f) {
      const float schema_maximum_pulse =
          schema::kFeatureMaximums[schema::index(kZoneMaxPulseFeatures[zone_index])];
      const float maximum_pulse =
          clampRange(zone.irrigation.maximum_pulse_s, 0.0f, schema_maximum_pulse);
      if (maximum_pulse != zone.irrigation.maximum_pulse_s) {
        addReason(report, output_index, SafetyReason::PumpPulseLimited);
      }
      safe.irrigation_pulse_s[zone_index] = irrigation * maximum_pulse;

      PumpRuntime& pump = zone_pumps_[zone_index];
      if (!pump.initialized) {
        pump.initialized = true;
        if (zone.previous_irrigation > 0.0f) {
          pump.has_pulse = true;
          pump.last_pulse_start_ms = input.monotonic_time_ms;
        }
      }
      const float schema_maximum_interval =
          schema::kFeatureMaximums[schema::index(kZoneMaxIntervalFeatures[zone_index])];
      const float interval_s =
          clampRange(zone.irrigation.minimum_interval_s, 0.0f, schema_maximum_interval);
      const std::uint64_t interval_ms = durationMs(interval_s);
      if (pump.has_pulse &&
          elapsedMs(input.monotonic_time_ms, pump.last_pulse_start_ms) < interval_ms) {
        irrigation = 0.0f;
        safe.irrigation_pulse_s[zone_index] = 0.0f;
        addReason(report, output_index, SafetyReason::PumpMinimumInterval);
      } else {
        pump.has_pulse = true;
        pump.last_pulse_start_ms = input.monotonic_time_ms;
      }
    }
  }

  report.modified = report.modified || different(raw.heater, safe.heater) ||
                    different(raw.fan, safe.fan) || different(raw.humidifier, safe.humidifier) ||
                    different(raw.dehumidifier, safe.dehumidifier) ||
                    different(raw.cooler, safe.cooler) || different(raw.co2_doser, safe.co2_doser);
  for (std::size_t zone_index = 0; zone_index < kMaxZones; ++zone_index) {
    report.modified =
        report.modified || different(rawOutputValue(raw, kIrrigationOutputs[zone_index]),
                                     safeOutputValue(safe, kIrrigationOutputs[zone_index]));
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
  }
  return "unknown";
}

} // namespace control
} // namespace growbox
