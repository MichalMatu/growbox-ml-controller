#include "climate/runtime/diagnostics/RfDiagnostics.h"

#include <esp_log.h>

#include <cstddef>

namespace growbox::app::climate_io::runtime {
namespace {
constexpr char kTag[] = "climate_stage27";
} // namespace

RfDiagnostics::RfDiagnostics(RfDiagnosticsConfig config, rf433::Rf433RmtLoopback& radio) noexcept
    : config_(config), radio_(radio) {}

bool RfDiagnostics::begin(bool radio_ready) noexcept {
  ready_ = config_.enabled && radio_ready;
  return ready_;
}

void RfDiagnostics::tick(std::uint64_t now_ms) noexcept {
  (void)now_ms;
  if (!ready_) {
    return;
  }

  if (config_.passive_capture) {
    capturePassive();
  }
}

bool RfDiagnostics::manualTransmit(const rf433::FrameConfig& frame,
                                   rf433::LoopbackEvidence& evidence) noexcept {
  evidence = {};
  if (!ready_) {
    return false;
  }
  static_cast<void>(radio_.transmitAndReceive(frame, config_.manual_tx_timeout_ms, evidence));
  return evidence.tx_completed;
}

bool RfDiagnostics::manualReceive(std::uint32_t timeout_ms,
                                  rf433::ReceiveEvidence& evidence) noexcept {
  evidence = {};
  return ready_ && timeout_ms > 0U && radio_.receiveOnce(timeout_ms, evidence);
}

void RfDiagnostics::capturePassive() noexcept {
  if (!capture_ready_logged_) {
    capture_ready_logged_ = true;
    ESP_LOGI(kTag,
             "rf433_remote_capture_ready_v=1 rx_gpio=%d passive_rx_only=1 "
             "outputs=fake-locked",
             config_.rx_gpio);
  }

  rf433::ReceiveEvidence capture{};
  if (!radio_.receiveOnce(config_.passive_timeout_ms, capture)) {
    return;
  }

  const std::uint32_t capture_id = ++capture_id_;
  ESP_LOGI(kTag,
           "rf433_remote_capture_v=1 capture_id=%lu rx_start_ms=%lu rx_finish_ms=%lu "
           "symbol_count=%u overflow=%d decode_status=%u decoded_code=%lu "
           "decoded_bits=%u decoded_protocol=%u estimated_pulse_us=%u "
           "observed_repeats=%u candidate_count=%u outputs=fake-locked",
           static_cast<unsigned long>(capture_id),
           static_cast<unsigned long>(capture.rx_started_at_ms),
           static_cast<unsigned long>(capture.rx_finished_at_ms),
           static_cast<unsigned>(capture.symbol_count), capture.overflow,
           static_cast<unsigned>(capture.decoded.status),
           static_cast<unsigned long>(capture.decoded.frame.code), capture.decoded.frame.bit_length,
           capture.decoded.frame.protocol, capture.decoded.estimated_pulse_us,
           capture.decoded.observed_repeats, capture.decoded.candidate_count);

  for (std::size_t i = 0U; i < capture.symbol_count; ++i) {
    const auto& symbol = capture.symbols[i];
    ESP_LOGI(kTag,
             "rf433_remote_symbol_v=1 capture_id=%lu index=%u d0_us=%lu l0=%d "
             "d1_us=%lu l1=%d",
             static_cast<unsigned long>(capture_id), static_cast<unsigned>(i),
             static_cast<unsigned long>(rf433::ticksToMicroseconds(symbol.duration0_ticks)),
             symbol.level0,
             static_cast<unsigned long>(rf433::ticksToMicroseconds(symbol.duration1_ticks)),
             symbol.level1);
  }
}

} // namespace growbox::app::climate_io::runtime
