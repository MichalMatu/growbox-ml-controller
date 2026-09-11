#pragma once

#include "climate/rf433/Rf433ProtocolCodec.h"

#include <cstddef>
#include <cstdint>

namespace growbox::app::climate_io::rf433 {

inline constexpr std::size_t kRmtMemorySymbols = 64U;

// Stage28C hardware-qualified receive tuning. The 20 ms idle threshold is
// intentionally above the longest pulse/gap in the frozen protocol-2 socket
// frames while still allowing noisy receiver captures to terminate reliably.
inline constexpr std::uint32_t kRxMinimumSignalNs = 10'000U;
inline constexpr std::uint32_t kRxMaximumSignalNs = 20'000'000U;
inline constexpr std::uint32_t kRxResolutionHz = kRmtResolutionHz;
inline constexpr std::uint32_t kSelfTxGuardMs = 50U;

static_assert(kRxResolutionHz == 100'000U);
static_assert(kRxMinimumSignalNs < kRxMaximumSignalNs);
static_assert(kRxResolutionHz % kRmtResolutionHz == 0U);

} // namespace growbox::app::climate_io::rf433
