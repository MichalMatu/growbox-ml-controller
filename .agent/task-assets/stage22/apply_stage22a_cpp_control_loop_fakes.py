from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()

HEADER = dedent(r'''
#pragma once

#include "ClimateRuntimeController.h"

#include <cstdint>

namespace growbox::climate {

enum class ClimateLoopIoStatus : std::uint8_t {
  Ok = 0U,
  InputUnavailable,
  ActuatorApplyFailed,
  ActuatorFaultLatched,
};

class ClimateInputSource {
public:
  virtual ~ClimateInputSource() = default;
  virtual bool sample(std::uint64_t monotonic_ms, ClimateControllerInput& input) noexcept = 0;
};

class ClimateActuatorSink {
public:
  virtual ~ClimateActuatorSink() = default;
  virtual bool apply(const ClimatePolicyRequest& request, std::uint64_t monotonic_ms) noexcept = 0;
};

struct ClimateLoopResult {
  ClimateLoopIoStatus io_status = ClimateLoopIoStatus::Ok;
  ClimateRuntimeStatus runtime_status = ClimateRuntimeStatus::Ok;
  bool input_sampled = false;
  bool command_applied = false;
  bool fail_safe_attempted = false;
  bool fail_safe_applied = false;
};

class ClimateControlLoop {
public:
  ClimateControlLoop(ClimateRuntimeController& runtime, ClimateInputSource& input_source,
                     ClimateActuatorSink& actuator_sink) noexcept;

  ClimateLoopResult tick(std::uint64_t monotonic_ms, ClimateRuntimeDecision& decision) noexcept;
  void reset() noexcept;

  bool actuatorFaultLatched() const noexcept { return actuator_fault_latched_; }
  const PreviousClimateActions& previousApplied() const noexcept { return previous_applied_; }

private:
  static PreviousClimateActions previousFromRequest(const ClimatePolicyRequest& request) noexcept;
  static bool isOff(const ClimatePolicyRequest& request) noexcept;

  ClimateRuntimeController& runtime_;
  ClimateInputSource& input_source_;
  ClimateActuatorSink& actuator_sink_;
  PreviousClimateActions previous_applied_{};
  bool actuator_fault_latched_ = false;
};

} // namespace growbox::climate
''').lstrip()

SOURCE = dedent(r'''
#include "ClimateControlLoop.h"

namespace growbox::climate {

ClimateControlLoop::ClimateControlLoop(ClimateRuntimeController& runtime,
                                       ClimateInputSource& input_source,
                                       ClimateActuatorSink& actuator_sink) noexcept
    : runtime_(runtime), input_source_(input_source), actuator_sink_(actuator_sink) {}

PreviousClimateActions
ClimateControlLoop::previousFromRequest(const ClimatePolicyRequest& request) noexcept {
  return PreviousClimateActions{request.heater,       request.cooler,       request.exhaust_fan,
                                request.humidifier,   request.dehumidifier, request.co2_doser};
}

bool ClimateControlLoop::isOff(const ClimatePolicyRequest& request) noexcept {
  return request.heater == 0.0F && request.cooler == 0.0F && request.exhaust_fan == 0.0F &&
         request.humidifier == 0.0F && request.dehumidifier == 0.0F && request.co2_doser == 0.0F;
}

ClimateLoopResult ClimateControlLoop::tick(std::uint64_t monotonic_ms,
                                           ClimateRuntimeDecision& decision) noexcept {
  ClimateLoopResult result{};

  if (actuator_fault_latched_) {
    decision = {};
    const ClimatePolicyRequest off{};
    result.io_status = ClimateLoopIoStatus::ActuatorFaultLatched;
    result.fail_safe_attempted = true;
    result.fail_safe_applied = actuator_sink_.apply(off, monotonic_ms);
    result.command_applied = result.fail_safe_applied;
    return result;
  }

  ClimateControllerInput input{};
  result.input_sampled = input_source_.sample(monotonic_ms, input);
  if (!result.input_sampled) {
    input = {};
  }
  input.previous = previous_applied_;

  result.runtime_status = runtime_.step(input, monotonic_ms, decision);
  result.command_applied = actuator_sink_.apply(decision.applied, monotonic_ms);
  if (result.command_applied) {
    previous_applied_ = previousFromRequest(decision.applied);
    result.io_status =
        result.input_sampled ? ClimateLoopIoStatus::Ok : ClimateLoopIoStatus::InputUnavailable;
    return result;
  }

  result.io_status = ClimateLoopIoStatus::ActuatorApplyFailed;
  result.fail_safe_attempted = true;
  const ClimatePolicyRequest off{};
  result.fail_safe_applied = actuator_sink_.apply(off, monotonic_ms);

  // The runtime already advanced its effective-action estimator before the sink
  // acknowledgement. Reset it after any rejected command so an unconfirmed
  // actuator state never becomes future ML context.
  runtime_.reset();
  previous_applied_ = {};
  if (!result.fail_safe_applied) {
    actuator_fault_latched_ = true;
  }
  return result;
}

void ClimateControlLoop::reset() noexcept {
  runtime_.reset();
  previous_applied_ = {};
  actuator_fault_latched_ = false;
}

} // namespace growbox::climate
''').lstrip()

TEST = dedent(r'''
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
  testRejectedCommandAttemptsOffAndRecoversEstimator();
  testDoubleActuatorFailureLatchesFault();
  return 0;
}
''').lstrip()

header_path = ROOT / "lib/environment_control/src/climate/ClimateControlLoop.h"
source_path = ROOT / "lib/environment_control/src/climate/ClimateControlLoop.cpp"
test_dir = ROOT / "test/test_climate_control_loop"
test_dir.mkdir(parents=True, exist_ok=True)
header_path.write_text(HEADER, encoding="utf-8")
source_path.write_text(SOURCE, encoding="utf-8")
(test_dir / "test_main.cpp").write_text(TEST, encoding="utf-8")

cmake_path = ROOT / "test/host/CMakeLists.txt"
cmake = cmake_path.read_text(encoding="utf-8")
needle = '''if(UNIX)
  target_link_libraries(environment_control_tests PRIVATE m)
  target_link_libraries(climate_v6_tests PRIVATE m)
  target_link_libraries(climate_runtime_parity_tests PRIVATE m)
endif()
'''
insert = '''add_executable(
  climate_control_loop_tests
  "${PROJECT_ROOT}/test/test_climate_control_loop/test_main.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateControlLoop.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateFeatureEncoder.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateRuntimeController.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateTrendEstimator.cpp"
)
target_include_directories(climate_control_loop_tests PRIVATE "${PROJECT_ROOT}/lib/environment_control/src/climate")
target_compile_features(climate_control_loop_tests PRIVATE cxx_std_17)
target_compile_options(climate_control_loop_tests PRIVATE -Wall -Wextra -Wpedantic)

if(UNIX)
  target_link_libraries(environment_control_tests PRIVATE m)
  target_link_libraries(climate_v6_tests PRIVATE m)
  target_link_libraries(climate_runtime_parity_tests PRIVATE m)
  target_link_libraries(climate_control_loop_tests PRIVATE m)
endif()
'''
if needle not in cmake:
    raise SystemExit("Stage22A CMake link block not found")
cmake = cmake.replace(needle, insert, 1)
needle_test = "add_test(NAME climate_runtime_parity_tests COMMAND climate_runtime_parity_tests)\n"
replacement_test = needle_test + "add_test(NAME climate_control_loop_tests COMMAND climate_control_loop_tests)\n"
if needle_test not in cmake:
    raise SystemExit("Stage22A CMake test block not found")
cmake_path.write_text(cmake.replace(needle_test, replacement_test, 1), encoding="utf-8")
