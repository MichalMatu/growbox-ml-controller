#include "climate/runtime/Stage28RfDiagnostics.h"

#include <esp_log.h>

#include <cstddef>

namespace growbox::app::climate_io::runtime {
namespace {
constexpr char kTag[] = "climate_stage27";
} // namespace

Stage28RfDiagnostics::Stage28RfDiagnostics(Stage28RfDiagnosticsConfig config) noexcept
    : config_(config), loopback_(rf433::Rf433RmtLoopback::Config{config.tx_gpio, config.rx_gpio}) {}

bool Stage28RfDiagnostics::begin() noexcept {
  ready_ = config_.enabled && loopback_.begin();
  return ready_;
}

void Stage28RfDiagnostics::tick(std::uint64_t now_ms) noexcept {
  if (!ready_) {
    return;
  }

  if (config_.passive_capture) {
    capturePassive();
    return;
  }

  if (config_.auto_smoke && !smoke_attempted_ && now_ms >= config_.smoke_after_ms) {
    runSmoke();
  }
}

bool Stage28RfDiagnostics::manualTransmit(const rf433::FrameConfig& frame,
                                          rf433::LoopbackEvidence& evidence) noexcept {
  evidence = {};
  if (!ready_) {
    return false;
  }
  static_cast<void>(loopback_.transmitAndReceive(frame, config_.smoke_timeout_ms, evidence));
  return evidence.tx_completed;
}

bool Stage28RfDiagnostics::manualReceive(std::uint32_t timeout_ms,
                                         rf433::ReceiveEvidence& evidence) noexcept {
  evidence = {};
  return ready_ && timeout_ms > 0U && loopback_.receiveOnce(timeout_ms, evidence);
}

void Stage28RfDiagnostics::capturePassive() noexcept {
  if (!capture_ready_logged_) {
    capture_ready_logged_ = true;
    ESP_LOGI(kTag,
             "rf433_remote_capture_ready_v=1 rx_gpio=%d passive_rx_only=1 "
             "outputs=fake-locked",
             config_.rx_gpio);
  }

  rf433::ReceiveEvidence capture{};
  if (!loopback_.receiveOnce(config_.passive_timeout_ms, capture)) {
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

void Stage28RfDiagnostics::runSmoke() noexcept {
  smoke_attempted_ = true;
  rf433::LoopbackEvidence evidence{};
  const bool passed =
      loopback_.transmitAndReceive(config_.smoke, config_.smoke_timeout_ms, evidence);
  const auto& rf_diag = loopback_.diagnostics();
  const auto& smoke = config_.smoke;

  ESP_LOGI(kTag,
           "rf433_loopback_v=1 pass=%d tx_id=%llu requested_code=%lu requested_bits=%u "
           "requested_protocol=%u requested_repeat=%u requested_pulse_us=%u tx_queued=%d "
           "tx_started=%d tx_completed=%d tx_started_ms=%lu tx_completed_ms=%lu "
           "rx_captured=%d rx_start_ms=%lu rx_finish_ms=%lu decode_status=%u "
           "decoded_code=%lu decoded_bits=%u decoded_protocol=%u estimated_pulse_us=%u "
           "observed_repeats=%u classification=%u tx_queue_errors=%lu tx_wait_errors=%lu "
           "rx_arm_errors=%lu rx_timeouts=%lu rx_decode_failures=%lu rx_ambiguous=%lu "
           "rx_self_tx=%lu rx_interference=%lu outputs=fake-locked",
           passed, static_cast<unsigned long long>(evidence.tx_id),
           static_cast<unsigned long>(smoke.key.code), smoke.key.bit_length, smoke.key.protocol,
           smoke.repeat, smoke.pulse_us, evidence.tx_queued, evidence.tx_started,
           evidence.tx_completed, static_cast<unsigned long>(evidence.tx_started_at_ms),
           static_cast<unsigned long>(evidence.tx_completed_at_ms), evidence.rx_captured,
           static_cast<unsigned long>(evidence.rx_started_at_ms),
           static_cast<unsigned long>(evidence.rx_finished_at_ms),
           static_cast<unsigned>(evidence.decoded.status),
           static_cast<unsigned long>(evidence.decoded.frame.code),
           evidence.decoded.frame.bit_length, evidence.decoded.frame.protocol,
           evidence.decoded.estimated_pulse_us, evidence.decoded.observed_repeats,
           static_cast<unsigned>(evidence.classification),
           static_cast<unsigned long>(rf_diag.tx_queue_errors),
           static_cast<unsigned long>(rf_diag.tx_wait_errors),
           static_cast<unsigned long>(rf_diag.rx_arm_errors),
           static_cast<unsigned long>(rf_diag.rx_timeouts),
           static_cast<unsigned long>(rf_diag.rx_decode_failures),
           static_cast<unsigned long>(rf_diag.rx_ambiguous),
           static_cast<unsigned long>(rf_diag.rx_self_tx),
           static_cast<unsigned long>(rf_diag.rx_interference));
}

} // namespace growbox::app::climate_io::runtime
