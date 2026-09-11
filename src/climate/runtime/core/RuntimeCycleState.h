#pragma once

#include <cstdint>

namespace growbox::app::climate_io::runtime {

class RuntimeCycleState final {
public:
  explicit RuntimeCycleState(std::uint64_t output_intent_sequence = 0U,
                             std::uint32_t diagnostic_tick = 0U) noexcept
      : output_intent_sequence_(output_intent_sequence), diagnostic_tick_(diagnostic_tick) {}

  std::uint64_t nextOutputIntentSequence() noexcept;
  bool telemetryDue() noexcept;

  std::uint64_t outputIntentSequence() const noexcept {
    return output_intent_sequence_;
  }

  std::uint32_t diagnosticTick() const noexcept {
    return diagnostic_tick_;
  }

private:
  static constexpr std::uint32_t kTelemetryEveryTicks = 10U;

  std::uint64_t output_intent_sequence_{0U};
  std::uint32_t diagnostic_tick_{0U};
};

} // namespace growbox::app::climate_io::runtime
