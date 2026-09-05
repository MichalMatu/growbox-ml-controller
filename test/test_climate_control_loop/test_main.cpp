#include "ClimateControlLoop.h"

#include <cassert>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <vector>

using namespace growbox::climate;

namespace {

bool near(float left, float right, float tolerance = 1.0e-6F) {
  return std::fabs(left - right) <= tolerance;
}

bool off(const ClimatePolicyRequest& request) {
  return near(request.heater, 0.0F) && near(request.cooler, 0.0F) &&
         near(request.exhaust_fan, 0.0F) && near(request.humidifier, 0.0F) &&
         near(request.dehumidifier, 0.0F) && near(request.co2_doser, 0.0F);
}

bool same(const ClimatePolicyRequest& left, const ClimatePolicyRequest& right) {
  return near(left.heater, right.heater) && near(left.cooler, right.cooler) &&
         near(left.exhaust_fan, right.exhaust_fan) && near(left.humidifier, right.humidifier) &&
         near(left.dehumidifier, right.dehumidifier) && near(left.co2_doser, right.co2_doser);
}

ClimateControllerInput validInput() {
  ClimateControllerInput input{};
  input.state.measurements.air_temperature_c = {18.0F, true, 0U};
  input.state.measurements.relative_humidity_pct = {60.0F, true, 0U};
  input.state.measurements.co2_ppm = {500.0F, true, 0U};
  input.state.measurements.outside_temperature_c = {10.0F, true, 0U};
  input.state.measurements.outside_humidity_pct = {50.0F, true, 0U};
  input.targets.air_temperature_c = 24.0F;
  input.targets.relative_humidity_pct = 60.0F;
  input.targets.co2_enabled = false;
  input.capabilities.heater = true;
  input.capabilities.cooler = true;
  input.capabilities.exhaust_fan = true;
  input.capabilities.humidifier = true;
  input.capabilities.dehumidifier = true;
  input.capabilities.co2_doser = true;
  input.schedule.light_level = 0.5F;
  return input;
}

class FakeInputSource final : public ClimateInputSource {
public:
  ClimateControllerInput input = validInput();
  bool available = true;
  std::size_t calls = 0U;

  bool sample(std::uint64_t, ClimateControllerInput& output) noexcept override {
    ++calls;
    if (!available) {
      return false;
    }
    output = input;
    return true;
  }
};

class FakeActuatorSink final : public ClimateActuatorSink {
public:
  std::vector<ClimatePolicyRequest> requests{};
  std::vector<bool> outcomes{};

  bool apply(const ClimatePolicyRequest& request, std::uint64_t) noexcept override {
    requests.push_back(request);
    const std::size_t index = requests.size() - 1U;
    return index < outcomes.size() ? outcomes[index] : true;
  }
};

class QuantizingActuatorSink final : public ClimateActuatorSink {
public:
  ClimatePolicyRequest requested{};

  bool apply(const ClimatePolicyRequest& request, std::uint64_t) noexcept override {
    requested = request;
    return true;
  }

  bool applyAndReport(const ClimatePolicyRequest& request, std::uint64_t monotonic_ms,
                      ClimatePolicyRequest& confirmed_applied) noexcept override {
    if (!apply(request, monotonic_ms)) {
      confirmed_applied = {};
      return false;
    }
    confirmed_applied = request;
    confirmed_applied.exhaust_fan = request.exhaust_fan > 0.0F ? 1.0F : 0.0F;
    return true;
  }
};

class FixedInference final : public ClimateInferenceProvider {
public:
  bool infer(const ClimateFeatureVector&, ClimatePolicyRequest& output) noexcept override {
    output.heater = 0.2F;
    output.cooler = 0.8F;
    output.exhaust_fan = 0.7F;
    output.humidifier = 0.6F;
    output.dehumidifier = 0.4F;
    output.co2_doser = 0.9F;
    return true;
  }
};

void testNominalRuleCommandReachesSink() {
  ClimateRuntimeController runtime{};
  FakeInputSource source{};
  FakeActuatorSink sink{};
  ClimateControlLoop loop(runtime, source, sink);
  ClimateRuntimeDecision decision{};

  const ClimateLoopResult result = loop.tick(120'000U, decision);
  assert(result.io_status == ClimateLoopIoStatus::Ok);
  assert(result.input_sampled);
  assert(result.command_applied);
  assert(sink.requests.size() == 1U);
  assert(same(sink.requests.front(), decision.applied));
  assert(decision.applied.heater > 0.0F);
  assert(near(loop.previousApplied().heater, decision.applied.heater));
}

void testInputFailureFailsClosed() {
  ClimateRuntimeController runtime{};
  FakeInputSource source{};
  source.available = false;
  FakeActuatorSink sink{};
  ClimateControlLoop loop(runtime, source, sink);
  ClimateRuntimeDecision decision{};

  const ClimateLoopResult result = loop.tick(120'000U, decision);
  assert(result.io_status == ClimateLoopIoStatus::InputUnavailable);
  assert(!result.input_sampled);
  assert(result.command_applied);
  assert(sink.requests.size() == 1U);
  assert(off(sink.requests.front()));
  assert(off(decision.applied));
}

void testMlShadowNeverDrivesSink() {
  FixedInference inference{};
  ClimateRuntimeConfig config{};
  config.mode = ClimatePolicyMode::MlShadow;
  ClimateRuntimeController runtime(&inference, config);
  FakeInputSource source{};
  FakeActuatorSink sink{};
  ClimateControlLoop loop(runtime, source, sink);
  ClimateRuntimeDecision decision{};

  const ClimateLoopResult result = loop.tick(120'000U, decision);
  assert(result.io_status == ClimateLoopIoStatus::Ok);
  assert(decision.ml_evaluated);
  assert(!decision.authoritative_ml);
  assert(same(sink.requests.front(), decision.rule.safe));
  assert(same(sink.requests.front(), decision.applied));
}

void testConfirmedBinaryStateBecomesRuntimeTruth() {
  ClimateRuntimeController runtime{};
  FakeInputSource source{};
  source.input = validInput();
  source.input.state.measurements.air_temperature_c = {24.0F, true, 0U};
  source.input.state.measurements.relative_humidity_pct = {75.0F, true, 0U};
  source.input.state.measurements.outside_temperature_c = {24.0F, true, 0U};
  source.input.state.measurements.outside_humidity_pct = {50.0F, true, 0U};
  source.input.targets.air_temperature_c = 24.0F;
  source.input.targets.relative_humidity_pct = 60.0F;
  QuantizingActuatorSink sink{};
  ClimateControlLoop loop(runtime, source, sink);
  ClimateRuntimeDecision decision{};

  const ClimateLoopResult result = loop.tick(120'000U, decision);
  assert(result.command_applied);
  assert(sink.requested.exhaust_fan > 0.0F && sink.requested.exhaust_fan < 1.0F);
  assert(decision.rule.safe.exhaust_fan > 0.0F && decision.rule.safe.exhaust_fan < 1.0F);
  assert(near(decision.applied.exhaust_fan, 1.0F));
  assert(near(loop.previousApplied().exhaust_fan, 1.0F));
  assert(decision.effective_after.exhaust_fan > 0.6F);
}

void testRejectedCommandAttemptsOffAndRecoversEstimator() {
  ClimateRuntimeController runtime{};
  FakeInputSource source{};
  FakeActuatorSink sink{};
  sink.outcomes = {false, true};
  ClimateControlLoop loop(runtime, source, sink);
  ClimateRuntimeDecision decision{};

  const ClimateLoopResult result = loop.tick(120'000U, decision);
  assert(result.io_status == ClimateLoopIoStatus::ActuatorApplyFailed);
  assert(!result.command_applied);
  assert(result.fail_safe_attempted);
  assert(result.fail_safe_applied);
  assert(sink.requests.size() == 2U);
  assert(!off(sink.requests.front()));
  assert(off(sink.requests.back()));
  assert(!loop.actuatorFaultLatched());
  assert(near(loop.previousApplied().heater, 0.0F));

  sink.outcomes.clear();
  const ClimateLoopResult recovered = loop.tick(130'000U, decision);
  assert(recovered.io_status == ClimateLoopIoStatus::Ok);
  assert(recovered.command_applied);
}

void testDoubleActuatorFailureLatchesFault() {
  ClimateRuntimeController runtime{};
  FakeInputSource source{};
  FakeActuatorSink sink{};
  sink.outcomes = {false, false, true};
  ClimateControlLoop loop(runtime, source, sink);
  ClimateRuntimeDecision decision{};

  const ClimateLoopResult failed = loop.tick(120'000U, decision);
  assert(failed.io_status == ClimateLoopIoStatus::ActuatorApplyFailed);
  assert(failed.fail_safe_attempted);
  assert(!failed.fail_safe_applied);
  assert(loop.actuatorFaultLatched());
  const std::size_t samples_before_latched_tick = source.calls;

  const ClimateLoopResult latched = loop.tick(130'000U, decision);
  assert(latched.io_status == ClimateLoopIoStatus::ActuatorFaultLatched);
  assert(latched.fail_safe_attempted);
  assert(latched.fail_safe_applied);
  assert(source.calls == samples_before_latched_tick);
  assert(off(sink.requests.back()));
  assert(loop.actuatorFaultLatched());

  loop.reset();
  assert(!loop.actuatorFaultLatched());
  sink.outcomes.clear();
  const ClimateLoopResult recovered = loop.tick(140'000U, decision);
  assert(recovered.io_status == ClimateLoopIoStatus::Ok);
}

} // namespace

int main() {
  testNominalRuleCommandReachesSink();
  testInputFailureFailsClosed();
  testMlShadowNeverDrivesSink();
  testConfirmedBinaryStateBecomesRuntimeTruth();
  testRejectedCommandAttemptsOffAndRecoversEstimator();
  testDoubleActuatorFailureLatchesFault();
  return 0;
}
