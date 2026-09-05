#pragma once

#include <cstdint>

namespace growbox::app::climate_io::stage28d {

enum class ThermalTestPhase : std::uint8_t {
  Safe = 0U,
  Trip,
  Hot,
  RecoveryAbove,
  RecoveryHold,
  Complete,
};

struct ThermalTestPoint {
  ThermalTestPhase phase{ThermalTestPhase::Safe};
  float temperature_c{27.5F};
  float scheduled_light_level{1.0F};
  bool complete{false};
};

struct ThermalTestSequenceConfig {
  std::uint64_t safe_ms{20'000U};
  std::uint64_t trip_ms{20'000U};
  std::uint64_t hot_ms{20'000U};
  std::uint64_t recovery_above_ms{20'000U};
  std::uint64_t recovery_hold_ms{610'000U};
};

class ThermalTestSequence {
public:
  explicit ThermalTestSequence(ThermalTestSequenceConfig config = {}) noexcept : config_(config) {}

  ThermalTestPoint sample(std::uint64_t elapsed_ms) const noexcept;
  std::uint64_t completionTimeMs() const noexcept;

private:
  ThermalTestSequenceConfig config_{};
};

const char* thermalTestPhaseName(ThermalTestPhase phase) noexcept;

} // namespace growbox::app::climate_io::stage28d
