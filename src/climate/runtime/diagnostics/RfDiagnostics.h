#pragma once

#include "climate/rf433/Rf433RmtLoopback.h"

#include <cstdint>

namespace growbox::app::climate_io::runtime {

struct RfDiagnosticsConfig {
  bool enabled{false};
  bool passive_capture{false};
  int tx_gpio{8};
  int rx_gpio{14};
  std::uint32_t passive_timeout_ms{750U};
  std::uint32_t manual_tx_timeout_ms{1'500U};
};

class RfDiagnostics final {
public:
  RfDiagnostics(RfDiagnosticsConfig config, rf433::Rf433RmtLoopback& radio) noexcept;

  bool begin(bool radio_ready) noexcept;
  void tick(std::uint64_t now_ms) noexcept;
  bool manualTransmit(const rf433::FrameConfig& frame, rf433::LoopbackEvidence& evidence) noexcept;
  bool manualReceive(std::uint32_t timeout_ms, rf433::ReceiveEvidence& evidence) noexcept;

  bool ready() const noexcept {
    return ready_;
  }

private:
  void capturePassive() noexcept;

  RfDiagnosticsConfig config_{};
  rf433::Rf433RmtLoopback& radio_;
  bool ready_{false};
  bool capture_ready_logged_{false};
  std::uint32_t capture_id_{0U};
};

} // namespace growbox::app::climate_io::runtime
