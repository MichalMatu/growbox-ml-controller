#pragma once

#include "climate/ClimateCompositeInput.h"

#include <cstdint>

namespace growbox::app::climate_io::runtime {

bool buildMintScheduleProfile(std::uint8_t local_hour,
                              ClimateScheduleConfigSnapshot& output) noexcept;

} // namespace growbox::app::climate_io::runtime
