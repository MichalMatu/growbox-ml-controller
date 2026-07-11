#pragma once

#include "EnvironmentTypes.h"

#include <cstdint>

namespace growbox {
namespace demo {

class DummyEnvironmentSimulator {
 public:
  static constexpr float kDefaultStepSeconds = 10.0f;

  DummyEnvironmentSimulator() noexcept;

  void reset(std::uint32_t seed = 20260711U) noexcept;
  void load(const control::ControllerInput& scenario, std::uint32_t seed) noexcept;
  void setSeed(std::uint32_t seed) noexcept;
  void setSensors(const control::SensorState& sensors,
                  const control::SensorValidity& validity) noexcept;
  void setTargets(const control::ControlTargets& targets) noexcept;
  void advance(const control::SafeControlDecision& decision,
               float step_seconds = kDefaultStepSeconds) noexcept;

  control::ControllerInput& input() noexcept { return input_; }
  const control::ControllerInput& input() const noexcept { return input_; }
  std::uint32_t seed() const noexcept { return initial_seed_; }

 private:
  float uniformSigned() noexcept;
  static float clamp(float value, float lower, float upper) noexcept;

  control::ControllerInput input_{};
  std::uint32_t initial_seed_ = 20260711U;
  std::uint32_t rng_state_ = 20260711U;
  float effective_heater_ = 0.0f;
  float effective_fan_ = 0.0f;
  float effective_humidifier_ = 0.0f;
};

}  // namespace demo
}  // namespace growbox
