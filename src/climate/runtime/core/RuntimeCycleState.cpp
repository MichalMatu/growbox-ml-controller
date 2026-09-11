#include "climate/runtime/core/RuntimeCycleState.h"

#include <limits>

namespace growbox::app::climate_io::runtime {

std::uint64_t RuntimeCycleState::nextOutputIntentSequence() noexcept {
  ++output_intent_sequence_;
  if (output_intent_sequence_ == 0U) {
    ++output_intent_sequence_;
  }
  return output_intent_sequence_;
}

bool RuntimeCycleState::telemetryDue() noexcept {
  const bool due = (diagnostic_tick_ % kTelemetryEveryTicks) == 0U;
  ++diagnostic_tick_;
  return due;
}

} // namespace growbox::app::climate_io::runtime
