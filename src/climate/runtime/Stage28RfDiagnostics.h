#pragma once

#include "climate/rf433/Rf433RmtLoopback.h"

#include <cstdint>

namespace growbox::app::climate_io::runtime {

struct Stage28RfDiagnosticsConfig {
  bool enabled{false};
  bool passive_capture{false};
  bool auto_smoke{false};
  int tx_gpio{8};
  int rx_gpio{14};
  rf433::FrameConfig smoke{};
  std::uint32_t passive_timeout_ms{750U};
  std::uint32_t smoke_timeout_ms{1'500U};
  std::uint64_t smoke_after_ms{3'000U};
};

class Stage28RfDiagnostics final {
public:
  explicit Stage28RfDiagnostics(Stage28RfDiagnosticsConfig config) noexcept;

  bool begin() noexcept;
  void tick(std::uint64_t now_ms) noexcept;
  bool manualTransmit(const rf433::FrameConfig& frame, rf433::LoopbackEvidence& evidence) noexcept;
  bool manualReceive(std::uint32_t timeout_ms, rf433::ReceiveEvidence& evidence) noexcept;

  bool ready() const noexcept {
    return ready_;
  }

private:
  void capturePassive() noexcept;
  void runSmoke() noexcept;

  Stage28RfDiagnosticsConfig config_{};
  rf433::Rf433RmtLoopback loopback_;
  bool ready_{false};
  bool smoke_attempted_{false};
  bool capture_ready_logged_{false};
  std::uint32_t capture_id_{0U};
};

} // namespace growbox::app::climate_io::runtime
