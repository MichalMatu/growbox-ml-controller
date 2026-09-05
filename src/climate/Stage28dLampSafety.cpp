#include "climate/Stage28dLampSafety.h"

#include <cmath>

namespace growbox::app::climate_io::stage28d {

bool validateLampSafetyConfig(const LampSafetyConfig& config) noexcept {
  return std::isfinite(config.trip_temperature_c) &&
         std::isfinite(config.recovery_temperature_c) &&
         std::isfinite(config.light_on_threshold) &&
         config.recovery_temperature_c < config.trip_temperature_c &&
         config.light_on_threshold >= 0.0F && config.light_on_threshold <= 1.0F &&
         config.temperature_timeout_ms > 0U;
}

LampSafetyController::LampSafetyController(LampSafetyConfig config) noexcept : config_(config) {}

void LampSafetyController::reset() noexcept {
  thermal_latched_ = false;
  recovery_running_ = false;
  recovery_started_ms_ = 0U;
}

LampSafetyDecision LampSafetyController::evaluate(const LampSafetyInput& input) noexcept {
  LampSafetyDecision output{};
  output.schedule_requests_lamp_on = input.scheduled_light_level >= config_.light_on_threshold;

  if (!validateLampSafetyConfig(config_)) {
    thermal_latched_ = true;
    recovery_running_ = false;
    output.effective_lamp_on = false;
    output.force_exhaust_on = input.exhaust_fan_available;
    output.thermal_latched = true;
    output.reason = LampSafetyReason::InvalidConfig;
    return output;
  }

  const auto& temperature = input.inside_temperature_c;
  const bool temperature_usable = temperature.valid && std::isfinite(temperature.value) &&
                                  temperature.age_ms <= config_.temperature_timeout_ms;
  if (!temperature_usable) {
    thermal_latched_ = true;
    recovery_running_ = false;
    output.effective_lamp_on = false;
    output.force_exhaust_on = input.exhaust_fan_available;
    output.thermal_latched = true;
    output.reason = LampSafetyReason::TemperatureUnavailable;
    return output;
  }

  if (temperature.value >= config_.trip_temperature_c) {
    thermal_latched_ = true;
    recovery_running_ = false;
  }

  if (thermal_latched_) {
    if (temperature.value <= config_.recovery_temperature_c) {
      if (!recovery_running_) {
        recovery_running_ = true;
        recovery_started_ms_ = input.monotonic_ms;
      }
      if ((input.monotonic_ms - recovery_started_ms_) >= config_.recovery_hold_ms) {
        thermal_latched_ = false;
        recovery_running_ = false;
      }
    } else {
      recovery_running_ = false;
    }
  }

  output.thermal_latched = thermal_latched_;
  output.force_exhaust_on = thermal_latched_ && input.exhaust_fan_available;
  if (thermal_latched_) {
    output.effective_lamp_on = false;
    output.reason = temperature.value >= config_.trip_temperature_c
                        ? LampSafetyReason::OverTemperature
                        : LampSafetyReason::RecoveryHold;
    return output;
  }

  output.effective_lamp_on = output.schedule_requests_lamp_on;
  output.reason = output.schedule_requests_lamp_on ? LampSafetyReason::Safe
                                                   : LampSafetyReason::TimerOff;
  return output;
}

} // namespace growbox::app::climate_io::stage28d
