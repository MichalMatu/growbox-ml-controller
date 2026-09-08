#include "climate/Stage28dBinaryRoleArbiter.h"

#include <algorithm>
#include <atomic>
#include <cmath>
#include <limits>

#if defined(ESP_PLATFORM)
#include "climate/runtime/Stage28eBreadcrumbs.h"

#include <esp_log.h>
#include <esp_timer.h>
#endif

namespace growbox::app::climate_io::stage28d {
namespace {

std::atomic<std::uint32_t> g_binary_arbiter_construction_count{0U};

std::uint32_t nextBinaryArbiterInstanceId() noexcept {
  return g_binary_arbiter_construction_count.fetch_add(1U, std::memory_order_relaxed) + 1U;
}

#if defined(ESP_PLATFORM)
constexpr char kLifecycleTag[] = "stage28e_lifecycle";

std::uint64_t arbiterUptimeMs() noexcept {
  const std::int64_t monotonic_us = esp_timer_get_time();
  return monotonic_us > 0 ? static_cast<std::uint64_t>(monotonic_us) / 1000U : 0U;
}

void recordArbiterBreadcrumb(std::uint32_t instance_id, std::uint32_t construction_count,
                             std::uint32_t transition_count, std::uint32_t dwell_hold_count,
                             std::uint32_t safety_override_count,
                             std::uint32_t continuity_fault_count,
                             bool continuity_fault) noexcept {
  runtime::recordStage28eBreadcrumbArbiter(
      arbiterUptimeMs(), instance_id, construction_count, transition_count, dwell_hold_count,
      safety_override_count, continuity_fault_count, continuity_fault);
}
#endif

} // namespace

Stage28dBinaryRoleArbiter::Stage28dBinaryRoleArbiter(ClimateRoleDriver& downstream,
                                                     BinaryRoleArbiterConfig config) noexcept
    : downstream_(downstream), config_(config), instance_id_(nextBinaryArbiterInstanceId()),
      exhaust_policy_(policyConfig(config.exhaust_fan)),
      humidifier_policy_(policyConfig(config.humidifier)) {
  config_.exhaust_fan = sanitized(config_.exhaust_fan);
  config_.humidifier = sanitized(config_.humidifier);
#if defined(ESP_PLATFORM)
  ESP_LOGI(kLifecycleTag, "arbiter_construct instance_id=%lu construction_count=%lu self=%p",
           static_cast<unsigned long>(instance_id_),
           static_cast<unsigned long>(constructionCount()), static_cast<void*>(this));
  recordArbiterBreadcrumb(instance_id_, constructionCount(), transition_count_, dwell_hold_count_,
                          safety_override_count_, continuity_fault_count_, false);
#endif
}

std::uint32_t Stage28dBinaryRoleArbiter::constructionCount() noexcept {
  return g_binary_arbiter_construction_count.load(std::memory_order_relaxed);
}

bool binaryArbiterCounterRegressed(std::uint32_t previous, std::uint32_t current,
                                   std::uint32_t maximum_expected_advance) noexcept {
  if (current >= previous) {
    return false;
  }
  const std::uint32_t modulo_delta = current - previous;
  return modulo_delta > maximum_expected_advance;
}

void Stage28dBinaryRoleArbiter::syncPolicyCounters() noexcept {
  transition_count_ = exhaust_policy_.transitionCount() + humidifier_policy_.transitionCount();
  dwell_hold_count_ = exhaust_policy_.dwellHoldCount() + humidifier_policy_.dwellHoldCount();
}

void Stage28dBinaryRoleArbiter::checkCounterContinuity() noexcept {
  const CounterSnapshot current{transition_count_, dwell_hold_count_, safety_override_count_};
  if (!counter_snapshot_initialized_) {
    last_counter_snapshot_ = current;
    counter_snapshot_initialized_ = true;
#if defined(ESP_PLATFORM)
    recordArbiterBreadcrumb(instance_id_, constructionCount(), current.transitions,
                            current.dwell_holds, current.safety_overrides,
                            continuity_fault_count_, false);
#endif
    return;
  }

  const bool transition_regressed =
      binaryArbiterCounterRegressed(last_counter_snapshot_.transitions, current.transitions);
  const bool dwell_regressed =
      binaryArbiterCounterRegressed(last_counter_snapshot_.dwell_holds, current.dwell_holds);
  const bool safety_regressed = binaryArbiterCounterRegressed(
      last_counter_snapshot_.safety_overrides, current.safety_overrides);
  const bool continuity_fault = transition_regressed || dwell_regressed || safety_regressed;
  if (continuity_fault) {
    if (continuity_fault_count_ != std::numeric_limits<std::uint32_t>::max()) {
      ++continuity_fault_count_;
    }
#if defined(ESP_PLATFORM)
    ESP_LOGE(kLifecycleTag,
             "arbiter_counter_regression instance_id=%lu faults=%lu transition=%lu/%lu "
             "dwell=%lu/%lu safety=%lu/%lu",
             static_cast<unsigned long>(instance_id_),
             static_cast<unsigned long>(continuity_fault_count_),
             static_cast<unsigned long>(last_counter_snapshot_.transitions),
             static_cast<unsigned long>(current.transitions),
             static_cast<unsigned long>(last_counter_snapshot_.dwell_holds),
             static_cast<unsigned long>(current.dwell_holds),
             static_cast<unsigned long>(last_counter_snapshot_.safety_overrides),
             static_cast<unsigned long>(current.safety_overrides));
#endif
  }
  last_counter_snapshot_ = current;
#if defined(ESP_PLATFORM)
  recordArbiterBreadcrumb(instance_id_, constructionCount(), current.transitions,
                          current.dwell_holds, current.safety_overrides,
                          continuity_fault_count_, continuity_fault);
#endif
}

float Stage28dBinaryRoleArbiter::normalized(float value) noexcept {
  if (!std::isfinite(value)) {
    return 0.0F;
  }
  return std::clamp(value, 0.0F, 1.0F);
}

BinaryActuatorConfig Stage28dBinaryRoleArbiter::sanitized(BinaryActuatorConfig config) noexcept {
  config.on_threshold = normalized(config.on_threshold);
  config.off_threshold = normalized(config.off_threshold);
  if (config.off_threshold > config.on_threshold) {
    config.off_threshold = config.on_threshold;
  }
  return config;
}

::growbox::app::output::BinaryActuatorPolicyConfig
Stage28dBinaryRoleArbiter::policyConfig(BinaryActuatorConfig config) noexcept {
  config = sanitized(config);
  return {config.on_threshold, config.off_threshold, config.min_on_ms, config.min_off_ms};
}

void Stage28dBinaryRoleArbiter::synchronizeSafeOff(std::uint64_t monotonic_ms) noexcept {
  checkCounterContinuity();
  exhaust_policy_.synchronize(::growbox::app::output::BinaryOutputState::Off, monotonic_ms);
  humidifier_policy_.synchronize(::growbox::app::output::BinaryOutputState::Off, monotonic_ms);
  syncPolicyCounters();
  exhaust_ = {true, false, monotonic_ms};
  humidifier_ = {true, false, monotonic_ms};
}

bool Stage28dBinaryRoleArbiter::apply(ClimateActuatorRole role, float level,
                                     std::uint64_t monotonic_ms) noexcept {
  checkCounterContinuity();
  if (role == ClimateActuatorRole::ExhaustFan) {
    return applyBinary(role, level, monotonic_ms, exhaust_policy_, exhaust_,
                       safety_force_exhaust_);
  }
  if (role == ClimateActuatorRole::Humidifier) {
    return applyBinary(role, level, monotonic_ms, humidifier_policy_, humidifier_, false);
  }
  return downstream_.apply(role, level, monotonic_ms);
}

float Stage28dBinaryRoleArbiter::appliedLevel(ClimateActuatorRole role,
                                             float requested_level) const noexcept {
  if (role == ClimateActuatorRole::ExhaustFan && exhaust_.known) {
    return exhaust_.on ? 1.0F : 0.0F;
  }
  if (role == ClimateActuatorRole::Humidifier && humidifier_.known) {
    return humidifier_.on ? 1.0F : 0.0F;
  }
  return downstream_.appliedLevel(role, requested_level);
}

bool Stage28dBinaryRoleArbiter::forceSafeOff(ClimateActuatorRole role,
                                            std::uint64_t monotonic_ms) noexcept {
  checkCounterContinuity();
  if (role == ClimateActuatorRole::ExhaustFan) {
    return forceBinaryOff(role, monotonic_ms, exhaust_policy_, exhaust_);
  }
  if (role == ClimateActuatorRole::Humidifier) {
    return forceBinaryOff(role, monotonic_ms, humidifier_policy_, humidifier_);
  }
  return downstream_.forceSafeOff(role, monotonic_ms);
}

bool Stage28dBinaryRoleArbiter::applyBinary(
    ClimateActuatorRole role, float requested_level, std::uint64_t monotonic_ms,
    ::growbox::app::output::BinaryActuatorPolicy& policy, BinaryState& state,
    bool force_on) noexcept {
  const auto override_mode = force_on ? ::growbox::app::output::BinaryPolicyOverride::ForceOn
                                      : ::growbox::app::output::BinaryPolicyOverride::None;
  const auto proposal = policy.propose(requested_level, monotonic_ms, override_mode);
  if (force_on && proposal.override_applied) {
    ++safety_override_count_;
  }
  syncPolicyCounters();

  if (!proposal.command_required) {
    return true;
  }

  const bool target_on = proposal.target == ::growbox::app::output::BinaryOutputState::On;
  if (!downstream_.apply(role, target_on ? 1.0F : 0.0F, monotonic_ms)) {
    (void)policy.commit(proposal, false);
    syncPolicyCounters();
    return false;
  }

  if (!policy.commit(proposal, true)) {
    syncPolicyCounters();
    return false;
  }
  syncPolicyCounters();
  state.known = policy.known();
  state.on = policy.on();
  state.last_change_ms = policy.lastChangeMs();
  return true;
}

bool Stage28dBinaryRoleArbiter::forceBinaryOff(
    ClimateActuatorRole role, std::uint64_t monotonic_ms,
    ::growbox::app::output::BinaryActuatorPolicy& policy, BinaryState& state) noexcept {
  const auto proposal = policy.propose(0.0F, monotonic_ms,
                                       ::growbox::app::output::BinaryPolicyOverride::ForceOff);
  if (!downstream_.forceSafeOff(role, monotonic_ms)) {
    if (proposal.command_required) {
      (void)policy.commit(proposal, false);
    }
    syncPolicyCounters();
    return false;
  }

  if (proposal.command_required) {
    if (!policy.commit(proposal, true)) {
      syncPolicyCounters();
      return false;
    }
  } else {
    policy.synchronize(::growbox::app::output::BinaryOutputState::Off, monotonic_ms);
  }
  syncPolicyCounters();
  state.known = policy.known();
  state.on = policy.on();
  state.last_change_ms = policy.lastChangeMs();
  return true;
}

} // namespace growbox::app::climate_io::stage28d
