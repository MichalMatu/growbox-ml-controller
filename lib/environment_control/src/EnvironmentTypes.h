#pragma once

#include "EnvironmentSchema.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace growbox {
namespace control {

inline constexpr std::size_t kMaxPots = 4U;

static_assert(schema::kFeatureCount <= schema::kFeatureDiagnosticsMaskBits,
              "Encoder diagnostics mask must cover every feature");
static_assert(schema::kOutputCount == 15U,
              "Environment decision structures implement fifteen schema outputs");

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
  float nutrient_solution_temperature_c =
      detail::schemaDefault(schema::FeatureIndex::NutrientSolutionTemperatureC);
  float outside_temperature_c = detail::schemaDefault(schema::FeatureIndex::OutsideTemperatureC);
  float outside_humidity_pct = detail::schemaDefault(schema::FeatureIndex::OutsideHumidityPct);
  float outside_co2_ppm = detail::schemaDefault(schema::FeatureIndex::OutsideCo2Ppm);
};

struct SensorValidity {
  bool air_temperature = detail::schemaDefaultBool(schema::FeatureIndex::AirTemperatureValid);
  bool air_humidity = detail::schemaDefaultBool(schema::FeatureIndex::AirHumidityValid);
  bool co2 = detail::schemaDefaultBool(schema::FeatureIndex::Co2Valid);
  bool nutrient_solution_temperature =
      detail::schemaDefaultBool(schema::FeatureIndex::NutrientSolutionTemperatureValid);
  bool outside_temperature =
      detail::schemaDefaultBool(schema::FeatureIndex::OutsideTemperatureValid);
  bool outside_humidity = detail::schemaDefaultBool(schema::FeatureIndex::OutsideHumidityValid);
  bool outside_co2 = detail::schemaDefaultBool(schema::FeatureIndex::OutsideCo2Valid);
};

struct PotSensorState {
  float soil_moisture_pct = 50.0f;
  float soil_temperature_c = 20.0f;
};

struct PotSensorValidity {
  bool soil_moisture = false;
  bool soil_temperature = false;
};

struct PotCultivationConfig {
  float pot_volume_l = 10.0f;
  float substrate_water_capacity_ml = 3000.0f;
  float transpiration_factor = 1.0f;
};

struct IrrigationPumpCapabilities {
  bool available = false;
  float flow_ml_s = 0.0f;
  float maximum_pulse_s = 0.0f;
  float minimum_interval_s = 0.0f;
  ActuatorControlType control_type = ActuatorControlType::Binary;
};

struct HeatMatCapabilities {
  bool available = false;
  float max_power_w = 0.0f;
  ActuatorControlType control_type = ActuatorControlType::Binary;
};

struct PotConfig {
  bool available = false;
  PotSensorState sensors{};
  PotSensorValidity validity{};
  PotCultivationConfig cultivation{};
  float target_soil_moisture_pct = 50.0f;
  float target_soil_temperature_c = 20.0f;
  IrrigationPumpCapabilities irrigation{};
  HeatMatCapabilities heat_mat{};
  float previous_irrigation = 0.0f;
  float previous_heat_mat = 0.0f;
};

struct EnvironmentConfig {
  float growbox_volume_m3 = detail::schemaDefault(schema::FeatureIndex::GrowboxVolumeM3);
  float thermal_mass_j_per_k = detail::schemaDefault(schema::FeatureIndex::ThermalMassJPerK);
  float heat_loss_w_per_k = detail::schemaDefault(schema::FeatureIndex::HeatLossWPerK);
  float air_leak_rate_ach = detail::schemaDefault(schema::FeatureIndex::AirLeakRateAch);
};

struct HeaterCapabilities {
  bool available = detail::schemaDefaultBool(schema::FeatureIndex::HeaterAvailable);
  float max_power_w = detail::schemaDefault(schema::FeatureIndex::HeaterMaxPowerW);
  float efficiency = detail::schemaDefault(schema::FeatureIndex::HeaterEfficiency);
};

struct FanCapabilities {
  bool available = detail::schemaDefaultBool(schema::FeatureIndex::FanAvailable);
  float max_airflow_m3_h = detail::schemaDefault(schema::FeatureIndex::FanMaxAirflowM3H);
  float minimum_command = detail::schemaDefault(schema::FeatureIndex::FanMinimumCommand);
};

struct HumidifierCapabilities {
  bool available = detail::schemaDefaultBool(schema::FeatureIndex::HumidifierAvailable);
  float max_output_g_h = detail::schemaDefault(schema::FeatureIndex::HumidifierMaxOutputGH);
};

struct DehumidifierCapabilities {
  bool available = detail::schemaDefaultBool(schema::FeatureIndex::DehumidifierAvailable);
  float max_removal_g_h = detail::schemaDefault(schema::FeatureIndex::DehumidifierMaxRemovalGH);
};

struct CoolerCapabilities {
  bool available = detail::schemaDefaultBool(schema::FeatureIndex::CoolerAvailable);
  float max_cooling_w = detail::schemaDefault(schema::FeatureIndex::CoolerMaxCoolingW);
};

struct Co2DoserCapabilities {
  bool available = detail::schemaDefaultBool(schema::FeatureIndex::Co2DoserAvailable);
  float dose_ppm_per_full_pulse =
      detail::schemaDefault(schema::FeatureIndex::Co2DoserDosePpmPerFullPulse);
  float maximum_pulse_s = detail::schemaDefault(schema::FeatureIndex::Co2DoserMaximumPulseS);
};

struct NutrientHeaterCapabilities {
  bool available = detail::schemaDefaultBool(schema::FeatureIndex::NutrientHeaterAvailable);
  float max_power_w = detail::schemaDefault(schema::FeatureIndex::NutrientHeaterMaxPowerW);
  float efficiency = detail::schemaDefault(schema::FeatureIndex::NutrientHeaterEfficiency);
};

struct GlobalActuatorCapabilities {
  HeaterCapabilities heater{};
  FanCapabilities fan{};
  HumidifierCapabilities humidifier{};
  DehumidifierCapabilities dehumidifier{};
  CoolerCapabilities cooler{};
  Co2DoserCapabilities co2_doser{};
  NutrientHeaterCapabilities nutrient_heater{};
};

struct ControlTargets {
  float air_temperature_c = detail::schemaDefault(schema::FeatureIndex::TargetAirTemperatureC);
  float air_humidity_pct = detail::schemaDefault(schema::FeatureIndex::TargetAirHumidityPct);
  float co2_ppm = detail::schemaDefault(schema::FeatureIndex::TargetCo2Ppm);
  float nutrient_solution_temperature_c =
      detail::schemaDefault(schema::FeatureIndex::TargetNutrientSolutionTemperatureC);
};

struct PreviousControlState {
  float heater = detail::schemaDefault(schema::FeatureIndex::PreviousHeater);
  float fan = detail::schemaDefault(schema::FeatureIndex::PreviousFan);
  float humidifier = detail::schemaDefault(schema::FeatureIndex::PreviousHumidifier);
  float dehumidifier = detail::schemaDefault(schema::FeatureIndex::PreviousDehumidifier);
  float cooler = detail::schemaDefault(schema::FeatureIndex::PreviousCooler);
  float co2_doser = detail::schemaDefault(schema::FeatureIndex::PreviousCo2Doser);
  float nutrient_heater = detail::schemaDefault(schema::FeatureIndex::PreviousNutrientHeater);
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
  float dehumidifier_minimum_on_s = schema::kDefaultDehumidifierMinimumOnS;
  float dehumidifier_minimum_off_s = schema::kDefaultDehumidifierMinimumOffS;
  float cooler_minimum_on_s = schema::kDefaultCoolerMinimumOnS;
  float cooler_minimum_off_s = schema::kDefaultCoolerMinimumOffS;
  float co2_doser_minimum_interval_s = schema::kDefaultCo2DoserMinimumIntervalS;
  float fan_venting_co2_threshold = schema::kDefaultFanVentingCo2Threshold;
  float maximum_nutrient_soil_delta_c = schema::kDefaultMaximumNutrientSoilDeltaC;
  float minimum_nutrient_solution_temperature_c =
      schema::kDefaultMinimumNutrientSolutionTemperatureC;
};

struct ControllerInput {
  SensorState sensors{};
  SensorValidity validity{};
  std::array<PotConfig, kMaxPots> pots{};
  bool lights_active = false;
  EnvironmentConfig environment{};
  GlobalActuatorCapabilities actuators{};
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
  float dehumidifier = 0.0f;
  float cooler = 0.0f;
  float co2_doser = 0.0f;
  float irrigation_pot_1 = 0.0f;
  float irrigation_pot_2 = 0.0f;
  float irrigation_pot_3 = 0.0f;
  float irrigation_pot_4 = 0.0f;
  float nutrient_heater = 0.0f;
  float heat_mat_pot_1 = 0.0f;
  float heat_mat_pot_2 = 0.0f;
  float heat_mat_pot_3 = 0.0f;
  float heat_mat_pot_4 = 0.0f;
};

struct SafeControlDecision {
  float heater = 0.0f;
  float fan = 0.0f;
  float humidifier = 0.0f;
  float dehumidifier = 0.0f;
  float cooler = 0.0f;
  float co2_doser = 0.0f;
  float irrigation_pot_1 = 0.0f;
  float irrigation_pot_2 = 0.0f;
  float irrigation_pot_3 = 0.0f;
  float irrigation_pot_4 = 0.0f;
  float nutrient_heater = 0.0f;
  float heat_mat_pot_1 = 0.0f;
  float heat_mat_pot_2 = 0.0f;
  float heat_mat_pot_3 = 0.0f;
  float heat_mat_pot_4 = 0.0f;
  std::array<float, kMaxPots> irrigation_pulse_s{};
};

struct EncoderMask {
  std::array<std::uint64_t, 2> words{};

  void set(std::size_t index) noexcept {
    if (index < 64U) {
      words[0] |= (std::uint64_t{1U} << index);
    } else {
      words[1] |= (std::uint64_t{1U} << (index - 64U));
    }
  }

  bool any() const noexcept {
    return words[0] != 0U || words[1] != 0U;
  }
};

enum class EncoderStatus : std::uint8_t {
  Ok = 0,
  NonFiniteInput,
};

struct EncoderReport {
  EncoderMask clamped_feature_mask{};
  EncoderMask substituted_feature_mask{};
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
  Co2VentingFan = 1U << 15U,
  SoilMoistureSatisfied = 1U << 16U,
  SoilMoistureUnavailable = 1U << 17U,
  NutrientSoilDeltaExceeded = 1U << 18U,
  NutrientSolutionTooCold = 1U << 19U,
  Co2TargetReached = 1U << 20U,
  Co2SensorUnavailable = 1U << 21U,
  HumidityUnavailable = 1U << 22U,
  ActuatorConflict = 1U << 23U,
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
  std::uint32_t inference_us = 0U;
};

struct ControllerOutput {
  RawModelDecision raw{};
  SafeControlDecision safe{};
  ControllerDiagnostics diagnostics{};
};

float rawOutputValue(const RawModelDecision& decision, schema::OutputIndex output) noexcept;
float& rawOutputValue(RawModelDecision& decision, schema::OutputIndex output) noexcept;
float safeOutputValue(const SafeControlDecision& decision, schema::OutputIndex output) noexcept;
float& safeOutputValue(SafeControlDecision& decision, schema::OutputIndex output) noexcept;

} // namespace control
} // namespace growbox
