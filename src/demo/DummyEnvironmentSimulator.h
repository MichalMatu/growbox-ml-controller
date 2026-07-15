#pragma once

#include "EnvironmentTypes.h"

#include <array>
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
  void setActuators(const control::GlobalActuatorCapabilities& actuators) noexcept;
  void advance(const control::SafeControlDecision& decision,
               float step_seconds = kDefaultStepSeconds) noexcept;

  control::ControllerInput& input() noexcept {
    return input_;
  }
  const control::ControllerInput& input() const noexcept {
    return input_;
  }
  std::uint32_t seed() const noexcept {
    return initial_seed_;
  }

private:
  static constexpr float kDefaultLightsHeatW = 120.0f;
  static constexpr float kHeaterLagS = 35.0f;
  static constexpr float kFanLagS = 8.0f;
  static constexpr float kHumidifierLagS = 20.0f;
  static constexpr float kDehumidifierLagS = 20.0f;
  static constexpr float kCoolerLagS = 45.0f;

  float uniformSigned() noexcept;
  static float clamp(float value, float lower, float upper) noexcept;
  static float lag(float previous, float requested, float dt, float time_constant) noexcept;
  bool irrigationReady(std::size_t zone_index) const noexcept;
  float zoneEvaporationPctPerSecond(std::size_t zone_index, float vapor_deficit,
                                    float air_temperature_c) const noexcept;
  float irrigationCommand(std::size_t zone_index,
                          const control::SafeControlDecision& decision) const noexcept;

  control::ControllerInput input_{};
  std::uint32_t initial_seed_ = 20260711U;
  std::uint32_t rng_state_ = 20260711U;
  float elapsed_s_ = 0.0f;
  std::array<float, control::kMaxZones> last_irrigation_s_{};
  float effective_heater_ = 0.0f;
  float effective_fan_ = 0.0f;
  float effective_humidifier_ = 0.0f;
  float effective_dehumidifier_ = 0.0f;
  float effective_cooler_ = 0.0f;
};

} // namespace demo
} // namespace growbox
