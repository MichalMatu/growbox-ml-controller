#pragma once

#include "EnvironmentSchema.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace growbox {
namespace control {

static_assert(schema::kFeatureCount <= 64U, "Encoder diagnostics use a 64-bit feature mask");
static_assert(schema::kOutputCount == 4U,
              "Environment decision structures implement four schema outputs");

namespace detail {

constexpr float schemaDefault(schema::FeatureIndex feature) noexcept {
  return schema::kFeatureDefaults[schema::index(feature)];
}

constexpr bool schemaDefaultBool(schema::FeatureIndex feature) noexcept {
  return schemaDefault(feature) != 0.0f;
}

} // namespace detail

enum class ActuatorControlType : std::uint8_t {
  Binary = schema::kHeaterControlTypeBinary,
  Pwm = schema::kHeaterControlTypePwm,
};

struct SensorState {
  float air_temperature_c = detail::schemaDefault(schema::FeatureIndex::AirTemperatureC);
  float air_humidity_pct = detail::schemaDefault(schema::FeatureIndex::AirHumidityPct);
  float co2_ppm = detail::schemaDefault(schema::FeatureIndex::Co2Ppm);
  float soil_moisture_pct = detail::schemaDefault(schema::FeatureIndex::SoilMoisturePct);
  float outside_temperature_c = detail::schemaDefault(schema::FeatureIndex::OutsideTemperatureC);
  float outside_humidity_pct = detail::schemaDefault(schema::FeatureIndex::OutsideHumidityPct);
  // Simulation-only boundary condition; not encoded into the ML feature vector.
  float outside_co2_ppm = 420.0f;
};

struct SensorValidity {
  bool air_temperature = detail::schemaDefaultBool(schema::FeatureIndex::AirTemperatureValid);
  bool air_humidity = detail::schemaDefaultBool(schema::FeatureIndex::AirHumidityValid);
  bool co2 = detail::schemaDefaultBool(schema::FeatureIndex::Co2Valid);
  bool soil_moisture = detail::schemaDefaultBool(schema::FeatureIndex::SoilMoistureValid);
  bool outside_temperature =
      detail::schemaDefaultBool(schema::FeatureIndex::OutsideTemperatureValid);
  bool outside_humidity = detail::schemaDefaultBool(schema::FeatureIndex::OutsideHumidityValid);
  // Simulation-only; when false, symulator używa domyślnego CO₂ zewnętrznego (420 ppm).
  bool outside_co2 = true;
};

struct EnvironmentConfig {
  float growbox_volume_m3 = detail::schemaDefault(schema::FeatureIndex::GrowboxVolumeM3);
  float thermal_mass_j_per_k = detail::schemaDefault(schema::FeatureIndex::ThermalMassJPerK);
  float heat_loss_w_per_k = detail::schemaDefault(schema::FeatureIndex::HeatLossWPerK);
  float air_leak_rate_ach = detail::schemaDefault(schema::FeatureIndex::AirLeakRateAch);
};

struct CultivationConfig {
  float pot_volume_l = detail::schemaDefault(schema::FeatureIndex::PotVolumeL);
  float substrate_water_capacity_ml =
      detail::schemaDefault(schema::FeatureIndex::SubstrateWaterCapacityMl);
  float transpiration_factor = detail::schemaDefault(schema::FeatureIndex::TranspirationFactor);
};

struct HeaterCapabilities {
  bool available = detail::schemaDefaultBool(schema::FeatureIndex::HeaterAvailable);
  float max_power_w = detail::schemaDefault(schema::FeatureIndex::HeaterMaxPowerW);
  float efficiency = detail::schemaDefault(schema::FeatureIndex::HeaterEfficiency);
  ActuatorControlType control_type = static_cast<ActuatorControlType>(
      static_cast<std::uint8_t>(detail::schemaDefault(schema::FeatureIndex::HeaterControlType)));
};

struct FanCapabilities {
  bool available = detail::schemaDefaultBool(schema::FeatureIndex::FanAvailable);
  float max_airflow_m3_h = detail::schemaDefault(schema::FeatureIndex::FanMaxAirflowM3H);
  float minimum_command = detail::schemaDefault(schema::FeatureIndex::FanMinimumCommand);
  ActuatorControlType control_type = static_cast<ActuatorControlType>(
      static_cast<std::uint8_t>(detail::schemaDefault(schema::FeatureIndex::FanControlType)));
};

struct HumidifierCapabilities {
  bool available = detail::schemaDefaultBool(schema::FeatureIndex::HumidifierAvailable);
  float max_output_g_h = detail::schemaDefault(schema::FeatureIndex::HumidifierMaxOutputGH);
  ActuatorControlType control_type = static_cast<ActuatorControlType>(static_cast<std::uint8_t>(
      detail::schemaDefault(schema::FeatureIndex::HumidifierControlType)));
};

struct IrrigationPumpCapabilities {
  bool available = detail::schemaDefaultBool(schema::FeatureIndex::IrrigationAvailable);
  float flow_ml_s = detail::schemaDefault(schema::FeatureIndex::IrrigationFlowMlS);
  float maximum_pulse_s = detail::schemaDefault(schema::FeatureIndex::IrrigationMaximumPulseS);
  float minimum_interval_s =
      detail::schemaDefault(schema::FeatureIndex::IrrigationMinimumIntervalS);
  ActuatorControlType control_type = static_cast<ActuatorControlType>(static_cast<std::uint8_t>(
      detail::schemaDefault(schema::FeatureIndex::IrrigationControlType)));
};

struct ActuatorCapabilities {
  HeaterCapabilities heater{};
  FanCapabilities fan{};
  HumidifierCapabilities humidifier{};
  IrrigationPumpCapabilities irrigation_pump{};
};

struct ControlTargets {
  float air_temperature_c = detail::schemaDefault(schema::FeatureIndex::TargetAirTemperatureC);
  float air_humidity_pct = detail::schemaDefault(schema::FeatureIndex::TargetAirHumidityPct);
  float co2_ppm = detail::schemaDefault(schema::FeatureIndex::TargetCo2Ppm);
  float soil_moisture_pct = detail::schemaDefault(schema::FeatureIndex::TargetSoilMoisturePct);
};

struct PreviousControlState {
  float heater = detail::schemaDefault(schema::FeatureIndex::PreviousHeater);
  float fan = detail::schemaDefault(schema::FeatureIndex::PreviousFan);
  float humidifier = detail::schemaDefault(schema::FeatureIndex::PreviousHumidifier);
  float irrigation = detail::schemaDefault(schema::FeatureIndex::PreviousIrrigation);
};

struct SafetyConfig {
  float maximum_air_temperature_c = schema::kDefaultMaximumAirTemperatureC;
  float alarm_air_temperature_c = schema::kDefaultAlarmAirTemperatureC;
  float alarm_minimum_fan = schema::kDefaultAlarmMinimumFan;
  float binary_threshold = schema::kDefaultBinaryThreshold;
  float heater_minimum_on_s = schema::kDefaultHeaterMinimumOnS;
  float heater_minimum_off_s = schema::kDefaultHeaterMinimumOffS;
  float humidifier_minimum_on_s = schema::kDefaultHumidifierMinimumOnS;
  float humidifier_minimum_off_s = schema::kDefaultHumidifierMinimumOffS;
};

struct ControllerInput {
  SensorState sensors{};
  SensorValidity validity{};
  EnvironmentConfig environment{};
  CultivationConfig cultivation{};
  ActuatorCapabilities actuators{};
  ControlTargets targets{};
  PreviousControlState previous{};
  SafetyConfig safety{};
  std::uint64_t monotonic_time_ms = 0U;
};

struct FeatureVector {
  std::array<float, schema::kFeatureCount> values{};
};

struct RawModelDecision {
  float heater = 0.0f;
  float fan = 0.0f;
  float humidifier = 0.0f;
  float irrigation = 0.0f;
};

struct SafeControlDecision {
  float heater = 0.0f;
  float fan = 0.0f;
  float humidifier = 0.0f;
  float irrigation = 0.0f;
  float irrigation_pulse_s = 0.0f;
};

enum class EncoderStatus : std::uint8_t {
  Ok = 0,
  NonFiniteInput,
};

struct EncoderReport {
  std::uint64_t clamped_feature_mask = 0U;
  std::uint64_t substituted_feature_mask = 0U;
};

enum class ModelStatus : std::uint8_t {
  Ok = 0,
  SchemaMismatch,
  ShapeMismatch,
  NonFiniteInput,
  InferenceFailure,
  NonFiniteOutput,
};

enum class SafetyReason : std::uint32_t {
  None = 0U,
  NonFiniteInput = 1U << 0U,
  ModelFailure = 1U << 1U,
  SchemaMismatch = 1U << 2U,
  NonFiniteModelOutput = 1U << 3U,
  OutputClamped = 1U << 4U,
  TemperatureUnavailable = 1U << 5U,
  ActuatorUnavailable = 1U << 6U,
  OverTemperature = 1U << 7U,
  TemperatureAlarmFan = 1U << 8U,
  PumpPulseLimited = 1U << 9U,
  PumpMinimumInterval = 1U << 10U,
  BinaryThreshold = 1U << 11U,
  BinaryMinimumOn = 1U << 12U,
  BinaryMinimumOff = 1U << 13U,
  InvalidCapability = 1U << 14U,
};

constexpr std::uint32_t reasonBit(SafetyReason reason) noexcept {
  return static_cast<std::uint32_t>(reason);
}

struct SafetyReport {
  bool modified = false;
  std::uint32_t reason_mask = 0U;
  std::array<std::uint32_t, schema::kOutputCount> output_reason_masks{};
};

enum class ControllerStatus : std::uint8_t {
  Ok = 0,
  EncoderError,
  ModelError,
};

struct ControllerDiagnostics {
  EncoderStatus encoder_status = EncoderStatus::Ok;
  ModelStatus model_status = ModelStatus::Ok;
  EncoderReport encoder{};
  SafetyReport safety{};
  // The platform application owns timing and may populate this after process().
  std::uint32_t inference_us = 0U;
};

struct ControllerOutput {
  RawModelDecision raw{};
  SafeControlDecision safe{};
  ControllerDiagnostics diagnostics{};
};

} // namespace control
} // namespace growbox
