#include "climate/Stage28dBinaryRoleArbiter.h"

#include <algorithm>
#include <atomic>
#include <cmath>
#include <limits>

#if defined(ESP_PLATFORM)
#include <esp_log.h>
#endif

namespace growbox::app::climate_io::stage28d {
namespace {

std::atomic<std::uint32_t> g_binary_arbiter_construction_count{0U};

std::uint32_t nextBinaryArbiterInstanceId() noexcept {
  return g_binary_arbiter_construction_count.fetch_add(1U, std::memory_order_relaxed) + 1U;
}

#if defined(ESP_PLATFORM)
constexpr char kLifecycleTag[] = "stage28e_lifecycle";
#endif

} // namespace

Stage28dBinaryRoleArbiter::Stage28dBinaryRoleArbiter(ClimateRoleDriver& downstream,
                                                     BinaryRoleArbiterConfig config) noexcept
    : downstream_(downstream), config_(config), instance_id_(nextBinaryArbiterInstanceId()) {
  config_.exhaust_fan = sanitized(config_.exhaust_fan);
  config_.humidifier = sanitized(config_.humidifier);
#if defined(ESP_PLATFORM)
  ESP_LOGI(kLifecycleTag, "arbiter_construct instance_id=%lu construction_count=%lu self=%p",
           static_cast<unsigned long>(instance_id_),
           static_cast<unsigned long>(constructionCount()), static_cast<void*>(this));
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

void Stage28dBinaryRoleArbiter::checkCounterContinuity() noexcept {
  const CounterSnapshot current{transition_count_, dwell_hold_count_, safety_override_count_};
  if (!counter_snapshot_initialized_) {
    last_counter_snapshot_ = current;
    counter_snapshot_initialized_ = true;
    return;
  }

  const bool transition_regressed =
      binaryArbiterCounterRegressed(last_counter_snapshot_.transitions, current.transitions);
  const bool dwell_regressed =
      binaryArbiterCounterRegressed(last_counter_snapshot_.dwell_holds, current.dwell_holds);
  const bool safety_regressed = binaryArbiterCounterRegressed(
      last_counter_snapshot_.safety_overrides, current.safety_overrides);
  if (transition_regressed || dwell_regressed || safety_regressed) {
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

void Stage28dBinaryRoleArbiter::synchronizeSafeOff(std::uint64_t monotonic_ms) noexcept {
  checkCounterContinuity();
  exhaust_ = {true, false, monotonic_ms};
  humidifier_ = {true, false, monotonic_ms};
}

bool Stage28dBinaryRoleArbiter::apply(ClimateActuatorRole role, float level,
                                     std::uint64_t monotonic_ms) noexcept {
  checkCounterContinuity();
  if (role == ClimateActuatorRole::ExhaustFan) {
    return applyBinary(role, level, monotonic_ms, config_.exhaust_fan, exhaust_,
                       safety_force_exhaust_);
  }
  if (role == ClimateActuatorRole::Humidifier) {
    return applyBinary(role, level, monotonic_ms, config_.humidifier, humidifier_, false);
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
    return forceBinaryOff(role, monotonic_ms, exhaust_);
  }
  if (role == ClimateActuatorRole::Humidifier) {
    return forceBinaryOff(role, monotonic_ms, humidifier_);
  }
  return downstream_.forceSafeOff(role, monotonic_ms);
}

bool Stage28dBinaryRoleArbiter::applyBinary(ClimateActuatorRole role, float requested_level,
                                           std::uint64_t monotonic_ms,
                                           const BinaryActuatorConfig& config,
                                           BinaryState& state, bool force_on) noexcept {
  const float request = normalized(requested_level);
  bool target_on = false;
  bool bypass_dwell = false;

  if (force_on) {
    target_on = true;
    bypass_dwell = true;
    if (!state.known || !state.on) {
      ++safety_override_count_;
    }
  } else if (!state.known) {
    target_on = request >= config.on_threshold;
  } else if (state.on) {
    target_on = request > config.off_threshold;
  } else {
    target_on = request >= config.on_threshold;
  }

  if (state.known && target_on == state.on) {
    return true;
  }

  if (state.known && !bypass_dwell) {
    const std::uint64_t elapsed_ms =
        monotonic_ms >= state.last_change_ms ? monotonic_ms - state.last_change_ms : 0U;
    const std::uint64_t required_ms = state.on ? config.min_on_ms : config.min_off_ms;
    if (elapsed_ms < required_ms) {
      ++dwell_hold_count_;
      return true;
    }
  }

  if (!downstream_.apply(role, target_on ? 1.0F : 0.0F, monotonic_ms)) {
    return false;
  }

  if (!state.known || state.on != target_on) {
    ++transition_count_;
  }
  state.known = true;
  state.on = target_on;
  state.last_change_ms = monotonic_ms;
  return true;
}

bool Stage28dBinaryRoleArbiter::forceBinaryOff(ClimateActuatorRole role,
                                              std::uint64_t monotonic_ms,
                                              BinaryState& state) noexcept {
  if (!downstream_.forceSafeOff(role, monotonic_ms)) {
    return false;
  }
  if (!state.known || state.on) {
    ++transition_count_;
  }
  state.known = true;
  state.on = false;
  state.last_change_ms = monotonic_ms;
  return true;
}

} // namespace growbox::app::climate_io::stage28d
