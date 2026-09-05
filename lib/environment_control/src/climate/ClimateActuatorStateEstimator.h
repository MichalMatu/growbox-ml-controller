#pragma once
#include "ClimateTypes.h"
#include <algorithm>
#include <cmath>
namespace growbox::climate {
struct ClimateActuatorLagSeconds {
  float heater = 35.0F;
  float cooler = 45.0F;
  float exhaust_fan = 8.0F;
  float humidifier = 20.0F;
  float dehumidifier = 20.0F;
  float co2_doser = 0.0F;
};
class ClimateActuatorStateEstimator {
public:
  void reset() noexcept {
    state_ = {};
  }
  void setState(const EstimatedEffectiveClimateActions& state) noexcept {
    state_ = state;
  }
  const EstimatedEffectiveClimateActions& state() const noexcept {
    return state_;
  }
  EstimatedEffectiveClimateActions update(const ClimatePolicyRequest& requested, float timestep_s,
                                          const ClimateCapabilities& capabilities,
                                          ClimateActuatorLagSeconds lag = {}) noexcept {
    if (!std::isfinite(timestep_s) || timestep_s <= 0.0F) {
      return state_;
    }
    const auto bounded = [](float value) noexcept {
      if (!std::isfinite(value)) {
        return 0.0F;
      }
      return std::clamp(value, 0.0F, 1.0F);
    };
    const float heater = capabilities.heater ? bounded(requested.heater) : 0.0F;
    const float cooler = capabilities.cooler ? bounded(requested.cooler) : 0.0F;
    const float exhaust = capabilities.exhaust_fan ? bounded(requested.exhaust_fan) : 0.0F;
    const float humidifier = capabilities.humidifier ? bounded(requested.humidifier) : 0.0F;
    const float dehumidifier = capabilities.dehumidifier ? bounded(requested.dehumidifier) : 0.0F;
    const float co2 = capabilities.co2_doser ? bounded(requested.co2_doser) : 0.0F;
    state_.heater = advance(state_.heater, heater, timestep_s, lag.heater);
    state_.cooler = advance(state_.cooler, cooler, timestep_s, lag.cooler);
    state_.exhaust_fan = advance(state_.exhaust_fan, exhaust, timestep_s, lag.exhaust_fan);
    state_.humidifier = advance(state_.humidifier, humidifier, timestep_s, lag.humidifier);
    state_.dehumidifier = advance(state_.dehumidifier, dehumidifier, timestep_s, lag.dehumidifier);
    state_.co2_doser = advance(state_.co2_doser, co2, timestep_s, lag.co2_doser);
    return state_;
  }

private:
  static float advance(float previous, float requested, float dt, float time_constant) noexcept {
    if (!std::isfinite(time_constant) || time_constant <= 0.0F) {
      return requested;
    }
    const float alpha = 1.0F - std::exp(-dt / time_constant);
    return previous + alpha * (requested - previous);
  }
  EstimatedEffectiveClimateActions state_{};
};
} // namespace growbox::climate
