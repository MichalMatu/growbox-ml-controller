#include "ClimateActuatorStateEstimator.h"
#include "ClimateContract.h"
#include "ClimateFeatureEncoder.h"
#include "ClimateMath.h"
#include "ClimateRuntimeController.h"
#include "ClimateTrendEstimator.h"
#include <cmath>
#include <cstring>
#include <iostream>
namespace {
int failures = 0;
void check(bool c, const char* m) {
  if (!c) {
    ++failures;
    std::cerr << "FAIL: " << m << '\n';
  }
}
bool near(float a, float b, float t) {
  return std::abs(a - b) <= t;
}
float feature(const growbox::climate::ClimateFeatureVector& v,
              growbox::climate::contract::FeatureIndex i) {
  return v.values[growbox::climate::contract::index(i)];
}

bool anyActiveForTest(const growbox::climate::ClimatePolicyRequest& request) {
  return request.heater > 0.0F || request.cooler > 0.0F || request.exhaust_fan > 0.0F ||
         request.humidifier > 0.0F || request.dehumidifier > 0.0F || request.co2_doser > 0.0F;
}

void contractTest() {
  namespace c = growbox::climate::contract;
  check(c::kSchemaVersion == 6U, "schema version");
  check(c::kFeatureCount == 44U, "feature count");
  check(c::kOutputCount == 6U, "output count");
  const char* expected[] = {"heater",     "cooler",       "exhaust_fan",
                            "humidifier", "dehumidifier", "co2_doser"};
  for (std::size_t i = 0; i < c::kOutputCount; ++i)
    check(std::strcmp(c::kOutputNames[i], expected[i]) == 0, "output order");
}
void encoderTest() {
  using namespace growbox::climate;
  namespace c = growbox::climate::contract;
  ClimateControllerInput in{};
  in.state.measurements.air_temperature_c = {24.0F, true, 0U};
  in.state.measurements.relative_humidity_pct = {60.0F, true, 0U};
  in.state.measurements.co2_ppm = {999.0F, false, 0U};
  in.state.measurements.outside_temperature_c = {18.0F, true, 40'000U};
  in.state.measurements.outside_humidity_pct = {45.0F, true, 0U};
  in.humidity_control_mode = HumidityControlMode::Vpd;
  in.schedule.light_level = 0.75F;
  in.previous.heater = 2.0F;
  in.estimated_effective.heater = 0.25F;
  in.capabilities.heater = true;
  in.state.trends.temperature = {1.0F, true};
  in.state.trends.humidity = {-2.0F, true};
  in.state.trends.co2 = {100.0F, true};
  ClimateEncoderReport r{};
  const auto v = ClimateFeatureEncoder::encode(in, &r);
  check(near(feature(v, c::FeatureIndex::AirTemperatureC), 0.55F, 0.0001F),
        "temperature normalization");
  check(feature(v, c::FeatureIndex::Co2Valid) == 0.0F, "CO2 valid");
  check(feature(v, c::FeatureIndex::Co2Fresh) == 1.0F, "freshness independent");
  check(r.substituted(c::FeatureIndex::Co2Ppm), "invalid CO2 fallback");
  check(feature(v, c::FeatureIndex::OutsideTemperatureFresh) == 0.0F, "stale outside");
  check(r.substituted(c::FeatureIndex::OutsideTemperatureC), "stale fallback");
  check(feature(v, c::FeatureIndex::HumidityControlMode) == 1.0F, "VPD mode");
  check(near(feature(v, c::FeatureIndex::LightLevel), 0.75F, 0.0001F), "light context");
  check(feature(v, c::FeatureIndex::PreviousHeater) == 1.0F, "command clamp");
  check(r.clamped(c::FeatureIndex::PreviousHeater), "clamp diagnostic");
  check(near(feature(v, c::FeatureIndex::EstimatedEffectiveHeater), 0.25F, 0.0001F),
        "effective actuator context");
}
void actuatorEstimatorTest() {
  using namespace growbox::climate;
  ClimateActuatorStateEstimator estimator{};
  ClimateCapabilities capabilities{};
  capabilities.heater = true;
  capabilities.cooler = true;
  capabilities.exhaust_fan = true;
  capabilities.humidifier = true;
  capabilities.dehumidifier = true;
  capabilities.co2_doser = true;
  ClimatePolicyRequest command{};
  command.heater = 1.0F;
  command.cooler = 0.5F;
  command.exhaust_fan = 0.8F;
  command.humidifier = 0.6F;
  command.dehumidifier = 0.4F;
  command.co2_doser = 0.7F;
  const auto first = estimator.update(command, 10.0F, capabilities);
  check(near(first.heater, 1.0F - std::exp(-10.0F / 35.0F), 0.0001F), "heater lag");
  check(near(first.cooler, 0.5F * (1.0F - std::exp(-10.0F / 45.0F)), 0.0001F), "cooler lag");
  check(near(first.co2_doser, 0.7F, 0.0001F), "zero-lag CO2");
  estimator.reset();
  capabilities.heater = false;
  const auto masked = estimator.update(command, 10.0F, capabilities);
  check(masked.heater == 0.0F, "unavailable actuator masked");
}

void trendTest() {
  using namespace growbox::climate;
  ClimateTrendEstimator e{};
  ClimateMeasurements m{};
  ClimateTrends tr{};
  for (std::uint64_t ms = 0U; ms <= 60'000U; ms += 5'000U) {
    const float min = static_cast<float>(ms) / 60'000.0F;
    m.air_temperature_c = {20.0F + min, true, 0U};
    m.relative_humidity_pct = {60.0F - 2.0F * min, true, 0U};
    m.co2_ppm = {500.0F + 100.0F * min, true, 0U};
    tr = e.update(m, ms);
    if (ms < 10'000U)
      check(!tr.temperature.available, "startup trend");
  }
  check(tr.temperature.available && near(tr.temperature.rate_per_min, 1.0F, 0.01F),
        "temperature trend");
  check(tr.humidity.available && near(tr.humidity.rate_per_min, -2.0F, 0.01F), "humidity trend");
  check(tr.co2.available && near(tr.co2.rate_per_min, 100.0F, 0.05F), "CO2 trend");
  m.co2_ppm.age_ms = kDefaultSensorTimeoutMs + 1U;
  tr = e.update(m, 65'000U);
  check(!tr.co2.available, "stale CO2 trend");
  tr = e.update(m, 1'000U);
  check(!tr.temperature.available, "rollback resets trend");
  ClimateTrendEstimator fast{};
  m.co2_ppm = {500.0F, true, 0U};
  for (std::uint64_t ms = 0U; ms <= 60'000U; ms += 1'000U) {
    const float min = static_cast<float>(ms) / 60'000.0F;
    m.air_temperature_c = {20.0F + min, true, 0U};
    m.relative_humidity_pct = {60.0F, true, 0U};
    tr = fast.update(m, ms);
  }
  check(tr.temperature.available && near(tr.temperature.rate_per_min, 1.0F, 0.02F), "1 Hz trend");
}

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
  check(!decision.authoritative_ml && blocked_provider.calls == 0,
        "runtime blocked active uses rule");
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

} // namespace
int main() {
  contractTest();
  check(near(growbox::climate::airVpdKpa(25.0F, 60.0F), 1.264F, 0.015F), "VPD math");
  encoderTest();
  actuatorEstimatorTest();
  trendTest();
  runtimePolicyModeTest();
  runtimeSafetyTest();
  if (failures) {
    std::cerr << failures << " climate v6 checks failed\n";
    return 1;
  }
  std::cout << "climate v6 checks passed\n";
  return 0;
}
