#pragma once

#include "climate/rf433/Rf433OutputTransport.h"
#include "climate/rf433/Rf433RmtLoopback.h"

#include <cstdint>

namespace growbox::app::climate_io::rf433 {

class Rf433RmtFrameSender final : public Rf433FrameSender {
public:
  explicit Rf433RmtFrameSender(Rf433RmtLoopback& radio,
                               std::uint32_t timeout_ms = 1'500U) noexcept
      : radio_(radio), timeout_ms_(timeout_ms) {}

  bool transmitFrame(const FrameConfig& frame) noexcept override;

private:
  Rf433RmtLoopback& radio_;
  std::uint32_t timeout_ms_{1'500U};
};

} // namespace growbox::app::climate_io::rf433
