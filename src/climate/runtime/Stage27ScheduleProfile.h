#pragma once

#include "climate/application/ClimateCompositeInput.h"

#include <cstdint>

namespace growbox::app::climate_io::runtime {

bool buildMintScheduleProfile(std::uint8_t local_hour,
                              ClimateScheduleConfigSnapshot& output) noexcept;

bool resolveMintScheduleProfile(const ClimateWallClockSnapshot& clock,
                                ClimateScheduleConfigSnapshot& output) noexcept;

} // namespace growbox::app::climate_io::runtime
