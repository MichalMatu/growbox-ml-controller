#pragma once

#include "climate/output/OutputExecutionTelemetry.h"

#include <cstdint>

namespace growbox::app::climate_io::runtime {

void logOutputExecutionTelemetry(const output::OutputExecutionTelemetrySnapshot& snapshot,
                                 std::uint32_t transmit_count,
                                 std::uint32_t transmit_error_count) noexcept;

} // namespace growbox::app::climate_io::runtime
