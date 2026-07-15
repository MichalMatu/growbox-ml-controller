#pragma once

#include "EnvironmentTypes.h"

namespace growbox {
namespace control {

class SafetySupervisor {
public:
  SafetySupervisor() noexcept = default;

  void reset() noexcept;

  void apply(const ControllerInput& input, const RawModelDecision& raw,
             SafetyReason upstream_failure, SafeControlDecision& safe,
             SafetyReport& report) noexcept;

  static const char* reasonCode(SafetyReason reason) noexcept;

private:
  struct BinaryRuntime {
    bool initialized = false;
    bool has_transition = false;
    bool on = false;
    std::uint64_t last_transition_ms = 0U;
  };

  struct PumpRuntime {
    bool initialized = false;
    bool has_pulse = false;
    std::uint64_t last_pulse_start_ms = 0U;
  };

  struct PulseRuntime {
    bool initialized = false;
    bool has_pulse = false;
    std::uint64_t last_pulse_start_ms = 0U;
  };

  BinaryRuntime heater_{};
  BinaryRuntime humidifier_{};
  BinaryRuntime dehumidifier_{};
  BinaryRuntime cooler_{};
  std::array<BinaryRuntime, kMaxZones> irrigation_binary_{};
  std::array<PumpRuntime, kMaxZones> zone_pumps_{};
  PulseRuntime co2_doser_{};
};

} // namespace control
} // namespace growbox
