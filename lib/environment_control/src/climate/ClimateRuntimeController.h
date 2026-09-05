#pragma once

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
  virtual bool infer(const ClimateFeatureVector& features,
                     ClimatePolicyRequest& output) noexcept = 0;
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

  // Reconcile a decision after the actuator sink reports the levels that were
  // actually accepted. This rewinds the estimator to effective_before and
  // advances it with the confirmed physical command instead of the proposal.
  void reconcileApplied(const ClimatePolicyRequest& confirmed_applied,
                        const ClimateCapabilities& capabilities,
                        ClimateRuntimeDecision& decision) noexcept;

  void reset() noexcept;

private:
  ClimateInferenceProvider* ml_provider_ = nullptr;
  ClimateRuntimeConfig config_{};
  ClimateTrendEstimator trend_estimator_{};
  ClimateActuatorStateEstimator effective_estimator_{};
};

} // namespace growbox::climate
