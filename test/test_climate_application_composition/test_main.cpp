#include "climate/ClimateApplication.h"

#include <array>
#include <cassert>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <utility>
#include <vector>

using namespace growbox::app::climate_io;
using namespace growbox::climate;

namespace {

constexpr std::size_t kRoleCount = 6U;
constexpr std::array<ClimateActuatorRole, kRoleCount> kExpectedRoles{
    ClimateActuatorRole::Heater,       ClimateActuatorRole::Cooler,
    ClimateActuatorRole::ExhaustFan,   ClimateActuatorRole::Humidifier,
    ClimateActuatorRole::Dehumidifier, ClimateActuatorRole::Co2Doser,
};

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
         near(left.exhaust_fan, right.exhaust_fan) && near(left.humidifier, right.humidifier) &&
         near(left.dehumidifier, right.dehumidifier) && near(left.co2_doser, right.co2_doser);
}

bool samePrevious(const PreviousClimateActions& previous, const ClimatePolicyRequest& request) {
  return near(previous.heater, request.heater) && near(previous.cooler, request.cooler) &&
         near(previous.exhaust_fan, request.exhaust_fan) &&
         near(previous.humidifier, request.humidifier) &&
         near(previous.dehumidifier, request.dehumidifier) &&
         near(previous.co2_doser, request.co2_doser);
}

ClimateInputSnapshot snapshotFor(float temperature_c, float humidity_pct = 60.0F,
                                 float co2_ppm = 500.0F) {
  ClimateInputSnapshot snapshot{};
  snapshot.measurements.air_temperature_c = {temperature_c, true, 0U};
  snapshot.measurements.relative_humidity_pct = {humidity_pct, true, 0U};
  snapshot.measurements.co2_ppm = {co2_ppm, true, 0U};
  snapshot.measurements.outside_temperature_c = {10.0F, true, 0U};
  snapshot.measurements.outside_humidity_pct = {50.0F, true, 0U};
  snapshot.targets.air_temperature_c = 24.0F;
  snapshot.targets.relative_humidity_pct = 60.0F;
  snapshot.targets.air_vpd_kpa = 1.2F;
  snapshot.targets.co2_enabled = true;
  snapshot.targets.co2_ppm = 950.0F;
  snapshot.schedule.light_level = 0.6F;
  snapshot.capabilities.heater = true;
  snapshot.capabilities.cooler = true;
  snapshot.capabilities.exhaust_fan = true;
  snapshot.capabilities.humidifier = true;
  snapshot.capabilities.dehumidifier = true;
  snapshot.capabilities.co2_doser = true;
  snapshot.sensor_timeout_ms = 30'000U;
  return snapshot;
}

struct SnapshotFrame {
  bool available = true;
  ClimateInputSnapshot snapshot{};
};

class ScriptedSnapshotProvider final : public ClimateSnapshotProvider {
public:
  explicit ScriptedSnapshotProvider(std::vector<SnapshotFrame> frames)
      : frames_(std::move(frames)) {}

  bool snapshot(std::uint64_t monotonic_ms, ClimateInputSnapshot& output) noexcept override {
    ++calls;
    timestamps.push_back(monotonic_ms);
    if (index_ >= frames_.size()) {
      return false;
    }
    const SnapshotFrame& frame = frames_[index_++];
    if (!frame.available) {
      return false;
    }
    output = frame.snapshot;
    return true;
  }

  std::size_t calls = 0U;
  std::vector<std::uint64_t> timestamps{};

private:
  std::vector<SnapshotFrame> frames_{};
  std::size_t index_ = 0U;
};

class ConstantSnapshotProvider final : public ClimateSnapshotProvider {
public:
  explicit ConstantSnapshotProvider(ClimateInputSnapshot value) : value_(std::move(value)) {}

  bool snapshot(std::uint64_t, ClimateInputSnapshot& output) noexcept override {
    ++calls;
    output = value_;
    return true;
  }

  std::size_t calls = 0U;

private:
  ClimateInputSnapshot value_{};
};

struct RoleCall {
  ClimateActuatorRole role = ClimateActuatorRole::Heater;
  float level = 0.0F;
  std::uint64_t monotonic_ms = 0U;
};

class RecordingRoleDriver final : public ClimateRoleDriver {
public:
  explicit RecordingRoleDriver(std::vector<bool> batch_outcomes = {})
      : batch_outcomes_(std::move(batch_outcomes)) {}

  bool apply(ClimateActuatorRole role, float level, std::uint64_t monotonic_ms) noexcept override {
    const std::size_t batch = calls.size() / kRoleCount;
    const bool batch_ok = batch >= batch_outcomes_.size() ? true : batch_outcomes_[batch];
    calls.push_back(RoleCall{role, level, monotonic_ms});
    return batch_ok || role != ClimateActuatorRole::Heater;
  }

  std::size_t batches() const {
    assert(calls.size() % kRoleCount == 0U);
    return calls.size() / kRoleCount;
  }

  ClimatePolicyRequest requestAt(std::size_t batch) const {
    assert((batch + 1U) * kRoleCount <= calls.size());
    const std::size_t base = batch * kRoleCount;
    ClimatePolicyRequest request{};
    request.heater = calls[base + 0U].level;
    request.cooler = calls[base + 1U].level;
    request.exhaust_fan = calls[base + 2U].level;
    request.humidifier = calls[base + 3U].level;
    request.dehumidifier = calls[base + 4U].level;
    request.co2_doser = calls[base + 5U].level;
    return request;
  }

  std::vector<RoleCall> calls{};

private:
  std::vector<bool> batch_outcomes_{};
};

class CountingRoleDriver final : public ClimateRoleDriver {
public:
  bool apply(ClimateActuatorRole, float, std::uint64_t) noexcept override {
    ++calls;
    return true;
  }

  std::size_t calls = 0U;
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

void assertBatchMapping(const RecordingRoleDriver& driver, std::size_t batch,
                        const ClimatePolicyRequest& request, std::uint64_t monotonic_ms) {
  const std::size_t base = batch * kRoleCount;
  assert((batch + 1U) * kRoleCount <= driver.calls.size());
  const std::array<float, kRoleCount> expected_levels{
      request.heater,     request.cooler,       request.exhaust_fan,
      request.humidifier, request.dehumidifier, request.co2_doser,
  };
  for (std::size_t index = 0U; index < kRoleCount; ++index) {
    assert(driver.calls[base + index].role == kExpectedRoles[index]);
    assert(near(driver.calls[base + index].level, expected_levels[index]));
    assert(driver.calls[base + index].monotonic_ms == monotonic_ms);
  }
}

void testFullIpoRuleSequenceHandlesChangingStaleInvalidAndUnavailableInput() {
  ClimateInputSnapshot stale = snapshotFor(20.0F);
  stale.measurements.air_temperature_c.age_ms = 30'001U;
  ClimateInputSnapshot invalid = snapshotFor(20.0F);
  invalid.measurements.relative_humidity_pct.valid = false;
  ScriptedSnapshotProvider provider({
      {true, snapshotFor(20.0F)},
      {true, snapshotFor(21.0F)},
      {true, snapshotFor(22.0F)},
      {true, stale},
      {true, invalid},
      {false, {}},
      {true, snapshotFor(20.0F)},
  });
  RecordingRoleDriver driver{};
  ClimateRuntimeConfig config{};
  config.sensor_timeout_ms = 30'000U;
  config.timestep_s = 10.0F;
  ClimateRuntimeController runtime(nullptr, config);
  ClimateApplication application(runtime, provider, driver);

  ClimateRuntimeDecision first{};
  ClimateRuntimeDecision second{};
  ClimateRuntimeDecision third{};
  ClimateRuntimeDecision stale_decision{};
  ClimateRuntimeDecision invalid_decision{};
  ClimateRuntimeDecision unavailable_decision{};
  ClimateRuntimeDecision recovered{};

  const auto first_result = application.tick(100'000U, first);
  assert(first_result.io_status == ClimateLoopIoStatus::Ok);
  assert(first_result.input_sampled);
  assert(first.applied.heater > 0.0F);
  assert(samePrevious(application.previousApplied(), first.applied));
  assertBatchMapping(driver, 0U, first.applied, 100'000U);

  const auto second_result = application.tick(110'000U, second);
  assert(second_result.io_status == ClimateLoopIoStatus::Ok);
  assert(first.applied.heater > second.applied.heater);
  assert(near(second.effective_before.heater, first.effective_after.heater));
  assert(samePrevious(application.previousApplied(), second.applied));

  const auto third_result = application.tick(120'000U, third);
  assert(third_result.io_status == ClimateLoopIoStatus::Ok);
  assert(second.applied.heater > third.applied.heater);
  assert(third.trends.temperature.available);
  assert(third.trends.temperature.rate_per_min > 0.0F);
  assert(samePrevious(application.previousApplied(), third.applied));

  const auto stale_result = application.tick(130'000U, stale_decision);
  assert(stale_result.io_status == ClimateLoopIoStatus::Ok);
  assert(stale_result.input_sampled);
  assert(off(stale_decision.applied));
  assert(samePrevious(application.previousApplied(), stale_decision.applied));

  const auto invalid_result = application.tick(140'000U, invalid_decision);
  assert(invalid_result.io_status == ClimateLoopIoStatus::Ok);
  assert(invalid_result.input_sampled);
  assert(off(invalid_decision.applied));

  const auto unavailable_result = application.tick(150'000U, unavailable_decision);
  assert(unavailable_result.io_status == ClimateLoopIoStatus::InputUnavailable);
  assert(!unavailable_result.input_sampled);
  assert(off(unavailable_decision.applied));

  const auto recovered_result = application.tick(160'000U, recovered);
  assert(recovered_result.io_status == ClimateLoopIoStatus::Ok);
  assert(recovered_result.input_sampled);
  assert(recovered.applied.heater > 0.0F);
  assert(provider.calls == 7U);
  assert(driver.batches() == 7U);
  assertBatchMapping(driver, 6U, recovered.applied, 160'000U);
}

void testMlShadowDivergesButRuleSafeOutputRemainsAuthoritative() {
  FixedShadowInference inference{};
  ClimateRuntimeConfig config{};
  config.mode = ClimatePolicyMode::MlShadow;
  config.sensor_timeout_ms = 30'000U;
  ClimateRuntimeController runtime(&inference, config);
  ScriptedSnapshotProvider provider({{true, snapshotFor(20.0F)}, {true, snapshotFor(21.0F)}});
  RecordingRoleDriver driver{};
  ClimateApplication application(runtime, provider, driver);
  ClimateRuntimeDecision decision{};

  for (std::uint64_t now : {200'000ULL, 210'000ULL}) {
    const auto result = application.tick(now, decision);
    assert(result.io_status == ClimateLoopIoStatus::Ok);
    assert(decision.ml_evaluated);
    assert(!decision.authoritative_ml);
    assert(!same(decision.ml.safe, decision.rule.safe));
    assert(same(decision.applied, decision.rule.safe));
    assert(same(driver.requestAt(driver.batches() - 1U), decision.rule.safe));
  }
}

void testRejectedCommandGetsOffRecoveryWithoutPoisoningConfirmedState() {
  ScriptedSnapshotProvider provider({{true, snapshotFor(20.0F)}, {true, snapshotFor(20.0F)}});
  RecordingRoleDriver driver({false, true, true});
  ClimateRuntimeController runtime{};
  ClimateApplication application(runtime, provider, driver);
  ClimateRuntimeDecision failed_decision{};
  ClimateRuntimeDecision recovered_decision{};

  const auto failed = application.tick(300'000U, failed_decision);
  assert(failed.io_status == ClimateLoopIoStatus::ActuatorApplyFailed);
  assert(failed.fail_safe_attempted);
  assert(failed.fail_safe_applied);
  assert(!application.actuatorFaultLatched());
  assert(driver.batches() == 2U);
  assert(!off(driver.requestAt(0U)));
  assert(off(driver.requestAt(1U)));
  assert(samePrevious(application.previousApplied(), ClimatePolicyRequest{}));

  const auto recovered = application.tick(310'000U, recovered_decision);
  assert(recovered.io_status == ClimateLoopIoStatus::Ok);
  assert(recovered.command_applied);
  assert(near(recovered_decision.effective_before.heater, 0.0F));
  assert(recovered_decision.applied.heater > 0.0F);
  assert(driver.batches() == 3U);
  assert(samePrevious(application.previousApplied(), recovered_decision.applied));
}

void testDoubleFailureLatchesSkipsNormalControlAndResetRestoresOperation() {
  ScriptedSnapshotProvider provider({{true, snapshotFor(20.0F)}, {true, snapshotFor(20.0F)}});
  RecordingRoleDriver driver({false, false, true, true});
  ClimateRuntimeController runtime{};
  ClimateApplication application(runtime, provider, driver);
  ClimateRuntimeDecision decision{};

  const auto failed = application.tick(400'000U, decision);
  assert(failed.io_status == ClimateLoopIoStatus::ActuatorApplyFailed);
  assert(failed.fail_safe_attempted);
  assert(!failed.fail_safe_applied);
  assert(application.actuatorFaultLatched());
  assert(provider.calls == 1U);
  assert(driver.batches() == 2U);
  assert(samePrevious(application.previousApplied(), ClimatePolicyRequest{}));

  const auto latched = application.tick(410'000U, decision);
  assert(latched.io_status == ClimateLoopIoStatus::ActuatorFaultLatched);
  assert(!latched.input_sampled);
  assert(latched.fail_safe_attempted);
  assert(latched.fail_safe_applied);
  assert(provider.calls == 1U);
  assert(driver.batches() == 3U);
  assert(off(driver.requestAt(2U)));
  assert(application.actuatorFaultLatched());

  application.reset();
  assert(!application.actuatorFaultLatched());
  assert(samePrevious(application.previousApplied(), ClimatePolicyRequest{}));

  const auto restored = application.tick(420'000U, decision);
  assert(restored.io_status == ClimateLoopIoStatus::Ok);
  assert(restored.input_sampled);
  assert(decision.applied.heater > 0.0F);
  assert(provider.calls == 2U);
  assert(driver.batches() == 4U);
}

void testProviderAndDriverImplementationsAreReplaceableAtCompositionBoundary() {
  ConstantSnapshotProvider provider(snapshotFor(20.0F));
  CountingRoleDriver driver{};
  ClimateRuntimeController runtime{};
  ClimateApplication application(runtime, provider, driver);
  ClimateRuntimeDecision decision{};

  const auto result = application.tick(500'000U, decision);
  assert(result.io_status == ClimateLoopIoStatus::Ok);
  assert(result.input_sampled);
  assert(result.command_applied);
  assert(provider.calls == 1U);
  assert(driver.calls == kRoleCount);
  assert(decision.applied.heater > 0.0F);
}

} // namespace

int main() {
  testFullIpoRuleSequenceHandlesChangingStaleInvalidAndUnavailableInput();
  testMlShadowDivergesButRuleSafeOutputRemainsAuthoritative();
  testRejectedCommandGetsOffRecoveryWithoutPoisoningConfirmedState();
  testDoubleFailureLatchesSkipsNormalControlAndResetRestoresOperation();
  testProviderAndDriverImplementationsAreReplaceableAtCompositionBoundary();
  return 0;
}
