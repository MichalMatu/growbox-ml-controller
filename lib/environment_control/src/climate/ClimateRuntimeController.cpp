#include "ClimateRuntimeController.h"

#include "ClimateMath.h"

#include <algorithm>
#include <cmath>

namespace growbox::climate {
namespace {

constexpr float kTemperatureDeadbandC = 0.3F;
constexpr float kHumidityDeadbandPct = 2.0F;
constexpr float kVpdDeadbandKpa = 0.08F;
constexpr float kCo2DeadbandPpm = 50.0F;
constexpr float kTemperatureFullScaleC = 4.0F;
constexpr float kHumidityFullScalePct = 18.0F;
constexpr float kVpdFullScaleKpa = 0.7F;
constexpr float kCo2FullScalePpm = 500.0F;
constexpr float kOutsideImprovementMargin = 0.08F;
constexpr float kMinimumTemperatureC = 8.0F;
constexpr float kMaximumTemperatureC = 42.0F;
constexpr float kMaximumHumidityPct = 95.0F;
constexpr float kMaximumCo2Ppm = 1800.0F;

float clip01(float value) noexcept {
  if (!std::isfinite(value)) {
    return 0.0F;
  }
  return std::clamp(value, 0.0F, 1.0F);
}

bool usable(const MeasuredValue& value, std::uint64_t timeout_ms) noexcept {
  return value.valid && value.age_ms <= timeout_ms && std::isfinite(value.value);
}

float level(float error, float deadband, float full_scale) noexcept {
  const float excess = std::max(0.0F, std::abs(error) - deadband);
  return clip01(excess / std::max(1.0e-9F, full_scale));
}

bool anyActive(const ClimatePolicyRequest& request) noexcept {
  return request.heater > 0.0F || request.cooler > 0.0F || request.exhaust_fan > 0.0F ||
         request.humidifier > 0.0F || request.dehumidifier > 0.0F || request.co2_doser > 0.0F;
}

ClimatePolicyRequest clipped(const ClimatePolicyRequest& request) noexcept {
  ClimatePolicyRequest result{};
  result.heater = clip01(request.heater);
  result.cooler = clip01(request.cooler);
  result.exhaust_fan = clip01(request.exhaust_fan);
  result.humidifier = clip01(request.humidifier);
  result.dehumidifier = clip01(request.dehumidifier);
  result.co2_doser = clip01(request.co2_doser);
  return result;
}

ClimatePolicyRequest ruleRequest(const ClimateControllerInput& input) noexcept {
  ClimatePolicyRequest request{};
  const auto& measurements = input.state.measurements;
  if (!usable(measurements.air_temperature_c, input.sensor_timeout_ms) ||
      !usable(measurements.relative_humidity_pct, input.sensor_timeout_ms)) {
    return request;
  }

  const float temperature = measurements.air_temperature_c.value;
  const float humidity = measurements.relative_humidity_pct.value;
  const float temperature_error = temperature - input.targets.air_temperature_c;
  const float temperature_level =
      level(temperature_error, kTemperatureDeadbandC, kTemperatureFullScaleC);
  if (temperature_error < -kTemperatureDeadbandC && input.capabilities.heater) {
    request.heater = temperature_level;
  } else if (temperature_error > kTemperatureDeadbandC && input.capabilities.cooler) {
    request.cooler = temperature_level;
  }

  float humidity_error = humidity - input.targets.relative_humidity_pct;
  float humidity_deadband = kHumidityDeadbandPct;
  float humidity_full_scale = kHumidityFullScalePct;
  bool too_dry = humidity_error < -humidity_deadband;
  bool too_humid = humidity_error > humidity_deadband;
  if (input.humidity_control_mode == HumidityControlMode::Vpd) {
    humidity_error = airVpdKpa(temperature, humidity) - input.targets.air_vpd_kpa;
    humidity_deadband = kVpdDeadbandKpa;
    humidity_full_scale = kVpdFullScaleKpa;
    too_dry = humidity_error > humidity_deadband;
    too_humid = humidity_error < -humidity_deadband;
  }
  const float humidity_level = level(humidity_error, humidity_deadband, humidity_full_scale);
  if (too_dry && input.capabilities.humidifier) {
    request.humidifier = humidity_level;
  } else if (too_humid && input.capabilities.dehumidifier) {
    request.dehumidifier = humidity_level;
  }

  const bool outside_ok = usable(measurements.outside_temperature_c, input.sensor_timeout_ms) &&
                          usable(measurements.outside_humidity_pct, input.sensor_timeout_ms);
  if (outside_ok && input.capabilities.exhaust_fan) {
    constexpr float kMixFraction = 0.20F;
    const float mixed_temperature =
        temperature + kMixFraction * (measurements.outside_temperature_c.value - temperature);
    const float mixed_humidity =
        humidity + kMixFraction * (measurements.outside_humidity_pct.value - humidity);
    const float current_temp_score = std::abs(temperature_error) / 5.0F;
    const float mixed_temp_score =
        std::abs(mixed_temperature - input.targets.air_temperature_c) / 5.0F;
    float current_humidity_error = humidity - input.targets.relative_humidity_pct;
    float mixed_humidity_error = mixed_humidity - input.targets.relative_humidity_pct;
    float humidity_scale = 20.0F;
    if (input.humidity_control_mode == HumidityControlMode::Vpd) {
      current_humidity_error = airVpdKpa(temperature, humidity) - input.targets.air_vpd_kpa;
      mixed_humidity_error =
          airVpdKpa(mixed_temperature, mixed_humidity) - input.targets.air_vpd_kpa;
      humidity_scale = 0.7F;
    }
    const float current_score =
        current_temp_score + std::abs(current_humidity_error) / humidity_scale;
    const float mixed_score = mixed_temp_score + std::abs(mixed_humidity_error) / humidity_scale;
    const float improvement = current_score - mixed_score;
    if (improvement > kOutsideImprovementMargin) {
      request.exhaust_fan = clip01(improvement / 0.75F);
    }
  }

  if (input.targets.co2_enabled && input.capabilities.co2_doser &&
      usable(measurements.co2_ppm, input.sensor_timeout_ms)) {
    const float co2_error = input.targets.co2_ppm - measurements.co2_ppm.value;
    if (co2_error > kCo2DeadbandPpm) {
      request.co2_doser = level(co2_error, kCo2DeadbandPpm, kCo2FullScalePpm);
    }
  }
  return clipped(request);
}

ClimatePolicyRequest arbitrate(const ClimatePolicyRequest& raw,
                               const ClimateCapabilities& capabilities,
                               std::uint32_t& interventions) noexcept {
  ClimatePolicyRequest result = clipped(raw);
  interventions = InterventionNone;
  const auto maskUnavailable = [&](float& value, bool available, std::uint32_t reason) {
    if (!available && value > 0.0F) {
      value = 0.0F;
      interventions |= reason;
    }
  };
  maskUnavailable(result.heater, capabilities.heater, UnavailableHeater);
  maskUnavailable(result.cooler, capabilities.cooler, UnavailableCooler);
  maskUnavailable(result.exhaust_fan, capabilities.exhaust_fan, UnavailableExhaustFan);
  maskUnavailable(result.humidifier, capabilities.humidifier, UnavailableHumidifier);
  maskUnavailable(result.dehumidifier, capabilities.dehumidifier, UnavailableDehumidifier);
  maskUnavailable(result.co2_doser, capabilities.co2_doser, UnavailableCo2Doser);
  if (result.heater > 0.0F && result.cooler > 0.0F) {
    if (result.heater >= result.cooler) {
      result.cooler = 0.0F;
    } else {
      result.heater = 0.0F;
    }
    interventions |= OppositionHeaterCooler;
  }
  if (result.humidifier > 0.0F && result.dehumidifier > 0.0F) {
    if (result.humidifier >= result.dehumidifier) {
      result.dehumidifier = 0.0F;
    } else {
      result.humidifier = 0.0F;
    }
    interventions |= OppositionHumidifierDehumidifier;
  }
  return result;
}

ClimatePolicyRequest safety(const ClimatePolicyRequest& arbitrated,
                            const ClimateControllerInput& input,
                            std::uint32_t& interventions) noexcept {
  ClimatePolicyRequest result = clipped(arbitrated);
  interventions = InterventionNone;
  const auto& measurements = input.state.measurements;
  const bool temperature_ok = usable(measurements.air_temperature_c, input.sensor_timeout_ms);
  const bool humidity_ok = usable(measurements.relative_humidity_pct, input.sensor_timeout_ms);
  if (!temperature_ok || !humidity_ok) {
    if (anyActive(result)) {
      interventions |= RequiredSensorUnusable;
    }
    return {};
  }

  const bool co2_ok = usable(measurements.co2_ppm, input.sensor_timeout_ms);
  if ((!input.targets.co2_enabled || !co2_ok) && result.co2_doser > 0.0F) {
    result.co2_doser = 0.0F;
    interventions |= Co2DosingInhibited;
  }

  const float temperature = measurements.air_temperature_c.value;
  if (temperature >= kMaximumTemperatureC) {
    if (result.heater > 0.0F || result.humidifier > 0.0F || result.co2_doser > 0.0F) {
      interventions |= HighTemperature;
    }
    result.heater = 0.0F;
    result.humidifier = 0.0F;
    result.co2_doser = 0.0F;
    result.cooler = input.capabilities.cooler ? 1.0F : 0.0F;
    result.exhaust_fan = input.capabilities.exhaust_fan ? 1.0F : 0.0F;
  } else if (temperature <= kMinimumTemperatureC) {
    if (result.cooler > 0.0F || result.exhaust_fan > 0.0F) {
      interventions |= LowTemperature;
    }
    result.cooler = 0.0F;
    result.exhaust_fan = 0.0F;
    result.heater = input.capabilities.heater ? 1.0F : 0.0F;
  }

  if (measurements.relative_humidity_pct.value >= kMaximumHumidityPct) {
    if (result.humidifier > 0.0F) {
      interventions |= HighHumidity;
    }
    result.humidifier = 0.0F;
    result.dehumidifier = input.capabilities.dehumidifier ? 1.0F : 0.0F;
    result.co2_doser = 0.0F;
  }

  if (co2_ok && measurements.co2_ppm.value >= kMaximumCo2Ppm) {
    if (result.co2_doser > 0.0F) {
      interventions |= HighCo2;
    }
    result.co2_doser = 0.0F;
    if (input.capabilities.exhaust_fan) {
      result.exhaust_fan = 1.0F;
    }
  }
  return clipped(result);
}

void evaluate(const ClimatePolicyRequest& raw, const ClimateControllerInput& input,
              ClimatePolicyEvaluation& evaluation) noexcept {
  evaluation.raw = clipped(raw);
  evaluation.arbitrated =
      arbitrate(evaluation.raw, input.capabilities, evaluation.arbitration_interventions);
  evaluation.safe = safety(evaluation.arbitrated, input, evaluation.safety_interventions);
}

bool finiteRequest(const ClimatePolicyRequest& request) noexcept {
  return std::isfinite(request.heater) && std::isfinite(request.cooler) &&
         std::isfinite(request.exhaust_fan) && std::isfinite(request.humidifier) &&
         std::isfinite(request.dehumidifier) && std::isfinite(request.co2_doser);
}

ClimatePolicyRequest applyDeadzone(const ClimatePolicyRequest& raw, float threshold) noexcept {
  ClimatePolicyRequest result = clipped(raw);
  const float deadzone = std::clamp(std::isfinite(threshold) ? threshold : 0.05F, 0.0F, 0.999F);
  const auto zeroSmall = [deadzone](float& value) {
    if (value <= deadzone) {
      value = 0.0F;
    }
  };
  zeroSmall(result.heater);
  zeroSmall(result.cooler);
  zeroSmall(result.exhaust_fan);
  zeroSmall(result.humidifier);
  zeroSmall(result.dehumidifier);
  zeroSmall(result.co2_doser);
  return result;
}

} // namespace

ClimateRuntimeController::ClimateRuntimeController(ClimateInferenceProvider* ml_provider,
                                                   ClimateRuntimeConfig config) noexcept
    : ml_provider_(ml_provider), config_(config) {}

ClimateRuntimeStatus ClimateRuntimeController::step(const ClimateControllerInput& input,
                                                    std::uint64_t monotonic_ms,
                                                    ClimateRuntimeDecision& decision) noexcept {
  decision = {};
  decision.mode = config_.mode;

  ClimateControllerInput runtime_input = input;
  runtime_input.sensor_timeout_ms = config_.sensor_timeout_ms;
  decision.trends = trend_estimator_.update(runtime_input.state.measurements, monotonic_ms,
                                            config_.sensor_timeout_ms);
  runtime_input.state.trends = decision.trends;
  decision.effective_before = effective_estimator_.state();
  runtime_input.estimated_effective = decision.effective_before;

  evaluate(ruleRequest(runtime_input), runtime_input, decision.rule);
  decision.applied = decision.rule.safe;

  if (config_.mode == ClimatePolicyMode::MlActive && !config_.allow_unqualified_ml_active) {
    decision.status = ClimateRuntimeStatus::MlActiveNotAllowed;
  } else if (config_.mode != ClimatePolicyMode::Rule) {
    if (ml_provider_ == nullptr) {
      decision.status = ClimateRuntimeStatus::MlProviderMissing;
    } else {
      decision.ml_features = ClimateFeatureEncoder::encode(runtime_input, &decision.encoder_report);
      ClimatePolicyRequest ml_raw{};
      if (!ml_provider_->infer(decision.ml_features, ml_raw) || !finiteRequest(ml_raw)) {
        decision.status = ClimateRuntimeStatus::MlInferenceFailed;
      } else {
        decision.ml_evaluated = true;
        evaluate(applyDeadzone(ml_raw, config_.ml_deadzone), runtime_input, decision.ml);
        if (config_.mode == ClimatePolicyMode::MlActive) {
          decision.authoritative_ml = true;
          decision.applied = decision.ml.safe;
        }
      }
    }
  }

  const float timestep =
      std::isfinite(config_.timestep_s) && config_.timestep_s > 0.0F ? config_.timestep_s : 10.0F;
  decision.effective_after =
      effective_estimator_.update(decision.applied, timestep, runtime_input.capabilities);
  return decision.status;
}

void ClimateRuntimeController::reconcileApplied(const ClimatePolicyRequest& confirmed_applied,
                                                const ClimateCapabilities& capabilities,
                                                ClimateRuntimeDecision& decision) noexcept {
  const float timestep =
      std::isfinite(config_.timestep_s) && config_.timestep_s > 0.0F ? config_.timestep_s : 10.0F;
  effective_estimator_.setState(decision.effective_before);
  decision.applied = clipped(confirmed_applied);
  decision.effective_after = effective_estimator_.update(decision.applied, timestep, capabilities);
}

void ClimateRuntimeController::reset() noexcept {
  trend_estimator_.reset();
  effective_estimator_.reset();
}

} // namespace growbox::climate
