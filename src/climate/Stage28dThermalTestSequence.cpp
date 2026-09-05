#include "climate/Stage28dThermalTestSequence.h"

namespace growbox::app::climate_io::stage28d {

std::uint64_t ThermalTestSequence::completionTimeMs() const noexcept {
  return config_.safe_ms + config_.trip_ms + config_.hot_ms + config_.recovery_above_ms +
         config_.recovery_hold_ms;
}

ThermalTestPoint ThermalTestSequence::sample(std::uint64_t elapsed_ms) const noexcept {
  std::uint64_t cursor = 0U;
  cursor += config_.safe_ms;
  if (elapsed_ms < cursor) {
    return {ThermalTestPhase::Safe, 27.5F, 1.0F, false};
  }
  cursor += config_.trip_ms;
  if (elapsed_ms < cursor) {
    return {ThermalTestPhase::Trip, 28.0F, 1.0F, false};
  }
  cursor += config_.hot_ms;
  if (elapsed_ms < cursor) {
    return {ThermalTestPhase::Hot, 29.0F, 1.0F, false};
  }
  cursor += config_.recovery_above_ms;
  if (elapsed_ms < cursor) {
    return {ThermalTestPhase::RecoveryAbove, 27.0F, 1.0F, false};
  }
  cursor += config_.recovery_hold_ms;
  if (elapsed_ms < cursor) {
    return {ThermalTestPhase::RecoveryHold, 26.0F, 1.0F, false};
  }
  return {ThermalTestPhase::Complete, 26.0F, 0.0F, true};
}

const char* thermalTestPhaseName(ThermalTestPhase phase) noexcept {
  switch (phase) {
  case ThermalTestPhase::Safe:
    return "safe";
  case ThermalTestPhase::Trip:
    return "trip";
  case ThermalTestPhase::Hot:
    return "hot";
  case ThermalTestPhase::RecoveryAbove:
    return "recovery-above";
  case ThermalTestPhase::RecoveryHold:
    return "recovery-hold";
  case ThermalTestPhase::Complete:
    return "complete";
  }
  return "unknown";
}

} // namespace growbox::app::climate_io::stage28d
