from pathlib import Path

ROOT = Path.cwd()

header = r'''#pragma once

#include "ClimateActuatorStateEstimator.h"
#include "ClimateFeatureEncoder.h"
#include "ClimateTrendEstimator.h"
#include "ClimateTypes.h"

#include <cstdint>

namespace growbox::climate {

enum class ClimatePolicyMode : std::uint8_t { Rule = 0U, MlShadow = 1U, MlActive = 2U };

enum class ClimateRuntimeStatus : std::uint8_t {
  Ok = 0U,
  MlProviderMissing,
  MlInferenceFailed,
  MlActiveNotAllowed,
};

enum ClimateIntervention : std::uint32_t {
  InterventionNone = 0U,
  UnavailableHeater = 1U << 0U,
  UnavailableCooler = 1U << 1U,
  UnavailableExhaustFan = 1U << 2U,
  UnavailableHumidifier = 1U << 3U,
  UnavailableDehumidifier = 1U << 4U,
  UnavailableCo2Doser = 1U << 5U,
  OppositionHeaterCooler = 1U << 6U,
  OppositionHumidifierDehumidifier = 1U << 7U,
  RequiredSensorUnusable = 1U << 8U,
  Co2DosingInhibited = 1U << 9U,
  HighTemperature = 1U << 10U,
  LowTemperature = 1U << 11U,
  HighHumidity = 1U << 12U,
  HighCo2 = 1U << 13U,
};

struct ClimatePolicyEvaluation {
  ClimatePolicyRequest raw{};
  ClimatePolicyRequest arbitrated{};
  ClimatePolicyRequest safe{};
  std::uint32_t arbitration_interventions = InterventionNone;
  std::uint32_t safety_interventions = InterventionNone;
};

struct ClimateRuntimeConfig {
  ClimatePolicyMode mode = ClimatePolicyMode::Rule;
  std::uint64_t sensor_timeout_ms = kDefaultSensorTimeoutMs;
  float timestep_s = 10.0F;
  float ml_deadzone = 0.05F;
  bool allow_unqualified_ml_active = false;
};

class ClimateInferenceProvider {
public:
  virtual ~ClimateInferenceProvider() = default;
  virtual bool infer(const ClimateFeatureVector& features, ClimatePolicyRequest& output) noexcept = 0;
};

struct ClimateRuntimeDecision {
  ClimateRuntimeStatus status = ClimateRuntimeStatus::Ok;
  ClimatePolicyMode mode = ClimatePolicyMode::Rule;
  bool authoritative_ml = false;
  bool ml_evaluated = false;
  ClimatePolicyEvaluation rule{};
  ClimatePolicyEvaluation ml{};
  ClimateFeatureVector ml_features{};
  ClimateEncoderReport encoder_report{};
  ClimateTrends trends{};
  EstimatedEffectiveClimateActions effective_before{};
  ClimatePolicyRequest applied{};
  EstimatedEffectiveClimateActions effective_after{};
};

class ClimateRuntimeController {
public:
  explicit ClimateRuntimeController(ClimateInferenceProvider* ml_provider = nullptr,
                                    ClimateRuntimeConfig config = {}) noexcept;

  ClimateRuntimeStatus step(const ClimateControllerInput& input, std::uint64_t monotonic_ms,
                            ClimateRuntimeDecision& decision) noexcept;
  void reset() noexcept;

private:
  ClimateInferenceProvider* ml_provider_ = nullptr;
  ClimateRuntimeConfig config_{};
  ClimateTrendEstimator trend_estimator_{};
  ClimateActuatorStateEstimator effective_estimator_{};
};

} // namespace growbox::climate
'''

source = r'''#include "ClimateRuntimeController.h"

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
    const float mixed_temp_score = std::abs(mixed_temperature - input.targets.air_temperature_c) / 5.0F;
    float current_humidity_error = humidity - input.targets.relative_humidity_pct;
    float mixed_humidity_error = mixed_humidity - input.targets.relative_humidity_pct;
    float humidity_scale = 20.0F;
    if (input.humidity_control_mode == HumidityControlMode::Vpd) {
      current_humidity_error = airVpdKpa(temperature, humidity) - input.targets.air_vpd_kpa;
      mixed_humidity_error =
          airVpdKpa(mixed_temperature, mixed_humidity) - input.targets.air_vpd_kpa;
      humidity_scale = 0.7F;
    }
    const float current_score = current_temp_score + std::abs(current_humidity_error) / humidity_scale;
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

ClimatePolicyRequest arbitrate(const ClimatePolicyRequest& raw, const ClimateCapabilities& capabilities,
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

ClimatePolicyRequest safety(const ClimatePolicyRequest& arbitrated, const ClimateControllerInput& input,
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
  evaluation.arbitrated = arbitrate(evaluation.raw, input.capabilities,
                                    evaluation.arbitration_interventions);
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

void ClimateRuntimeController::reset() noexcept {
  trend_estimator_.reset();
  effective_estimator_.reset();
}

} // namespace growbox::climate
'''

runtime_tests = r'''

class FixedMlProvider final : public growbox::climate::ClimateInferenceProvider {
public:
  explicit FixedMlProvider(growbox::climate::ClimatePolicyRequest request, bool succeeds = true)
      : request_(request), succeeds_(succeeds) {}
  bool infer(const growbox::climate::ClimateFeatureVector&,
             growbox::climate::ClimatePolicyRequest& output) noexcept override {
    ++calls;
    output = request_;
    return succeeds_;
  }
  int calls = 0;

private:
  growbox::climate::ClimatePolicyRequest request_{};
  bool succeeds_ = true;
};

growbox::climate::ClimateControllerInput runtimeInput() {
  using namespace growbox::climate;
  ClimateControllerInput input{};
  input.state.measurements.air_temperature_c = {18.0F, true, 0U};
  input.state.measurements.relative_humidity_pct = {60.0F, true, 0U};
  input.state.measurements.co2_ppm = {500.0F, true, 0U};
  input.state.measurements.outside_temperature_c = {10.0F, true, 0U};
  input.state.measurements.outside_humidity_pct = {50.0F, true, 0U};
  input.targets.air_temperature_c = 24.0F;
  input.targets.relative_humidity_pct = 60.0F;
  input.targets.co2_enabled = true;
  input.targets.co2_ppm = 950.0F;
  input.capabilities.heater = true;
  input.capabilities.cooler = true;
  input.capabilities.exhaust_fan = true;
  input.capabilities.humidifier = true;
  input.capabilities.dehumidifier = true;
  input.capabilities.co2_doser = true;
  return input;
}

bool nearRequest(const growbox::climate::ClimatePolicyRequest& left,
                 const growbox::climate::ClimatePolicyRequest& right, float tolerance = 0.0001F) {
  return near(left.heater, right.heater, tolerance) && near(left.cooler, right.cooler, tolerance) &&
         near(left.exhaust_fan, right.exhaust_fan, tolerance) &&
         near(left.humidifier, right.humidifier, tolerance) &&
         near(left.dehumidifier, right.dehumidifier, tolerance) &&
         near(left.co2_doser, right.co2_doser, tolerance);
}

void runtimePolicyModeTest() {
  using namespace growbox::climate;
  const auto input = runtimeInput();
  ClimateRuntimeDecision decision{};
  ClimateRuntimeController rule{};
  check(rule.step(input, 0U, decision) == ClimateRuntimeStatus::Ok, "runtime rule status");
  check(!decision.authoritative_ml && !decision.ml_evaluated, "runtime rule authority");
  check(nearRequest(decision.applied, decision.rule.safe), "runtime rule applied");
  check(decision.applied.heater > 0.0F, "runtime rule heating");
  check(decision.effective_after.heater > 0.0F, "runtime effective state advances from applied");

  ClimatePolicyRequest ml_request{};
  ml_request.cooler = 0.8F;
  ml_request.heater = 0.2F;
  FixedMlProvider shadow_provider{ml_request};
  ClimateRuntimeConfig shadow_cfg{};
  shadow_cfg.mode = ClimatePolicyMode::MlShadow;
  ClimateRuntimeController shadow{&shadow_provider, shadow_cfg};
  check(shadow.step(input, 0U, decision) == ClimateRuntimeStatus::Ok, "runtime shadow status");
  check(decision.ml_evaluated && !decision.authoritative_ml, "runtime shadow diagnostic only");
  check(nearRequest(decision.applied, decision.rule.safe), "runtime shadow cannot affect applied");
  check(decision.ml.arbitrated.heater == 0.0F && decision.ml.arbitrated.cooler > 0.0F,
        "runtime ML opposition arbitration");
  check((decision.ml.arbitration_interventions & OppositionHeaterCooler) != 0U,
        "runtime ML opposition reason");

  ClimateRuntimeConfig blocked_cfg{};
  blocked_cfg.mode = ClimatePolicyMode::MlActive;
  FixedMlProvider blocked_provider{ml_request};
  ClimateRuntimeController blocked{&blocked_provider, blocked_cfg};
  check(blocked.step(input, 0U, decision) == ClimateRuntimeStatus::MlActiveNotAllowed,
        "runtime ML active opt-in gate");
  check(!decision.authoritative_ml && blocked_provider.calls == 0, "runtime blocked active uses rule");
  check(nearRequest(decision.applied, decision.rule.safe), "runtime blocked active applied rule");

  ClimateRuntimeConfig active_cfg{};
  active_cfg.mode = ClimatePolicyMode::MlActive;
  active_cfg.allow_unqualified_ml_active = true;
  FixedMlProvider active_provider{ml_request};
  ClimateRuntimeController active{&active_provider, active_cfg};
  check(active.step(input, 0U, decision) == ClimateRuntimeStatus::Ok, "runtime active status");
  check(decision.authoritative_ml && decision.ml_evaluated, "runtime active authority");
  check(nearRequest(decision.applied, decision.ml.safe), "runtime active applies safe ML only");

  FixedMlProvider failing_provider{ml_request, false};
  ClimateRuntimeController failing{&failing_provider, shadow_cfg};
  check(failing.step(input, 0U, decision) == ClimateRuntimeStatus::MlInferenceFailed,
        "runtime ML failure status");
  check(!decision.authoritative_ml && !decision.ml_evaluated, "runtime ML failure falls back rule");
  check(nearRequest(decision.applied, decision.rule.safe), "runtime ML failure applied rule");
}

void runtimeSafetyTest() {
  using namespace growbox::climate;
  auto input = runtimeInput();
  input.state.measurements.air_temperature_c.valid = false;
  ClimateRuntimeDecision decision{};
  ClimateRuntimeController controller{};
  controller.step(input, 0U, decision);
  check(!anyActiveForTest(decision.applied), "runtime unusable required sensor safe off");

  input = runtimeInput();
  input.state.measurements.air_temperature_c.value = 45.0F;
  controller.reset();
  controller.step(input, 0U, decision);
  check(decision.applied.heater == 0.0F && decision.applied.cooler == 1.0F &&
            decision.applied.exhaust_fan == 1.0F,
        "runtime high temperature safety override");
}
'''

# Insert files.
(ROOT / "lib/environment_control/src/climate/ClimateRuntimeController.h").write_text(header, encoding="utf-8")
(ROOT / "lib/environment_control/src/climate/ClimateRuntimeController.cpp").write_text(source, encoding="utf-8")

# Extend existing host test file with runtime tests.
test_path = ROOT / "test/test_climate_v6/test_main.cpp"
test = test_path.read_text(encoding="utf-8")
test = test.replace('#include "ClimateMath.h"\n', '#include "ClimateMath.h"\n#include "ClimateRuntimeController.h"\n')
helper = r'''
bool anyActiveForTest(const growbox::climate::ClimatePolicyRequest& request) {
  return request.heater > 0.0F || request.cooler > 0.0F || request.exhaust_fan > 0.0F ||
         request.humidifier > 0.0F || request.dehumidifier > 0.0F || request.co2_doser > 0.0F;
}
'''
test = test.replace('void contractTest() {', helper + '\nvoid contractTest() {', 1)
test = test.replace('\n} // namespace\nint main() {', runtime_tests + '\n} // namespace\nint main() {', 1)
test = test.replace('  trendTest();\n', '  trendTest();\n  runtimePolicyModeTest();\n  runtimeSafetyTest();\n', 1)
test_path.write_text(test, encoding="utf-8")

# Add runtime implementation to climate_v6_tests target.
cmake_path = ROOT / "test/host/CMakeLists.txt"
cmake = cmake_path.read_text(encoding="utf-8")
needle = '  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateFeatureEncoder.cpp"\n'
replacement = needle + '  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateRuntimeController.cpp"\n'
if replacement not in cmake:
    cmake = cmake.replace(needle, replacement, 1)
cmake_path.write_text(cmake, encoding="utf-8")
