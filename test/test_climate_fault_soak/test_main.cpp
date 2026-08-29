#include "climate/ClimateApplication.h"

#include <cassert>
#include <cmath>
#include <cstddef>
#include <cstdint>

using namespace growbox::app::climate_io;
using namespace growbox::climate;

namespace {

constexpr std::size_t kRoleCount = 6U;
constexpr std::uint64_t kTickMs = 1'000U;

bool near(float left, float right, float tolerance = 1.0e-5F) {
  return std::fabs(left - right) <= tolerance;
}

bool off(const ClimatePolicyRequest& request) {
  return near(request.heater, 0.0F) && near(request.cooler, 0.0F) &&
         near(request.exhaust_fan, 0.0F) && near(request.humidifier, 0.0F) &&
         near(request.dehumidifier, 0.0F) && near(request.co2_doser, 0.0F);
}

bool off(const PreviousClimateActions& actions) {
  return near(actions.heater, 0.0F) && near(actions.cooler, 0.0F) &&
         near(actions.exhaust_fan, 0.0F) && near(actions.humidifier, 0.0F) &&
         near(actions.dehumidifier, 0.0F) && near(actions.co2_doser, 0.0F);
}

bool off(const EstimatedEffectiveClimateActions& actions) {
  return near(actions.heater, 0.0F) && near(actions.cooler, 0.0F) &&
         near(actions.exhaust_fan, 0.0F) && near(actions.humidifier, 0.0F) &&
         near(actions.dehumidifier, 0.0F) && near(actions.co2_doser, 0.0F);
}

ClimateInputSnapshot nominalSnapshot() {
  ClimateInputSnapshot snapshot{};
  snapshot.measurements.air_temperature_c = {20.0F, true, 0U};
  snapshot.measurements.relative_humidity_pct = {58.0F, true, 0U};
  snapshot.measurements.co2_ppm = {500.0F, true, 0U};
  snapshot.measurements.outside_temperature_c = {14.0F, true, 0U};
  snapshot.measurements.outside_humidity_pct = {48.0F, true, 0U};
  snapshot.targets.air_temperature_c = 24.0F;
  snapshot.targets.relative_humidity_pct = 60.0F;
  snapshot.targets.air_vpd_kpa = 1.2F;
  snapshot.targets.co2_enabled = true;
  snapshot.targets.co2_ppm = 950.0F;
  snapshot.schedule.light_level = 0.7F;
  snapshot.capabilities.heater = true;
  snapshot.capabilities.cooler = true;
  snapshot.capabilities.exhaust_fan = true;
  snapshot.capabilities.humidifier = true;
  snapshot.capabilities.dehumidifier = true;
  snapshot.capabilities.co2_doser = true;
  snapshot.sensor_timeout_ms = kDefaultSensorTimeoutMs;
  return snapshot;
}

class CyclicFaultProvider final : public ClimateSnapshotProvider {
public:
  static constexpr std::uint64_t kCycleTicks = 8U;

  bool snapshot(std::uint64_t monotonic_ms, ClimateInputSnapshot& output) noexcept override {
    ++calls;
    const std::uint64_t phase = (monotonic_ms / kTickMs) % kCycleTicks;
    if (phase == 4U) {
      ++unavailable;
      return false;
    }

    output = nominalSnapshot();
    if (phase == 1U) {
      output.measurements.air_temperature_c.age_ms = output.sensor_timeout_ms;
      ++timeout_boundary;
    } else if (phase == 2U) {
      output.measurements.air_temperature_c.age_ms = output.sensor_timeout_ms + 1U;
      ++stale;
    } else if (phase == 3U) {
      output.measurements.relative_humidity_pct.valid = false;
      ++invalid;
    } else if (phase == 5U) {
      output.capabilities.heater = false;
      output.capabilities.co2_doser = false;
      ++capability_limited;
    } else if (phase == 6U) {
      ++recovered;
    }
    return true;
  }

  std::size_t calls = 0U;
  std::size_t timeout_boundary = 0U;
  std::size_t stale = 0U;
  std::size_t invalid = 0U;
  std::size_t unavailable = 0U;
  std::size_t capability_limited = 0U;
  std::size_t recovered = 0U;
};

class AcceptAllRoleDriver final : public ClimateRoleDriver {
public:
  bool apply(ClimateActuatorRole, float, std::uint64_t) noexcept override {
    ++role_calls;
    return true;
  }

  std::size_t batches() const {
    assert(role_calls % kRoleCount == 0U);
    return role_calls / kRoleCount;
  }

  std::size_t role_calls = 0U;
};

class PeriodicRejectRoleDriver final : public ClimateRoleDriver {
public:
  bool apply(ClimateActuatorRole role, float, std::uint64_t monotonic_ms) noexcept override {
    if (monotonic_ms != last_monotonic_ms_) {
      last_monotonic_ms_ = monotonic_ms;
      calls_at_timestamp_ = 0U;
    }
    const std::size_t batch_at_timestamp = calls_at_timestamp_ / kRoleCount;
    ++calls_at_timestamp_;
    ++role_calls;

    const bool reject_primary = ((monotonic_ms / kTickMs) % 37U) == 0U;
    if (reject_primary && batch_at_timestamp == 0U && role == ClimateActuatorRole::Heater) {
      ++rejected_batches;
      return false;
    }
    return true;
  }

  std::size_t role_calls = 0U;
  std::size_t rejected_batches = 0U;

private:
  std::uint64_t last_monotonic_ms_ = static_cast<std::uint64_t>(-1);
  std::size_t calls_at_timestamp_ = 0U;
};

class DoubleRejectThenAcceptDriver final : public ClimateRoleDriver {
public:
  bool apply(ClimateActuatorRole role, float, std::uint64_t monotonic_ms) noexcept override {
    if (monotonic_ms != last_monotonic_ms_) {
      last_monotonic_ms_ = monotonic_ms;
      calls_at_timestamp_ = 0U;
    }
    const std::size_t batch_at_timestamp = calls_at_timestamp_ / kRoleCount;
    ++calls_at_timestamp_;
    ++role_calls;

    if (monotonic_ms == kTickMs && batch_at_timestamp < 2U && role == ClimateActuatorRole::Heater) {
      return false;
    }
    return true;
  }

  std::size_t role_calls = 0U;

private:
  std::uint64_t last_monotonic_ms_ = static_cast<std::uint64_t>(-1);
  std::size_t calls_at_timestamp_ = 0U;
};

class ConstantProvider final : public ClimateSnapshotProvider {
public:
  bool snapshot(std::uint64_t, ClimateInputSnapshot& output) noexcept override {
    ++calls;
    output = nominalSnapshot();
    return true;
  }

  std::size_t calls = 0U;
};

ClimateRuntimeConfig ruleConfig() {
  ClimateRuntimeConfig config{};
  config.mode = ClimatePolicyMode::Rule;
  config.sensor_timeout_ms = kDefaultSensorTimeoutMs;
  config.timestep_s = 1.0F;
  return config;
}

void testLongInputFaultCapabilityAndRecoveryCycle() {
  CyclicFaultProvider provider;
  AcceptAllRoleDriver driver;
  ClimateRuntimeController runtime(nullptr, ruleConfig());
  ClimateApplication application(runtime, provider, driver);

  constexpr std::size_t kTicks = 4'800U;
  for (std::size_t index = 0U; index < kTicks; ++index) {
    const std::uint64_t now_ms = static_cast<std::uint64_t>(index) * kTickMs;
    const std::uint64_t phase = index % CyclicFaultProvider::kCycleTicks;
    ClimateRuntimeDecision decision{};
    const ClimateLoopResult result = application.tick(now_ms, decision);

    if (phase == 4U) {
      assert(result.io_status == ClimateLoopIoStatus::InputUnavailable);
      assert(!result.input_sampled);
      assert(off(decision.rule.raw));
      assert(off(decision.rule.arbitrated));
      assert(off(decision.rule.safe));
      assert(off(decision.applied));
    } else {
      assert(result.input_sampled);
      assert(result.command_applied);
      assert(result.io_status == ClimateLoopIoStatus::Ok);
    }

    if (phase == 1U) {
      assert((decision.rule.safety_interventions & RequiredSensorUnusable) == 0U);
      assert(decision.applied.heater > 0.0F);
    } else if (phase == 2U || phase == 3U) {
      assert(off(decision.rule.raw));
      assert(off(decision.rule.arbitrated));
      assert(off(decision.rule.safe));
      assert(off(decision.applied));
    } else if (phase == 5U) {
      assert(near(decision.rule.raw.heater, 0.0F));
      assert(near(decision.rule.raw.co2_doser, 0.0F));
      assert(near(decision.applied.heater, 0.0F));
      assert(near(decision.applied.co2_doser, 0.0F));
    } else if (phase == 6U) {
      assert(decision.applied.heater > 0.0F);
    }

    assert(!application.actuatorFaultLatched());
  }

  assert(provider.calls == kTicks);
  assert(provider.timeout_boundary == 600U);
  assert(provider.stale == 600U);
  assert(provider.invalid == 600U);
  assert(provider.unavailable == 600U);
  assert(provider.capability_limited == 600U);
  assert(provider.recovered == 600U);
  assert(driver.batches() == kTicks);
}

void testPeriodicRejectionSoakNeverConfirmsRejectedState() {
  ConstantProvider provider;
  PeriodicRejectRoleDriver driver;
  ClimateRuntimeController runtime(nullptr, ruleConfig());
  ClimateApplication application(runtime, provider, driver);

  constexpr std::size_t kTicks = 1'000U;
  bool previous_tick_rejected = false;
  std::size_t rejected_ticks = 0U;
  for (std::size_t index = 1U; index <= kTicks; ++index) {
    const std::uint64_t now_ms = static_cast<std::uint64_t>(index) * kTickMs;
    ClimateRuntimeDecision decision{};
    const ClimateLoopResult result = application.tick(now_ms, decision);
    const bool should_reject = (index % 37U) == 0U;

    if (previous_tick_rejected) {
      assert(off(decision.effective_before));
    }

    if (should_reject) {
      ++rejected_ticks;
      assert(result.io_status == ClimateLoopIoStatus::ActuatorApplyFailed);
      assert(!result.command_applied);
      assert(result.fail_safe_attempted);
      assert(result.fail_safe_applied);
      assert(off(application.previousApplied()));
      assert(!application.actuatorFaultLatched());
    } else {
      assert(result.io_status == ClimateLoopIoStatus::Ok);
      assert(result.command_applied);
    }
    previous_tick_rejected = should_reject;
  }

  assert(provider.calls == kTicks);
  assert(rejected_ticks == kTicks / 37U);
  assert(driver.rejected_batches == rejected_ticks);
}

void testOffRejectionLatchesUntilExplicitReset() {
  ConstantProvider provider;
  DoubleRejectThenAcceptDriver driver;
  ClimateRuntimeController runtime(nullptr, ruleConfig());
  ClimateApplication application(runtime, provider, driver);

  ClimateRuntimeDecision failed_decision{};
  const ClimateLoopResult failed = application.tick(kTickMs, failed_decision);
  assert(failed.io_status == ClimateLoopIoStatus::ActuatorApplyFailed);
  assert(failed.fail_safe_attempted);
  assert(!failed.fail_safe_applied);
  assert(application.actuatorFaultLatched());
  assert(off(application.previousApplied()));
  assert(provider.calls == 1U);

  ClimateRuntimeDecision latched_decision{};
  const ClimateLoopResult latched = application.tick(2U * kTickMs, latched_decision);
  assert(latched.io_status == ClimateLoopIoStatus::ActuatorFaultLatched);
  assert(latched.fail_safe_attempted);
  assert(latched.fail_safe_applied);
  assert(latched.command_applied);
  assert(application.actuatorFaultLatched());
  assert(off(application.previousApplied()));
  assert(provider.calls == 1U);

  application.reset();
  assert(!application.actuatorFaultLatched());
  assert(off(application.previousApplied()));

  ClimateRuntimeDecision recovered_decision{};
  const ClimateLoopResult recovered = application.tick(3U * kTickMs, recovered_decision);
  assert(recovered.io_status == ClimateLoopIoStatus::Ok);
  assert(recovered.input_sampled);
  assert(recovered.command_applied);
  assert(recovered_decision.applied.heater > 0.0F);
  assert(off(recovered_decision.effective_before));
  assert(provider.calls == 2U);
}

void testRepeatedResetKeepsRecoveryDeterministic() {
  ConstantProvider provider;
  AcceptAllRoleDriver driver;
  ClimateRuntimeController runtime(nullptr, ruleConfig());
  ClimateApplication application(runtime, provider, driver);

  for (std::size_t cycle = 0U; cycle < 100U; ++cycle) {
    ClimateRuntimeDecision before_reset{};
    const std::uint64_t base = static_cast<std::uint64_t>(cycle * 2U + 1U) * kTickMs;
    assert(application.tick(base, before_reset).io_status == ClimateLoopIoStatus::Ok);
    assert(before_reset.applied.heater > 0.0F);
    application.reset();
    assert(off(application.previousApplied()));
    assert(!application.actuatorFaultLatched());

    ClimateRuntimeDecision after_reset{};
    assert(application.tick(base + kTickMs, after_reset).io_status == ClimateLoopIoStatus::Ok);
    assert(off(after_reset.effective_before));
    assert(after_reset.applied.heater > 0.0F);
  }
}

} // namespace

int main() {
  testLongInputFaultCapabilityAndRecoveryCycle();
  testPeriodicRejectionSoakNeverConfirmsRejectedState();
  testOffRejectionLatchesUntilExplicitReset();
  testRepeatedResetKeepsRecoveryDeterministic();
  return 0;
}
