from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()
TEST = ROOT / "test" / "test_climate_virtual_hil" / "test_main.cpp"
CMAKE = ROOT / "test" / "host" / "CMakeLists.txt"

TEST.parent.mkdir(parents=True, exist_ok=True)
TEST.write_text(
    dedent(
        r'''
        #include "ClimateControlLoop.h"

        #include <cassert>
        #include <cmath>
        #include <cstddef>
        #include <cstdint>
        #include <utility>
        #include <vector>

        using namespace growbox::climate;

        namespace {

        bool near(float left, float right, float tolerance = 1.0e-5F) {
          return std::fabs(left - right) <= tolerance;
        }

        bool off(const ClimatePolicyRequest& request) {
          return near(request.heater, 0.0F) && near(request.cooler, 0.0F) &&
                 near(request.exhaust_fan, 0.0F) && near(request.humidifier, 0.0F) &&
                 near(request.dehumidifier, 0.0F) && near(request.co2_doser, 0.0F);
        }

        bool same(const ClimatePolicyRequest& left, const ClimatePolicyRequest& right) {
          return near(left.heater, right.heater) && near(left.cooler, right.cooler) &&
                 near(left.exhaust_fan, right.exhaust_fan) &&
                 near(left.humidifier, right.humidifier) &&
                 near(left.dehumidifier, right.dehumidifier) && near(left.co2_doser, right.co2_doser);
        }

        ClimateControllerInput inputFor(float temperature_c, float humidity_pct = 60.0F,
                                        float co2_ppm = 500.0F) {
          ClimateControllerInput input{};
          input.state.measurements.air_temperature_c = {temperature_c, true, 0U};
          input.state.measurements.relative_humidity_pct = {humidity_pct, true, 0U};
          input.state.measurements.co2_ppm = {co2_ppm, true, 0U};
          input.state.measurements.outside_temperature_c = {10.0F, true, 0U};
          input.state.measurements.outside_humidity_pct = {50.0F, true, 0U};
          input.targets.air_temperature_c = 24.0F;
          input.targets.relative_humidity_pct = 60.0F;
          input.targets.air_vpd_kpa = 1.2F;
          input.targets.co2_enabled = true;
          input.targets.co2_ppm = 950.0F;
          input.schedule.light_level = 0.6F;
          input.capabilities.heater = true;
          input.capabilities.cooler = true;
          input.capabilities.exhaust_fan = true;
          input.capabilities.humidifier = true;
          input.capabilities.dehumidifier = true;
          input.capabilities.co2_doser = true;
          input.sensor_timeout_ms = 30'000U;
          return input;
        }

        struct ScriptedFrame {
          bool available = true;
          ClimateControllerInput input{};
        };

        class ScriptedInputSource final : public ClimateInputSource {
        public:
          explicit ScriptedInputSource(std::vector<ScriptedFrame> frames)
              : frames_(std::move(frames)) {}

          bool sample(std::uint64_t, ClimateControllerInput& output) noexcept override {
            ++calls;
            if (index_ >= frames_.size()) {
              return false;
            }
            const ScriptedFrame& frame = frames_[index_++];
            if (!frame.available) {
              return false;
            }
            output = frame.input;
            return true;
          }

          std::size_t calls = 0U;

        private:
          std::vector<ScriptedFrame> frames_{};
          std::size_t index_ = 0U;
        };

        class ScriptedActuatorSink final : public ClimateActuatorSink {
        public:
          explicit ScriptedActuatorSink(std::vector<bool> outcomes = {})
              : outcomes_(std::move(outcomes)) {}

          bool apply(const ClimatePolicyRequest& request, std::uint64_t monotonic_ms) noexcept override {
            requests.push_back(request);
            timestamps.push_back(monotonic_ms);
            const std::size_t index = requests.size() - 1U;
            return index < outcomes_.size() ? outcomes_[index] : true;
          }

          std::vector<ClimatePolicyRequest> requests{};
          std::vector<std::uint64_t> timestamps{};

        private:
          std::vector<bool> outcomes_{};
        };

        class FixedShadowInference final : public ClimateInferenceProvider {
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

        void testStatefulRuleSequenceUpdatesTrendsAndEffectiveState() {
          ScriptedInputSource source({{true, inputFor(20.0F)},
                                      {true, inputFor(21.0F)},
                                      {true, inputFor(22.0F)}});
          ScriptedActuatorSink sink{};
          ClimateRuntimeConfig config{};
          config.timestep_s = 10.0F;
          ClimateRuntimeController runtime(nullptr, config);
          ClimateControlLoop loop(runtime, source, sink);

          ClimateRuntimeDecision first{};
          ClimateRuntimeDecision second{};
          ClimateRuntimeDecision third{};
          assert(loop.tick(100'000U, first).io_status == ClimateLoopIoStatus::Ok);
          assert(loop.tick(110'000U, second).io_status == ClimateLoopIoStatus::Ok);
          assert(loop.tick(120'000U, third).io_status == ClimateLoopIoStatus::Ok);

          assert(sink.requests.size() == 3U);
          assert(first.applied.heater > second.applied.heater);
          assert(second.applied.heater > third.applied.heater);
          assert(near(first.effective_before.heater, 0.0F));
          assert(first.effective_after.heater > 0.0F);
          assert(near(second.effective_before.heater, first.effective_after.heater));
          assert(second.trends.temperature.available);
          assert(second.trends.temperature.rate_per_min > 0.0F);
          assert(third.trends.temperature.available);
          assert(near(loop.previousApplied().heater, third.applied.heater));
          assert(same(sink.requests[0], first.applied));
          assert(same(sink.requests[1], second.applied));
          assert(same(sink.requests[2], third.applied));
        }

        void testStaleAndUnavailableInputsFailClosedThenRecover() {
          ClimateControllerInput stale = inputFor(20.0F);
          stale.state.measurements.air_temperature_c.age_ms = 31'000U;
          ScriptedInputSource source({{true, inputFor(20.0F)},
                                      {true, stale},
                                      {false, {}},
                                      {true, inputFor(20.0F)}});
          ScriptedActuatorSink sink{};
          ClimateRuntimeController runtime{};
          ClimateControlLoop loop(runtime, source, sink);
          ClimateRuntimeDecision decision{};

          const auto nominal = loop.tick(100'000U, decision);
          assert(nominal.io_status == ClimateLoopIoStatus::Ok);
          assert(decision.applied.heater > 0.0F);

          const auto stale_result = loop.tick(110'000U, decision);
          assert(stale_result.io_status == ClimateLoopIoStatus::Ok);
          assert(stale_result.input_sampled);
          assert(off(decision.applied));

          const auto unavailable = loop.tick(120'000U, decision);
          assert(unavailable.io_status == ClimateLoopIoStatus::InputUnavailable);
          assert(!unavailable.input_sampled);
          assert(off(decision.applied));

          const auto recovered = loop.tick(130'000U, decision);
          assert(recovered.io_status == ClimateLoopIoStatus::Ok);
          assert(recovered.input_sampled);
          assert(decision.applied.heater > 0.0F);
          assert(sink.requests.size() == 4U);
        }

        void testMlShadowRemainsObservationalAcrossSequence() {
          FixedShadowInference inference{};
          ClimateRuntimeConfig config{};
          config.mode = ClimatePolicyMode::MlShadow;
          ClimateRuntimeController runtime(&inference, config);
          ScriptedInputSource source({{true, inputFor(20.0F)},
                                      {true, inputFor(21.0F)},
                                      {true, inputFor(22.0F)}});
          ScriptedActuatorSink sink{};
          ClimateControlLoop loop(runtime, source, sink);
          ClimateRuntimeDecision decision{};

          for (std::uint64_t now : {100'000ULL, 110'000ULL, 120'000ULL}) {
            const auto result = loop.tick(now, decision);
            assert(result.io_status == ClimateLoopIoStatus::Ok);
            assert(decision.ml_evaluated);
            assert(!decision.authoritative_ml);
            assert(same(sink.requests.back(), decision.rule.safe));
            assert(same(sink.requests.back(), decision.applied));
            assert(!same(decision.ml.safe, decision.rule.safe));
          }
          assert(sink.requests.size() == 3U);
        }

        void testSafetyTransitionsStayAuthoritativeAcrossTicks() {
          ScriptedInputSource source({{true, inputFor(45.0F, 60.0F, 500.0F)},
                                      {true, inputFor(24.0F, 96.0F, 500.0F)},
                                      {true, inputFor(24.0F, 60.0F, 1'900.0F)}});
          ScriptedActuatorSink sink{};
          ClimateRuntimeController runtime{};
          ClimateControlLoop loop(runtime, source, sink);
          ClimateRuntimeDecision decision{};

          assert(loop.tick(100'000U, decision).io_status == ClimateLoopIoStatus::Ok);
          assert(near(decision.applied.heater, 0.0F));
          assert(near(decision.applied.cooler, 1.0F));
          assert(near(decision.applied.exhaust_fan, 1.0F));
          assert(near(decision.applied.co2_doser, 0.0F));

          assert(loop.tick(110'000U, decision).io_status == ClimateLoopIoStatus::Ok);
          assert(near(decision.applied.humidifier, 0.0F));
          assert(near(decision.applied.dehumidifier, 1.0F));
          assert(near(decision.applied.co2_doser, 0.0F));

          assert(loop.tick(120'000U, decision).io_status == ClimateLoopIoStatus::Ok);
          assert(near(decision.applied.co2_doser, 0.0F));
          assert(near(decision.applied.exhaust_fan, 1.0F));
          assert(sink.requests.size() == 3U);
        }

        void testRejectedCommandResetsRuntimeStateBeforeRecoveryTick() {
          ScriptedInputSource source({{true, inputFor(20.0F)}, {true, inputFor(20.0F)}});
          ScriptedActuatorSink sink({false, true, true});
          ClimateRuntimeController runtime{};
          ClimateControlLoop loop(runtime, source, sink);
          ClimateRuntimeDecision failed_decision{};
          ClimateRuntimeDecision recovered_decision{};

          const auto failed = loop.tick(100'000U, failed_decision);
          assert(failed.io_status == ClimateLoopIoStatus::ActuatorApplyFailed);
          assert(failed.fail_safe_attempted);
          assert(failed.fail_safe_applied);
          assert(!loop.actuatorFaultLatched());
          assert(sink.requests.size() == 2U);
          assert(!off(sink.requests.front()));
          assert(off(sink.requests[1]));

          const auto recovered = loop.tick(110'000U, recovered_decision);
          assert(recovered.io_status == ClimateLoopIoStatus::Ok);
          assert(recovered.command_applied);
          assert(near(recovered_decision.effective_before.heater, 0.0F));
          assert(recovered_decision.applied.heater > 0.0F);
          assert(sink.requests.size() == 3U);
        }

        } // namespace

        int main() {
          testStatefulRuleSequenceUpdatesTrendsAndEffectiveState();
          testStaleAndUnavailableInputsFailClosedThenRecover();
          testMlShadowRemainsObservationalAcrossSequence();
          testSafetyTransitionsStayAuthoritativeAcrossTicks();
          testRejectedCommandResetsRuntimeStateBeforeRecoveryTick();
          return 0;
        }
        '''
    ).lstrip(),
    encoding="utf-8",
)

cmake = CMAKE.read_text(encoding="utf-8")
if "climate_virtual_hil_tests" in cmake:
    raise SystemExit("climate_virtual_hil_tests already present")
anchor = '''target_compile_options(climate_control_loop_tests PRIVATE -Wall -Wextra -Wpedantic)\n\n'''
block = '''target_compile_options(climate_control_loop_tests PRIVATE -Wall -Wextra -Wpedantic)\n\nadd_executable(\n  climate_virtual_hil_tests\n  "${PROJECT_ROOT}/test/test_climate_virtual_hil/test_main.cpp"\n  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateControlLoop.cpp"\n  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateFeatureEncoder.cpp"\n  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateRuntimeController.cpp"\n  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateTrendEstimator.cpp"\n)\ntarget_include_directories(climate_virtual_hil_tests PRIVATE "${PROJECT_ROOT}/lib/environment_control/src/climate")\ntarget_compile_features(climate_virtual_hil_tests PRIVATE cxx_std_17)\ntarget_compile_options(climate_virtual_hil_tests PRIVATE -Wall -Wextra -Wpedantic)\n\n'''
if anchor not in cmake:
    raise SystemExit("host CMake insertion anchor not found")
cmake = cmake.replace(anchor, block, 1)
cmake = cmake.replace(
    "  target_link_libraries(climate_control_loop_tests PRIVATE m)\n",
    "  target_link_libraries(climate_control_loop_tests PRIVATE m)\n  target_link_libraries(climate_virtual_hil_tests PRIVATE m)\n",
    1,
)
cmake = cmake.replace(
    "add_test(NAME climate_control_loop_tests COMMAND climate_control_loop_tests)\n",
    "add_test(NAME climate_control_loop_tests COMMAND climate_control_loop_tests)\nadd_test(NAME climate_virtual_hil_tests COMMAND climate_virtual_hil_tests)\n",
    1,
)
CMAKE.write_text(cmake, encoding="utf-8")
