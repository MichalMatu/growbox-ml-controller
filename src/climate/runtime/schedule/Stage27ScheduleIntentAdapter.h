#pragma once

#include "climate/application/ClimateCompositeInput.h"
#include "climate/output/OutputIntents.h"

#include <cstdint>

namespace growbox::app::climate_io::runtime {

bool buildStage27ScheduleIntent(std::uint64_t monotonic_ms, const ClimateWallClockSnapshot& clock,
                                std::uint64_t sequence,
                                ::growbox::app::output::ScheduleIntent& output) noexcept;

} // namespace growbox::app::climate_io::runtime
