#include "ClimateRuntimeController.h"
#include "climate_runtime_parity_generated.h"

#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <iostream>

namespace {
int failures = 0;

void check(bool condition, const char* case_name, const char* message) {
  if (!condition) {
    ++failures;
    std::cerr << "FAIL [" << case_name << "]: " << message << '\n';
  }
}

bool near(float left, float right, float tolerance = 1.0e-4F) {
  return std::abs(left - right) <= tolerance;
}

std::array<float, 6> values(const growbox::climate::ClimatePolicyRequest& request) {
  return {request.heater,     request.cooler,       request.exhaust_fan,
          request.humidifier, request.dehumidifier, request.co2_doser};
}

std::array<float, 6> values(const growbox::climate::EstimatedEffectiveClimateActions& action) {
  return {action.heater,     action.cooler,       action.exhaust_fan,
          action.humidifier, action.dehumidifier, action.co2_doser};
}

template <std::size_t N>
void checkArray(const std::array<float, N>& actual, const std::array<float, N>& expected,
                const char* case_name, const char* message, float tolerance = 1.0e-4F) {
  for (std::size_t index = 0; index < N; ++index) {
    if (!near(actual[index], expected[index], tolerance)) {
      ++failures;
      std::cerr << "FAIL [" << case_name << "]: " << message << " index=" << index
                << " actual=" << actual[index] << " expected=" << expected[index] << '\n';
      return;
    }
  }
}

class FixtureProvider final : public growbox::climate::ClimateInferenceProvider {
public:
  explicit FixtureProvider(const growbox::climate::parity_fixture::Case& fixture)
      : fixture_(fixture) {}

  bool infer(const growbox::climate::ClimateFeatureVector&,
             growbox::climate::ClimatePolicyRequest& output) noexcept override {
    if (fixture_.model_behavior == growbox::climate::parity_fixture::ModelBehavior::Fail) {
      return false;
    }
    const auto& value = fixture_.model_output;
    output = {value[0], value[1], value[2], value[3], value[4], value[5]};
    return true;
  }

private:
  const growbox::climate::parity_fixture::Case& fixture_;
};

growbox::climate::ClimateControllerInput
makeInput(const growbox::climate::parity_fixture::Case& fixture) {
  using namespace growbox::climate;
  ClimateControllerInput input{};
  auto measured = [&](std::size_t index) {
    return MeasuredValue{fixture.measurement_values[index], fixture.measurement_valid[index],
                         fixture.measurement_age_ms[index]};
  };
  input.state.measurements.air_temperature_c = measured(0U);
  input.state.measurements.relative_humidity_pct = measured(1U);
  input.state.measurements.co2_ppm = measured(2U);
  input.state.measurements.outside_temperature_c = measured(3U);
  input.state.measurements.outside_humidity_pct = measured(4U);
  input.humidity_control_mode =
      fixture.humidity_vpd ? HumidityControlMode::Vpd : HumidityControlMode::Rh;
  input.targets.air_temperature_c = fixture.target_temperature_c;
  input.targets.relative_humidity_pct = fixture.target_humidity_pct;
  input.targets.air_vpd_kpa = fixture.target_vpd_kpa;
  input.targets.co2_enabled = fixture.co2_enabled;
  input.targets.co2_ppm = fixture.target_co2_ppm;
  input.schedule.light_level = fixture.light_level;
  input.capabilities = {fixture.capabilities[0], fixture.capabilities[1], fixture.capabilities[2],
                        fixture.capabilities[3], fixture.capabilities[4], fixture.capabilities[5]};
  input.previous = {fixture.previous[0], fixture.previous[1], fixture.previous[2],
                    fixture.previous[3], fixture.previous[4], fixture.previous[5]};
  input.sensor_timeout_ms = fixture.sensor_timeout_ms;
  return input;
}

void runCase(const growbox::climate::parity_fixture::Case& fixture) {
  using namespace growbox::climate;
  ClimateRuntimeConfig config{};
  config.mode = static_cast<ClimatePolicyMode>(fixture.mode);
  config.allow_unqualified_ml_active = fixture.allow_ml_active;
  config.sensor_timeout_ms = fixture.sensor_timeout_ms;
  config.timestep_s = fixture.timestep_s;
  config.ml_deadzone = 0.05F;

  FixtureProvider provider{fixture};
  ClimateInferenceProvider* provider_ptr =
      fixture.model_behavior == parity_fixture::ModelBehavior::None ? nullptr : &provider;
  ClimateRuntimeController runtime{provider_ptr, config};
  ClimateRuntimeDecision decision{};
  const auto status = runtime.step(makeInput(fixture), fixture.monotonic_ms, decision);

  check(static_cast<std::uint8_t>(status) == fixture.expected_status, fixture.name,
        "runtime status");
  check(decision.authoritative_ml == fixture.expected_authoritative_ml, fixture.name,
        "authoritative policy");
  check(decision.ml_evaluated == fixture.expected_ml_evaluated, fixture.name, "ML evaluated");

  checkArray(values(decision.rule.raw), fixture.expected_rule_raw, fixture.name, "rule raw");
  checkArray(values(decision.rule.arbitrated), fixture.expected_rule_arbitrated, fixture.name,
             "rule arbitrated");
  checkArray(values(decision.rule.safe), fixture.expected_rule_safe, fixture.name, "rule safe");
  check(decision.rule.arbitration_interventions == fixture.expected_rule_arb_mask, fixture.name,
        "rule arbitration interventions");
  check(decision.rule.safety_interventions == fixture.expected_rule_safety_mask, fixture.name,
        "rule safety interventions");

  if (fixture.expected_ml_evaluated) {
    checkArray(values(decision.ml.raw), fixture.expected_ml_raw, fixture.name, "ML raw");
    checkArray(values(decision.ml.arbitrated), fixture.expected_ml_arbitrated, fixture.name,
               "ML arbitrated");
    checkArray(values(decision.ml.safe), fixture.expected_ml_safe, fixture.name, "ML safe");
    check(decision.ml.arbitration_interventions == fixture.expected_ml_arb_mask, fixture.name,
          "ML arbitration interventions");
    check(decision.ml.safety_interventions == fixture.expected_ml_safety_mask, fixture.name,
          "ML safety interventions");
  }

  if (fixture.expected_has_ml_features) {
    checkArray(decision.ml_features.values, fixture.expected_ml_features, fixture.name,
               "44-feature runtime vector", 2.0e-4F);
  }

  checkArray(values(decision.applied), fixture.expected_applied, fixture.name, "applied action");
  checkArray(values(decision.effective_before), fixture.expected_effective_before, fixture.name,
             "effective before");
  checkArray(values(decision.effective_after), fixture.expected_effective_after, fixture.name,
             "effective after", 2.0e-4F);
}
} // namespace

int main() {
  for (const auto& fixture : growbox::climate::parity_fixture::kCases) {
    runCase(fixture);
  }
  if (failures != 0) {
    std::cerr << failures << " climate runtime parity checks failed\n";
    return 1;
  }
  std::cout << "climate runtime parity checks passed\n";
  return 0;
}
