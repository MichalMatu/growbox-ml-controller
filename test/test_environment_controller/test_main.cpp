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

ControllerInput nominalInput() {
  ControllerInput input{};
  input.validity = SensorValidity{true, true, true, true, true, true};
  input.actuators.heater.available = true;
  input.actuators.heater.max_power_w = 250.0f;
  input.actuators.heater.efficiency = 0.9f;
  input.actuators.heater.control_type = ActuatorControlType::Binary;
  input.actuators.fan.available = true;
  input.actuators.fan.max_airflow_m3_h = 120.0f;
  input.actuators.fan.minimum_command = 0.15f;
  input.actuators.fan.control_type = ActuatorControlType::Pwm;
  input.actuators.humidifier.available = true;
  input.actuators.humidifier.max_output_g_h = 250.0f;
  input.actuators.humidifier.control_type = ActuatorControlType::Binary;
  input.actuators.irrigation_pump.available = true;
  input.actuators.irrigation_pump.flow_ml_s = 20.0f;
  input.actuators.irrigation_pump.maximum_pulse_s = 15.0f;
  input.actuators.irrigation_pump.minimum_interval_s = 3600.0f;
  input.actuators.irrigation_pump.control_type = ActuatorControlType::Binary;
  input.monotonic_time_ms = 100000U;
  return input;
}

bool hasReason(std::uint32_t mask, SafetyReason reason) {
  return (mask & reasonBit(reason)) != 0U;
}

void assertDecisionInRange(const SafeControlDecision& decision) {
  TEST_ASSERT_TRUE(decision.heater >= 0.0f);
  TEST_ASSERT_TRUE(decision.heater <= 1.0f);
  TEST_ASSERT_TRUE(decision.fan >= 0.0f);
  TEST_ASSERT_TRUE(decision.fan <= 1.0f);
  TEST_ASSERT_TRUE(decision.humidifier >= 0.0f);
  TEST_ASSERT_TRUE(decision.humidifier <= 1.0f);
  TEST_ASSERT_TRUE(decision.irrigation >= 0.0f);
  TEST_ASSERT_TRUE(decision.irrigation <= 1.0f);
}

void test_schema_feature_count_and_order() {
  TEST_ASSERT_EQUAL_UINT32(1U, schema::kSchemaVersion);
  TEST_ASSERT_EQUAL_UINT32(43U, schema::kFeatureCount);
  TEST_ASSERT_EQUAL_UINT32(4U, schema::kOutputCount);
  TEST_ASSERT_EQUAL_STRING("air_temperature_c", schema::kFeatureNames[0]);
  TEST_ASSERT_EQUAL_STRING("air_temperature_valid", schema::kFeatureNames[6]);
  TEST_ASSERT_EQUAL_STRING("heater_available", schema::kFeatureNames[19]);
  TEST_ASSERT_EQUAL_STRING("fan_control_type", schema::kFeatureNames[26]);
  TEST_ASSERT_EQUAL_STRING("target_air_temperature_c", schema::kFeatureNames[35]);
  TEST_ASSERT_EQUAL_STRING("previous_irrigation", schema::kFeatureNames[42]);
  TEST_ASSERT_EQUAL_STRING("sensors.air_temperature_c", schema::kFeaturePaths[0]);
  TEST_ASSERT_EQUAL_STRING("validity.air_temperature_c", schema::kFeaturePaths[6]);
  TEST_ASSERT_EQUAL_STRING("actuators.heater.available", schema::kFeaturePaths[19]);
  TEST_ASSERT_EQUAL_STRING("actuators.fan.control_type", schema::kFeaturePaths[26]);
  TEST_ASSERT_EQUAL_STRING("targets.air_temperature_c", schema::kFeaturePaths[35]);
  TEST_ASSERT_EQUAL_STRING("previous.irrigation", schema::kFeaturePaths[42]);
  TEST_ASSERT_EQUAL_STRING("available", schema::wireKey(schema::FeatureIndex::HeaterAvailable));
  TEST_ASSERT_EQUAL_STRING("control_type",
                           schema::wireKey(schema::FeatureIndex::HeaterControlType));
  TEST_ASSERT_EQUAL_STRING("irrigation", schema::kOutputNames[3]);
}

void test_feature_encoder_uses_generated_indices_and_normalization() {
  ControllerInput input = nominalInput();
  input.sensors.air_temperature_c = 20.0f;
  input.sensors.air_humidity_pct = 25.0f;
  input.actuators.heater.control_type = ActuatorControlType::Pwm;
  FeatureVector features{};
  EncoderReport report{};

  TEST_ASSERT_EQUAL_UINT8(
      static_cast<std::uint8_t>(EncoderStatus::Ok),
      static_cast<std::uint8_t>(FeatureEncoder::encode(input, features, report)));
  TEST_ASSERT_FLOAT_WITHIN(1.0e-6f, 0.5f,
                           features.values[schema::index(schema::FeatureIndex::AirTemperatureC)]);
  TEST_ASSERT_FLOAT_WITHIN(1.0e-6f, 0.25f,
                           features.values[schema::index(schema::FeatureIndex::AirHumidityPct)]);
  TEST_ASSERT_FLOAT_WITHIN(
      0.0f, 1.0f, features.values[schema::index(schema::FeatureIndex::AirTemperatureValid)]);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 1.0f,
                           features.values[schema::index(schema::FeatureIndex::HeaterControlType)]);
  TEST_ASSERT_EQUAL_UINT64(0U, report.clamped_feature_mask);
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

void test_unavailable_actuator_capabilities_are_canonicalized_to_zero() {
  ControllerInput input = nominalInput();
  input.actuators.heater.available = false;
  input.actuators.heater.max_power_w = 500.0f;
  input.actuators.heater.efficiency = 0.9f;
  input.actuators.heater.control_type = ActuatorControlType::Pwm;
  input.actuators.fan.available = false;
  input.actuators.fan.max_airflow_m3_h = 200.0f;
  input.actuators.fan.minimum_command = 0.2f;
  input.actuators.irrigation_pump.available = false;
  input.actuators.irrigation_pump.flow_ml_s = 20.0f;
  input.actuators.irrigation_pump.maximum_pulse_s = 30.0f;
  input.actuators.irrigation_pump.minimum_interval_s = 100.0f;
  FeatureVector features{};
  EncoderReport report{};

  TEST_ASSERT_EQUAL_UINT8(
      static_cast<std::uint8_t>(EncoderStatus::Ok),
      static_cast<std::uint8_t>(FeatureEncoder::encode(input, features, report)));
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f,
                           features.values[schema::index(schema::FeatureIndex::HeaterAvailable)]);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f,
                           features.values[schema::index(schema::FeatureIndex::HeaterMaxPowerW)]);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f,
                           features.values[schema::index(schema::FeatureIndex::FanMaxAirflowM3H)]);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f,
                           features.values[schema::index(schema::FeatureIndex::IrrigationFlowMlS)]);
  TEST_ASSERT_FLOAT_WITHIN(
      0.0f, 0.0f, features.values[schema::index(schema::FeatureIndex::IrrigationMaximumPulseS)]);
  TEST_ASSERT_NOT_EQUAL(0U, report.substituted_feature_mask);
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
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 1.0f,
                           features.values[schema::index(schema::FeatureIndex::AirTemperatureC)]);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f,
                           features.values[schema::index(schema::FeatureIndex::AirHumidityPct)]);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 1.0f,
                           features.values[schema::index(schema::FeatureIndex::PreviousFan)]);
  TEST_ASSERT_NOT_EQUAL(0U, report.clamped_feature_mask);
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
  TEST_ASSERT_EQUAL_UINT8(
      static_cast<std::uint8_t>(EncoderStatus::NonFiniteInput),
      static_cast<std::uint8_t>(FeatureEncoder::encode(input, features, report)));

  input.sensors.air_temperature_c = 200.0f;
  TEST_ASSERT_EQUAL_UINT8(
      static_cast<std::uint8_t>(EncoderStatus::Ok),
      static_cast<std::uint8_t>(FeatureEncoder::encode(input, features, report)));
  TEST_ASSERT_FLOAT_WITHIN(
      0.0f, 0.0f, features.values[schema::index(schema::FeatureIndex::AirTemperatureValid)]);
  TEST_ASSERT_FLOAT_WITHIN(1.0e-6f, 0.55f,
                           features.values[schema::index(schema::FeatureIndex::AirTemperatureC)]);

  input.environment.thermal_mass_j_per_k = std::numeric_limits<float>::infinity();
  TEST_ASSERT_EQUAL_UINT8(
      static_cast<std::uint8_t>(EncoderStatus::NonFiniteInput),
      static_cast<std::uint8_t>(FeatureEncoder::encode(input, features, report)));
}

void test_safety_masks_unavailable_outputs_and_missing_temperature() {
  ControllerInput input{};
  input.validity.air_temperature = false;
  RawModelDecision raw{1.0f, 1.0f, 1.0f, 1.0f};
  SafeControlDecision safe{};
  SafetyReport report{};
  SafetySupervisor supervisor{};

  supervisor.apply(input, raw, SafetyReason::None, safe, report);
  assertDecisionInRange(safe);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f, safe.heater);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f, safe.fan);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f, safe.humidifier);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f, safe.irrigation);
  TEST_ASSERT_TRUE(report.modified);
  TEST_ASSERT_TRUE(hasReason(report.reason_mask, SafetyReason::ActuatorUnavailable));
  TEST_ASSERT_TRUE(hasReason(report.reason_mask, SafetyReason::TemperatureUnavailable));
}

void test_safety_rejects_nan_and_infinity() {
  ControllerInput input = nominalInput();
  RawModelDecision raw{std::numeric_limits<float>::quiet_NaN(),
                       std::numeric_limits<float>::infinity(), 0.2f, 0.3f};
  SafeControlDecision safe{};
  SafetyReport report{};
  SafetySupervisor supervisor{};

  supervisor.apply(input, raw, SafetyReason::None, safe, report);
  assertDecisionInRange(safe);
  TEST_ASSERT_TRUE(hasReason(report.reason_mask, SafetyReason::NonFiniteModelOutput));

  input.safety.binary_threshold = std::numeric_limits<float>::quiet_NaN();
  raw = RawModelDecision{1.0f, 1.0f, 1.0f, 1.0f};
  supervisor.apply(input, raw, SafetyReason::None, safe, report);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f, safe.heater);
  TEST_ASSERT_TRUE(hasReason(report.reason_mask, SafetyReason::NonFiniteInput));
}

void test_alarm_temperature_forces_heater_off_and_fan_minimum() {
  ControllerInput input = nominalInput();
  input.sensors.air_temperature_c = 36.0f;
  RawModelDecision raw{1.0f, 0.1f, 0.0f, 0.0f};
  SafeControlDecision safe{};
  SafetyReport report{};
  SafetySupervisor supervisor{};

  supervisor.apply(input, raw, SafetyReason::None, safe, report);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f, safe.heater);
  TEST_ASSERT_FLOAT_WITHIN(1.0e-6f, input.safety.alarm_minimum_fan, safe.fan);
  TEST_ASSERT_TRUE(hasReason(report.reason_mask, SafetyReason::OverTemperature));
  TEST_ASSERT_TRUE(hasReason(report.reason_mask, SafetyReason::TemperatureAlarmFan));
}

void test_pump_pulse_and_minimum_interval() {
  ControllerInput input = nominalInput();
  input.actuators.irrigation_pump.maximum_pulse_s = 10.0f;
  input.actuators.irrigation_pump.minimum_interval_s = 60.0f;
  RawModelDecision raw{0.0f, 0.0f, 0.0f, 2.0f};
  SafeControlDecision safe{};
  SafetyReport report{};
  SafetySupervisor supervisor{};

  supervisor.apply(input, raw, SafetyReason::None, safe, report);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 1.0f, safe.irrigation);
  TEST_ASSERT_FLOAT_WITHIN(1.0e-6f, 10.0f, safe.irrigation_pulse_s);
  TEST_ASSERT_TRUE(hasReason(report.reason_mask, SafetyReason::PumpPulseLimited));

  input.monotonic_time_ms += 1000U;
  raw.irrigation = 1.0f;
  supervisor.apply(input, raw, SafetyReason::None, safe, report);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f, safe.irrigation);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f, safe.irrigation_pulse_s);
  TEST_ASSERT_TRUE(hasReason(report.reason_mask, SafetyReason::PumpMinimumInterval));

  input.monotonic_time_ms += 60000U;
  supervisor.apply(input, raw, SafetyReason::None, safe, report);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 1.0f, safe.irrigation);

  supervisor.reset();
  input.monotonic_time_ms = 200000U;
  input.previous.irrigation = 1.0f;
  supervisor.apply(input, raw, SafetyReason::ModelFailure, safe, report);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f, safe.irrigation);
  input.previous.irrigation = 0.0f;
  input.monotonic_time_ms += 1000U;
  supervisor.apply(input, raw, SafetyReason::None, safe, report);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f, safe.irrigation);
  TEST_ASSERT_TRUE(hasReason(report.reason_mask, SafetyReason::PumpMinimumInterval));

  supervisor.reset();
  input.monotonic_time_ms = 300000U;
  input.actuators.irrigation_pump.maximum_pulse_s = 1000.0f;
  input.actuators.irrigation_pump.minimum_interval_s = 0.0f;
  supervisor.apply(input, raw, SafetyReason::None, safe, report);
  TEST_ASSERT_FLOAT_WITHIN(1.0e-6f, 600.0f, safe.irrigation_pulse_s);
  TEST_ASSERT_TRUE(hasReason(report.reason_mask, SafetyReason::PumpPulseLimited));
}

void test_invalid_heater_control_type_is_fail_safe() {
  ControllerInput input = nominalInput();
  input.actuators.heater.control_type = static_cast<ActuatorControlType>(255U);
  FeatureVector features{};
  EncoderReport encoder_report{};
  TEST_ASSERT_EQUAL_UINT8(
      static_cast<std::uint8_t>(EncoderStatus::Ok),
      static_cast<std::uint8_t>(FeatureEncoder::encode(input, features, encoder_report)));
  TEST_ASSERT_TRUE(
      (encoder_report.clamped_feature_mask &
       (std::uint64_t{1U} << schema::index(schema::FeatureIndex::HeaterControlType))) != 0U);

  SafetySupervisor supervisor{};
  SafeControlDecision safe{};
  SafetyReport report{};
  supervisor.apply(input, RawModelDecision{1.0f, 0.0f, 0.0f, 0.0f}, SafetyReason::None, safe,
                   report);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f, safe.heater);
  TEST_ASSERT_TRUE(hasReason(report.reason_mask, SafetyReason::InvalidCapability));
}

void test_binary_dwell_limits() {
  ControllerInput input = nominalInput();
  input.safety.heater_minimum_on_s = 30.0f;
  input.safety.heater_minimum_off_s = 30.0f;
  input.monotonic_time_ms = 0U;
  RawModelDecision raw{1.0f, 0.0f, 0.0f, 0.0f};
  SafeControlDecision safe{};
  SafetyReport report{};
  SafetySupervisor supervisor{};

  supervisor.apply(input, raw, SafetyReason::None, safe, report);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f, safe.heater);
  TEST_ASSERT_TRUE(hasReason(report.reason_mask, SafetyReason::BinaryMinimumOff));

  input.monotonic_time_ms = 30000U;
  supervisor.apply(input, raw, SafetyReason::None, safe, report);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 1.0f, safe.heater);

  input.monotonic_time_ms = 31000U;
  input.previous.heater = 1.0f;
  raw.heater = 0.0f;
  supervisor.apply(input, raw, SafetyReason::None, safe, report);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 1.0f, safe.heater);
  TEST_ASSERT_TRUE(hasReason(report.reason_mask, SafetyReason::BinaryMinimumOn));

  input.monotonic_time_ms = 60000U;
  supervisor.apply(input, raw, SafetyReason::None, safe, report);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f, safe.heater);

  input.monotonic_time_ms = 61000U;
  input.previous.heater = 0.0f;
  raw.heater = 1.0f;
  supervisor.apply(input, raw, SafetyReason::None, safe, report);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f, safe.heater);
  TEST_ASSERT_TRUE(hasReason(report.reason_mask, SafetyReason::BinaryMinimumOff));
}

void test_model_schema_hash_compatibility() {
  TEST_ASSERT_TRUE(ModelRuntime::isCompatible());
  TEST_ASSERT_TRUE(ModelRuntime::isSchemaCompatible(schema::kSchemaHash, schema::kFeatureCount,
                                                    schema::kOutputCount));
  TEST_ASSERT_FALSE(ModelRuntime::isSchemaCompatible("000000000000", schema::kFeatureCount,
                                                     schema::kOutputCount));
  TEST_ASSERT_FALSE(ModelRuntime::isSchemaCompatible(
      schema::kSchemaHash, schema::kFeatureCount - 1U, schema::kOutputCount));
  TEST_ASSERT_EQUAL_STRING(schema::kSchemaHash, model_golden_vectors::kSchemaHash);
  TEST_ASSERT_EQUAL_STRING(schema::kSchemaHash, generated_manifest::kSchemaHash);
  TEST_ASSERT_EQUAL_STRING(ModelRuntime::modelVersion(), generated_manifest::kModelVersion);
  TEST_ASSERT_EQUAL_UINT32(schema::kSchemaVersion, generated_manifest::kSchemaVersion);
  TEST_ASSERT_EQUAL_UINT32(schema::kFeatureCount, generated_manifest::kInputCount);
  TEST_ASSERT_EQUAL_UINT32(schema::kOutputCount, generated_manifest::kOutputCount);
}

void test_golden_model_inference_and_output_bounds() {
  ModelRuntime model{};
  for (std::size_t row = 0; row < model_golden_vectors::kVectorCount; ++row) {
    FeatureVector features{};
    features.values = model_golden_vectors::kFeatures[row];
    RawModelDecision actual{};
    TEST_ASSERT_EQUAL_UINT8(static_cast<std::uint8_t>(ModelStatus::Ok),
                            static_cast<std::uint8_t>(model.infer(features, actual)));
    const float values[] = {actual.heater, actual.fan, actual.humidifier, actual.irrigation};
    for (std::size_t output = 0; output < schema::kOutputCount; ++output) {
      TEST_ASSERT_FLOAT_WITHIN(2.0e-5f, model_golden_vectors::kExpected[row][output],
                               values[output]);
      TEST_ASSERT_TRUE(values[output] >= 0.0f);
      TEST_ASSERT_TRUE(values[output] <= 1.0f);
    }
  }
}

void test_controller_is_deterministic_after_reset() {
  ControllerInput input = nominalInput();
  EnvironmentController first{};
  EnvironmentController second{};
  ControllerOutput first_output{};
  ControllerOutput second_output{};

  TEST_ASSERT_EQUAL_UINT8(static_cast<std::uint8_t>(ControllerStatus::Ok),
                          static_cast<std::uint8_t>(first.process(input, first_output)));
  TEST_ASSERT_EQUAL_UINT8(static_cast<std::uint8_t>(ControllerStatus::Ok),
                          static_cast<std::uint8_t>(second.process(input, second_output)));
  TEST_ASSERT_FLOAT_WITHIN(0.0f, first_output.raw.heater, second_output.raw.heater);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, first_output.raw.fan, second_output.raw.fan);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, first_output.raw.humidifier, second_output.raw.humidifier);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, first_output.raw.irrigation, second_output.raw.irrigation);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, first_output.safe.heater, second_output.safe.heater);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, first_output.safe.fan, second_output.safe.fan);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, first_output.safe.humidifier, second_output.safe.humidifier);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, first_output.safe.irrigation, second_output.safe.irrigation);
  TEST_ASSERT_EQUAL_UINT32(first_output.diagnostics.safety.reason_mask,
                           second_output.diagnostics.safety.reason_mask);
  assertDecisionInRange(first_output.safe);
}

void test_controller_routes_encoder_failure_to_safe_state() {
  ControllerInput input = nominalInput();
  input.targets.co2_ppm = std::numeric_limits<float>::infinity();
  EnvironmentController controller{};
  ControllerOutput output{};

  TEST_ASSERT_EQUAL_UINT8(static_cast<std::uint8_t>(ControllerStatus::EncoderError),
                          static_cast<std::uint8_t>(controller.process(input, output)));
  TEST_ASSERT_EQUAL_UINT8(static_cast<std::uint8_t>(EncoderStatus::NonFiniteInput),
                          static_cast<std::uint8_t>(output.diagnostics.encoder_status));
  TEST_ASSERT_EQUAL_UINT8(static_cast<std::uint8_t>(ModelStatus::NonFiniteInput),
                          static_cast<std::uint8_t>(output.diagnostics.model_status));
  TEST_ASSERT_TRUE(hasReason(output.diagnostics.safety.reason_mask, SafetyReason::NonFiniteInput));
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f, output.safe.heater);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f, output.safe.fan);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f, output.safe.humidifier);
  TEST_ASSERT_FLOAT_WITHIN(0.0f, 0.0f, output.safe.irrigation);

  input.sensors.air_temperature_c = 36.0f;
  controller.resetSafetyState();
  TEST_ASSERT_EQUAL_UINT8(static_cast<std::uint8_t>(ControllerStatus::EncoderError),
                          static_cast<std::uint8_t>(controller.process(input, output)));
  TEST_ASSERT_FLOAT_WITHIN(1.0e-6f, input.safety.alarm_minimum_fan, output.safe.fan);
  TEST_ASSERT_TRUE(
      hasReason(output.diagnostics.safety.reason_mask, SafetyReason::TemperatureAlarmFan));
}

} // namespace

void setUp() {}

void tearDown() {}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_schema_feature_count_and_order);
  RUN_TEST(test_feature_encoder_uses_generated_indices_and_normalization);
  RUN_TEST(test_cpp_defaults_match_schema_defaults);
  RUN_TEST(test_unavailable_actuator_capabilities_are_canonicalized_to_zero);
  RUN_TEST(test_encoder_clamps_contract_ranges);
  RUN_TEST(test_encoder_rejects_non_finite_input_and_imputes_finite_masked_sensor);
  RUN_TEST(test_safety_masks_unavailable_outputs_and_missing_temperature);
  RUN_TEST(test_safety_rejects_nan_and_infinity);
  RUN_TEST(test_alarm_temperature_forces_heater_off_and_fan_minimum);
  RUN_TEST(test_pump_pulse_and_minimum_interval);
  RUN_TEST(test_invalid_heater_control_type_is_fail_safe);
  RUN_TEST(test_binary_dwell_limits);
  RUN_TEST(test_model_schema_hash_compatibility);
  RUN_TEST(test_golden_model_inference_and_output_bounds);
  RUN_TEST(test_controller_is_deterministic_after_reset);
  RUN_TEST(test_controller_routes_encoder_failure_to_safe_state);
  return UNITY_END();
}
