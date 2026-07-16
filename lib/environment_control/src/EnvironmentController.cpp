#include "EnvironmentController.h"

#include <algorithm>
#include <cmath>

namespace growbox {
namespace control {
namespace {

SafetyReason modelFailureReason(ModelStatus status) noexcept {
  switch (status) {
  case ModelStatus::SchemaMismatch:
  case ModelStatus::ShapeMismatch:
    return SafetyReason::SchemaMismatch;
  case ModelStatus::NonFiniteOutput:
    return SafetyReason::NonFiniteModelOutput;
  case ModelStatus::Ok:
    return SafetyReason::None;
  case ModelStatus::NonFiniteInput:
  case ModelStatus::InferenceFailure:
    return SafetyReason::ModelFailure;
  }
  return SafetyReason::ModelFailure;
}

float clamp01(float value) noexcept {
  return std::max(0.0f, std::min(1.0f, value));
}

// Soft MLP outputs often land just below binary_threshold even when residual is clear.
// Lift those mid-range proposals to the threshold so safety binary dwell can engage.
// Safety still owns hard limits (overtemp, unavailable, mutual exclusion).
void sharpenBinaryProposals(const ControllerInput& input, RawModelDecision& raw) noexcept {
  if (!std::isfinite(input.safety.binary_threshold)) {
    return;
  }
  const float thr = clamp01(input.safety.binary_threshold);
  if (thr <= 0.0f) {
    return;
  }
  // Soft floor: mid-range model votes with clear residual lift to thr.
  // Severe residual uses a lower floor so weak but non-zero MLP output still acts.
  const float soft = thr * 0.2f;
  const float soft_severe = thr * 0.04f;

  auto lift = [&](float& channel, bool need_on, bool severe) {
    if (!need_on) {
      return;
    }
    const float floor = severe ? soft_severe : soft;
    if (std::isfinite(channel) && channel >= floor && channel < thr) {
      channel = thr;
    }
  };

  if (input.validity.air_temperature && std::isfinite(input.sensors.air_temperature_c) &&
      std::isfinite(input.targets.air_temperature_c)) {
    const float temp_err = input.targets.air_temperature_c - input.sensors.air_temperature_c;
    if (input.actuators.heater.available && input.actuators.heater.max_power_w > 0.0f) {
      lift(raw.heater, temp_err > 1.5f, temp_err > 4.0f);
    }
    if (input.actuators.cooler.available && input.actuators.cooler.max_cooling_w > 0.0f) {
      lift(raw.cooler, temp_err < -1.5f, temp_err < -4.0f);
    }
  }

  if (input.validity.air_humidity && std::isfinite(input.sensors.air_humidity_pct) &&
      std::isfinite(input.targets.air_humidity_pct)) {
    const float rh_err = input.targets.air_humidity_pct - input.sensors.air_humidity_pct;
    if (input.actuators.humidifier.available && input.actuators.humidifier.max_output_g_h > 0.0f) {
      lift(raw.humidifier, rh_err > 8.0f, rh_err > 15.0f);
    }
    if (input.actuators.dehumidifier.available &&
        input.actuators.dehumidifier.max_removal_g_h > 0.0f) {
      lift(raw.dehumidifier, rh_err < -8.0f, rh_err < -15.0f);
    }
  }

  if (input.validity.co2 && std::isfinite(input.sensors.co2_ppm) &&
      std::isfinite(input.targets.co2_ppm) && input.actuators.co2_doser.available &&
      input.actuators.co2_doser.dose_ppm_per_full_pulse > 0.0f) {
    const float co2_err = input.targets.co2_ppm - input.sensors.co2_ppm;
    lift(raw.co2_doser, co2_err > 50.0f, co2_err > 150.0f);
  }

  if (input.validity.nutrient_solution_temperature &&
      std::isfinite(input.sensors.nutrient_solution_temperature_c) &&
      std::isfinite(input.targets.nutrient_solution_temperature_c) &&
      input.actuators.nutrient_heater.available &&
      input.actuators.nutrient_heater.max_power_w > 0.0f) {
    const float n_err = input.targets.nutrient_solution_temperature_c -
                        input.sensors.nutrient_solution_temperature_c;
    lift(raw.nutrient_heater, n_err > 1.0f, n_err > 3.0f);
  }

  float* irrigation_channels[kMaxPots] = {&raw.irrigation_pot_1, &raw.irrigation_pot_2,
                                          &raw.irrigation_pot_3, &raw.irrigation_pot_4};
  float* heat_mat_channels[kMaxPots] = {&raw.heat_mat_pot_1, &raw.heat_mat_pot_2,
                                        &raw.heat_mat_pot_3, &raw.heat_mat_pot_4};
  for (std::size_t pot_index = 0; pot_index < kMaxPots; ++pot_index) {
    const PotConfig& pot = input.pots[pot_index];
    if (!pot.available) {
      continue;
    }
    if (pot.irrigation.available && pot.validity.soil_moisture &&
        std::isfinite(pot.sensors.soil_moisture_pct) &&
        std::isfinite(pot.target_soil_moisture_pct)) {
      const float soil_err = pot.target_soil_moisture_pct - pot.sensors.soil_moisture_pct;
      lift(*irrigation_channels[pot_index], soil_err > 5.0f, soil_err > 12.0f);
    }
    if (pot.heat_mat.available && pot.validity.soil_temperature &&
        std::isfinite(pot.sensors.soil_temperature_c) &&
        std::isfinite(pot.target_soil_temperature_c)) {
      const float soil_t_err = pot.target_soil_temperature_c - pot.sensors.soil_temperature_c;
      lift(*heat_mat_channels[pot_index], soil_t_err > 1.0f, soil_t_err > 3.0f);
    }
  }
}

} // namespace

ControllerStatus EnvironmentController::process(const ControllerInput& input,
                                                ControllerOutput& output) noexcept {
  output = ControllerOutput{};
  FeatureVector features{};
  output.diagnostics.encoder_status =
      FeatureEncoder::encode(input, features, output.diagnostics.encoder);
  if (output.diagnostics.encoder_status != EncoderStatus::Ok) {
    output.diagnostics.model_status = ModelStatus::NonFiniteInput;
    safety_.apply(input, output.raw, SafetyReason::NonFiniteInput, output.safe,
                  output.diagnostics.safety);
    return ControllerStatus::EncoderError;
  }

  output.diagnostics.model_status = model_.infer(features, output.raw);
  if (output.diagnostics.model_status != ModelStatus::Ok) {
    safety_.apply(input, output.raw, modelFailureReason(output.diagnostics.model_status),
                  output.safe, output.diagnostics.safety);
    return ControllerStatus::ModelError;
  }

  sharpenBinaryProposals(input, output.raw);
  safety_.apply(input, output.raw, SafetyReason::None, output.safe, output.diagnostics.safety);
  return ControllerStatus::Ok;
}

void EnvironmentController::resetSafetyState() noexcept {
  safety_.reset();
}

const ModelRuntime& EnvironmentController::modelRuntime() const noexcept {
  return model_;
}

} // namespace control
} // namespace growbox
