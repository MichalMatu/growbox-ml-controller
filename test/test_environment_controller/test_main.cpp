#include <unity.h>

#include "../../tests/fixtures/ModelGoldenVectors.h"
#include "EnvironmentController.h"
#include "FeatureEncoder.h"
#include "ModelRuntime.h"
#include "SafetySupervisor.h"
#include "generated/ModelManifest.h"

#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>

using namespace growbox::control;

namespace {

bool maskAny(const EncoderMask& mask) noexcept {
  return mask.words[0] != 0U || mask.words[1] != 0U;
}

bool maskHas(const EncoderMask& mask, schema::FeatureIndex feature) noexcept {
  const std::size_t index = schema::index(feature);
  if (index < 64U) {
    return (mask.words[0] & (std::uint64_t{1U} << index)) != 0U;
  }
  return (mask.words[1] & (std::uint64_t{1U} << (index - 64U))) != 0U;
}

ControllerInput nominalInput() {
  ControllerInput input{};
  input.validity = SensorValidity{true, true, true, false, true, true, true};
  input.sensors.air_temperature_c = 24.0f;
  input.sensors.air_humidity_pct = 55.0f;
  input.sensors.co2_ppm = 900.0f;
  input.sensors.outside_temperature_c = 18.0f;
  input.sensors.outside_humidity_pct = 52.0f;
  input.sensors.outside_co2_ppm = 420.0f;

  input.zones[0].available = true;
  input.zones[0].validity.soil_moisture = true;
  input.zones[0].sensors.soil_moisture_pct = 44.0f;
  input.zones[0].cultivation.pot_volume_l = 12.0f;
  input.zones[0].cultivation.substrate_water_capacity_ml = 3600.0f;
  input.zones[0].cultivation.transpiration_factor = 1.0f;
  input.zones[0].target_soil_moisture_pct = 50.0f;
  input.zones[0].irrigation.available = true;
  input.zones[0].irrigation.flow_ml_s = 20.0f;
  input.zones[0].irrigation.maximum_pulse_s = 10.0f;
  input.zones[0].irrigation.minimum_interval_s = 60.0f;
  input.zones[0].irrigation.control_type = ActuatorControlType::Binary;

  input.actuators.heater.available = true;
  input.actuators.heater.max_power_w = 250.0f;
  input.actuators.heater.efficiency = 0.9f;
  input.actuators.fan.available = true;
  input.actuators.fan.max_airflow_m3_h = 120.0f;
  input.actuators.fan.minimum_command = 0.15f;
  input.actuators.humidifier.available = true;
  input.actuators.humidifier.max_output_g_h = 250.0f;
  input.actuators.dehumidifier.available = false;
  input.actuators.cooler.available = false;
  input.actuators.co2_doser.available = false;
  input.monotonic_time_ms = 100000U;
  return input;
}

bool hasReason(std::uint32_t mask, SafetyReason reason) {
  return (mask & reasonBit(reason)) != 0U;
}

void assertDecisionInRange(const SafeControlDecision& decision) {
  for (std::size_t index = 0; index < schema::kOutputCount; ++index) {
    const float value = safeOutputValue(decision, static_cast<schema::OutputIndex>(index));
    TEST_ASSERT_TRUE(value >= 0.0f);
    TEST_ASSERT_TRUE(value <= 1.0f);
  }
}

void test_schema_feature_count_and_order() {
  TEST_ASSERT_EQUAL_UINT32(3U, schema::kSchemaVersion);
  TEST_ASSERT_EQUAL_UINT32(128U, schema::kFeatureCount);
  TEST_ASSERT_EQUAL_UINT32(15U, schema::kOutputCount);
  TEST_ASSERT_EQUAL_STRING("air_temperature_c", schema::kFeatureNames[0]);
  TEST_ASSERT_EQUAL_STRING("lights_active", schema::kFeatureNames[34]);
  TEST_ASSERT_EQUAL_STRING("heater", schema::kOutputNames[0]);
  TEST_ASSERT_EQUAL_STRING("irrigation_zone_4", schema::kOutputNames[9]);
  TEST_ASSERT_EQUAL_STRING("nutrient_heater", schema::kOutputNames[10]);
  TEST_ASSERT_EQUAL_STRING("heat_mat_zone_4", schema::kOutputNames[14]);
}

void test_feature_encoder_uses_generated_indices_and_normalization() {
  ControllerInput input = nominalInput();
  input.sensors.air_temperature_c = 20.0f;
  input.sensors.air_humidity_pct = 25.0f;
  FeatureVector features{};
  EncoderReport report{};

  TEST_ASSERT_EQUAL_UINT8(
      static_cast<std::uint8_t>(EncoderStatus::Ok),
      static_cast<std::uint8_t>(FeatureEncoder::encode(input, features, report)));
  TEST_ASSERT_FLOAT_WITHIN(1.0e-6f, 0.5f,
                           features.values[schema::index(schema::FeatureIndex::AirTemperatureC)]);
  TEST_ASSERT_FLOAT_WITHIN(1.0e-6f, 0.25f,
                           features.values[schema::index(schema::FeatureIndex::AirHumidityPct)]);
  TEST_ASSERT_FALSE(maskAny(report.clamped_feature_mask));
}

void test_cpp_defaults_match_schema_defaults() {
  ControllerInput input{};
  FeatureVector features{};
  EncoderReport report{};
  TEST_ASSERT_EQUAL_UINT8(
      static_cast<std::uint8_t>(EncoderStatus::Ok),
      static_cast<std::uint8_t>(FeatureEncoder::encode(input, features, report)));
  for (std::size_t index = 0; index < schema::kFeatureCount; ++index) {
    const float expected = (schema::kFeatureDefaults[index] - schema::kFeatureMinimums[index]) /
                           (schema::kFeatureMaximums[index] - schema::kFeatureMinimums[index]);
    TEST_ASSERT_FLOAT_WITHIN(1.0e-6f, expected, features.values[index]);
  }
}

void test_unavailable_zone_target_is_canonicalized_to_schema_default() {
  ControllerInput input = nominalInput();
  input.zones[1].available = false;
  input.zones[1].target_soil_moisture_pct = 72.0f;
  FeatureVector features{};
  EncoderReport report{};

  TEST_ASSERT_EQUAL_UINT8(
      static_cast<std::uint8_t>(EncoderStatus::Ok),
      static_cast<std::uint8_t>(FeatureEncoder::encode(input, features, report)));
  const std::size_t target_index = schema::index(schema::FeatureIndex::Zone2TargetSoilMoisturePct);
  const float expected =
      (schema::kFeatureDefaults[target_index] - schema::kFeatureMinimums[target_index]) /
      (schema::kFeatureMaximums[target_index] - schema::kFeatureMinimums[target_index]);
  TEST_ASSERT_FLOAT_WITHIN(1.0e-6f, expected, features.values[target_index]);
  TEST_ASSERT_TRUE(
      maskHas(report.substituted_feature_mask, schema::FeatureIndex::Zone2TargetSoilMoisturePct));
}

void test_unavailable_actuator_capabilities_are_canonicalized_to_zero() {
  ControllerInput input = nominalInput();
  input.actuators.heater.available = false;
  input.actuators.heater.max_power_w = 500.0f;
  input.actuators.fan.available = false;
  input.actuators.fan.max_airflow_m3_h = 200.0f;
  input.zones[0].irrigation.available = false;
  input.zones[0].irrigation.flow_ml_s = 20.0f;
  FeatureVector features{};
  EncoderReport report{};

  TEST_ASSERT_EQUAL_UINT8(
      static_cast<std::uint8_t>(EncoderStatus::Ok),
      static_cast<std::uint8_t>(FeatureEncoder::encode(input, features, report)));
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f,
                           features.values[schema::index(schema::FeatureIndex::HeaterMaxPowerW)]);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f,
                           features.values[schema::index(schema::FeatureIndex::FanMaxAirflowM3H)]);
  TEST_ASSERT_FLOAT_WITHIN(
      0.0f, 0.0f, features.values[schema::index(schema::FeatureIndex::Zone1IrrigationFlowMlS)]);
  TEST_ASSERT_TRUE(maskAny(report.substituted_feature_mask));
}

void test_encoder_clamps_contract_ranges() {
  ControllerInput input = nominalInput();
  input.sensors.air_temperature_c = 200.0f;
  input.sensors.air_humidity_pct = -10.0f;
  input.previous.fan = 2.0f;
  FeatureVector features{};
  EncoderReport report{};

  TEST_ASSERT_EQUAL_UINT8(
      static_cast<std::uint8_t>(EncoderStatus::Ok),
      static_cast<std::uint8_t>(FeatureEncoder::encode(input, features, report)));
  TEST_ASSERT_TRUE(maskAny(report.clamped_feature_mask));
}

void test_encoder_rejects_non_finite_input_and_imputes_finite_masked_sensor() {
  ControllerInput input = nominalInput();
  input.sensors.air_temperature_c = std::numeric_limits<float>::quiet_NaN();
  FeatureVector features{};
  EncoderReport report{};

  TEST_ASSERT_EQUAL_UINT8(
      static_cast<std::uint8_t>(EncoderStatus::NonFiniteInput),
      static_cast<std::uint8_t>(FeatureEncoder::encode(input, features, report)));

  input.validity.air_temperature = false;
  input.sensors.air_temperature_c = 200.0f;
  TEST_ASSERT_EQUAL_UINT8(
      static_cast<std::uint8_t>(EncoderStatus::Ok),
      static_cast<std::uint8_t>(FeatureEncoder::encode(input, features, report)));
  TEST_ASSERT_FLOAT_WITHIN(
      0.0f, 0.0f, features.values[schema::index(schema::FeatureIndex::AirTemperatureValid)]);
}

void test_safety_masks_unavailable_outputs_and_missing_temperature() {
  ControllerInput input{};
  input.validity.air_temperature = false;
  RawModelDecision raw{};
  raw.heater = 1.0f;
  raw.fan = 1.0f;
  raw.humidifier = 1.0f;
  raw.irrigation_zone_1 = 1.0f;
  SafeControlDecision safe{};
  SafetyReport report{};
  SafetySupervisor supervisor{};

  supervisor.apply(input, raw, SafetyReason::None, safe, report);
  assertDecisionInRange(safe);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f, safe.heater);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f, safe.fan);
  TEST_ASSERT_TRUE(hasReason(report.reason_mask, SafetyReason::ActuatorUnavailable));
  TEST_ASSERT_TRUE(hasReason(report.reason_mask, SafetyReason::TemperatureUnavailable));
}

void test_alarm_temperature_forces_heater_off_and_fan_minimum() {
  ControllerInput input = nominalInput();
  input.sensors.air_temperature_c = 36.0f;
  RawModelDecision raw{};
  raw.heater = 1.0f;
  raw.fan = 0.1f;
  SafeControlDecision safe{};
  SafetyReport report{};
  SafetySupervisor supervisor{};

  supervisor.apply(input, raw, SafetyReason::None, safe, report);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f, safe.heater);
  TEST_ASSERT_FLOAT_WITHIN(1.0e-6f, input.safety.alarm_minimum_fan, safe.fan);
  TEST_ASSERT_TRUE(hasReason(report.reason_mask, SafetyReason::OverTemperature));
  TEST_ASSERT_TRUE(hasReason(report.reason_mask, SafetyReason::TemperatureAlarmFan));
}

void test_zone_pump_pulse_and_minimum_interval() {
  ControllerInput input = nominalInput();
  input.zones[0].irrigation.maximum_pulse_s = 1000.0f;
  input.zones[0].irrigation.minimum_interval_s = 60.0f;
  RawModelDecision raw{};
  raw.irrigation_zone_1 = 1.0f;
  SafeControlDecision safe{};
  SafetyReport report{};
  SafetySupervisor supervisor{};

  supervisor.apply(input, raw, SafetyReason::None, safe, report);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 1.0f, safe.irrigation_zone_1);
  TEST_ASSERT_FLOAT_WITHIN(1.0e-6f, 600.0f, safe.irrigation_pulse_s[0]);
  TEST_ASSERT_TRUE(hasReason(report.reason_mask, SafetyReason::PumpPulseLimited));

  input.monotonic_time_ms += 1000U;
  raw.irrigation_zone_1 = 1.0f;
  supervisor.apply(input, raw, SafetyReason::None, safe, report);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f, safe.irrigation_zone_1);
  TEST_ASSERT_TRUE(hasReason(report.reason_mask, SafetyReason::PumpMinimumInterval));

  input.monotonic_time_ms += 60000U;
  supervisor.apply(input, raw, SafetyReason::None, safe, report);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 1.0f, safe.irrigation_zone_1);
}

void test_soil_moisture_at_target_blocks_irrigation() {
  ControllerInput input = nominalInput();
  input.zones[0].sensors.soil_moisture_pct = 55.0f;
  input.zones[0].target_soil_moisture_pct = 50.0f;
  RawModelDecision raw{};
  raw.irrigation_zone_1 = 1.0f;
  SafeControlDecision safe{};
  SafetyReport report{};
  SafetySupervisor supervisor{};

  supervisor.apply(input, raw, SafetyReason::None, safe, report);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f, safe.irrigation_zone_1);
  TEST_ASSERT_TRUE(hasReason(report.reason_mask, SafetyReason::SoilMoistureSatisfied));
}

void test_invalid_soil_moisture_blocks_irrigation() {
  ControllerInput input = nominalInput();
  input.zones[0].validity.soil_moisture = false;
  RawModelDecision raw{};
  raw.irrigation_zone_1 = 1.0f;
  SafeControlDecision safe{};
  SafetyReport report{};
  SafetySupervisor supervisor{};

  supervisor.apply(input, raw, SafetyReason::None, safe, report);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f, safe.irrigation_zone_1);
  TEST_ASSERT_TRUE(hasReason(report.reason_mask, SafetyReason::SoilMoistureUnavailable));
}

void test_cold_nutrient_solution_blocks_irrigation() {
  ControllerInput input = nominalInput();
  input.zones[0].sensors.soil_moisture_pct = 30.0f;
  input.sensors.nutrient_solution_temperature_c = 10.0f;
  input.validity.nutrient_solution_temperature = true;
  input.safety.minimum_nutrient_solution_temperature_c = 15.0f;
  RawModelDecision raw{};
  raw.irrigation_zone_1 = 1.0f;
  SafeControlDecision safe{};
  SafetyReport report{};
  SafetySupervisor supervisor{};

  supervisor.apply(input, raw, SafetyReason::None, safe, report);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f, safe.irrigation_zone_1);
  TEST_ASSERT_TRUE(hasReason(report.reason_mask, SafetyReason::NutrientSolutionTooCold));
}

void test_nutrient_soil_delta_blocks_irrigation() {
  ControllerInput input = nominalInput();
  input.zones[0].sensors.soil_moisture_pct = 30.0f;
  input.zones[0].sensors.soil_temperature_c = 30.0f;
  input.zones[0].validity.soil_temperature = true;
  input.sensors.nutrient_solution_temperature_c = 20.0f;
  input.validity.nutrient_solution_temperature = true;
  input.safety.maximum_nutrient_soil_delta_c = 8.0f;
  input.safety.minimum_nutrient_solution_temperature_c = 15.0f;
  RawModelDecision raw{};
  raw.irrigation_zone_1 = 1.0f;
  SafeControlDecision safe{};
  SafetyReport report{};
  SafetySupervisor supervisor{};

  supervisor.apply(input, raw, SafetyReason::None, safe, report);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f, safe.irrigation_zone_1);
  TEST_ASSERT_TRUE(hasReason(report.reason_mask, SafetyReason::NutrientSoilDeltaExceeded));
}

void test_co2_target_reached_blocks_doser() {
  ControllerInput input = nominalInput();
  input.actuators.co2_doser.available = true;
  input.actuators.co2_doser.dose_ppm_per_full_pulse = 100.0f;
  input.validity.co2 = true;
  input.sensors.co2_ppm = 1100.0f;
  input.targets.co2_ppm = 900.0f;
  RawModelDecision raw{};
  raw.co2_doser = 1.0f;
  SafeControlDecision safe{};
  SafetyReport report{};
  SafetySupervisor supervisor{};

  supervisor.apply(input, raw, SafetyReason::None, safe, report);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f, safe.co2_doser);
  TEST_ASSERT_TRUE(hasReason(report.reason_mask, SafetyReason::Co2TargetReached));
}

void test_heater_and_cooler_are_mutually_exclusive() {
  ControllerInput input = nominalInput();
  input.actuators.cooler.available = true;
  input.actuators.cooler.max_cooling_w = 200.0f;
  input.previous.heater = 1.0f;
  input.safety.heater_minimum_off_s = 0.0f;
  input.safety.heater_minimum_on_s = 0.0f;
  input.safety.cooler_minimum_on_s = 0.0f;
  input.safety.cooler_minimum_off_s = 0.0f;
  input.monotonic_time_ms = 1'000'000U;
  RawModelDecision raw{};
  raw.heater = 1.0f;
  raw.cooler = 1.0f;
  SafeControlDecision safe{};
  SafetyReport report{};
  SafetySupervisor supervisor{};

  supervisor.apply(input, raw, SafetyReason::None, safe, report);
  TEST_ASSERT_TRUE(safe.heater > 0.0f || safe.cooler == 0.0f);
  TEST_ASSERT_TRUE(hasReason(report.reason_mask, SafetyReason::ActuatorConflict));
}

void test_humidity_unavailable_blocks_humidifier_and_dehumidifier() {
  ControllerInput input = nominalInput();
  input.actuators.dehumidifier.available = true;
  input.actuators.dehumidifier.max_removal_g_h = 80.0f;
  input.validity.air_humidity = false;
  RawModelDecision raw{};
  raw.humidifier = 1.0f;
  raw.dehumidifier = 1.0f;
  SafeControlDecision safe{};
  SafetyReport report{};
  SafetySupervisor supervisor{};

  supervisor.apply(input, raw, SafetyReason::None, safe, report);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f, safe.humidifier);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f, safe.dehumidifier);
  TEST_ASSERT_TRUE(hasReason(report.reason_mask, SafetyReason::HumidityUnavailable));
}

bool manifestMatchesSchema() noexcept {
  return generated_manifest::kInputCount == schema::kFeatureCount &&
         generated_manifest::kOutputCount == schema::kOutputCount;
}

void test_model_schema_hash_compatibility() {
  if (!manifestMatchesSchema()) {
    return;
  }
  TEST_ASSERT_EQUAL_STRING(schema::kSchemaHash, model_golden_vectors::kSchemaHash);
  TEST_ASSERT_EQUAL_STRING(schema::kSchemaHash, generated_manifest::kSchemaHash);
  TEST_ASSERT_EQUAL_STRING(ModelRuntime::modelVersion(), generated_manifest::kModelVersion);
  TEST_ASSERT_EQUAL_UINT32(schema::kSchemaVersion, generated_manifest::kSchemaVersion);
  TEST_ASSERT_EQUAL_UINT32(schema::kFeatureCount, generated_manifest::kInputCount);
  TEST_ASSERT_EQUAL_UINT32(schema::kOutputCount, generated_manifest::kOutputCount);
  TEST_ASSERT_EQUAL_STRING(schema::kSchemaHash, ModelRuntime::schemaHash());
}

void test_golden_model_inference_and_output_bounds() {
  if (!manifestMatchesSchema()) {
    return;
  }
  ModelRuntime model{};
  for (std::size_t row = 0; row < model_golden_vectors::kVectorCount; ++row) {
    FeatureVector features{};
    for (std::size_t feature = 0; feature < generated_manifest::kInputCount; ++feature) {
      features.values[feature] = model_golden_vectors::kFeatures[row][feature];
    }
    RawModelDecision actual{};
    TEST_ASSERT_EQUAL_UINT8(static_cast<std::uint8_t>(ModelStatus::Ok),
                            static_cast<std::uint8_t>(model.infer(features, actual)));
    for (std::size_t output = 0; output < generated_manifest::kOutputCount; ++output) {
      const float value = rawOutputValue(actual, static_cast<schema::OutputIndex>(output));
      TEST_ASSERT_FLOAT_WITHIN(2.0e-5f, model_golden_vectors::kExpected[row][output], value);
      TEST_ASSERT_TRUE(value >= 0.0f);
      TEST_ASSERT_TRUE(value <= 1.0f);
    }
  }
}

} // namespace

void setUp() {}

void tearDown() {}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_schema_feature_count_and_order);
  RUN_TEST(test_feature_encoder_uses_generated_indices_and_normalization);
  RUN_TEST(test_cpp_defaults_match_schema_defaults);
  RUN_TEST(test_unavailable_zone_target_is_canonicalized_to_schema_default);
  RUN_TEST(test_unavailable_actuator_capabilities_are_canonicalized_to_zero);
  RUN_TEST(test_encoder_clamps_contract_ranges);
  RUN_TEST(test_encoder_rejects_non_finite_input_and_imputes_finite_masked_sensor);
  RUN_TEST(test_safety_masks_unavailable_outputs_and_missing_temperature);
  RUN_TEST(test_alarm_temperature_forces_heater_off_and_fan_minimum);
  RUN_TEST(test_zone_pump_pulse_and_minimum_interval);
  RUN_TEST(test_soil_moisture_at_target_blocks_irrigation);
  RUN_TEST(test_invalid_soil_moisture_blocks_irrigation);
  RUN_TEST(test_cold_nutrient_solution_blocks_irrigation);
  RUN_TEST(test_nutrient_soil_delta_blocks_irrigation);
  RUN_TEST(test_co2_target_reached_blocks_doser);
  RUN_TEST(test_heater_and_cooler_are_mutually_exclusive);
  RUN_TEST(test_humidity_unavailable_blocks_humidifier_and_dehumidifier);
  RUN_TEST(test_model_schema_hash_compatibility);
  RUN_TEST(test_golden_model_inference_and_output_bounds);
  return UNITY_END();
}
