#pragma once

#include "climate/ClimateIoAdapters.h"

#include <cstdint>

namespace growbox::app::climate_io {

class DeterministicClimateScenarioProvider final : public ClimateSnapshotProvider {
public:
  static constexpr std::uint64_t kTickIntervalMs = 1'000U;
  static constexpr std::uint32_t kPeriodTicks = 240U;

  bool snapshot(std::uint64_t monotonic_ms, ClimateInputSnapshot& output) noexcept override;

  static std::uint32_t phaseTick(std::uint64_t monotonic_ms) noexcept;
};

} // namespace growbox::app::climate_io
