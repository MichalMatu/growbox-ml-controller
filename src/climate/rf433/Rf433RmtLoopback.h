#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

#include <driver/rmt_rx.h>
#include <driver/rmt_tx.h>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>

#include "climate/rf433/Rf433ProtocolCodec.h"
#include "climate/rf433/Rf433TemporalPolicy.h"

namespace growbox::app::climate_io::rf433 {

struct LoopbackDiagnostics {
  std::uint32_t tx_requests{0U};
  std::uint32_t tx_queue_errors{0U};
  std::uint32_t tx_wait_errors{0U};
  std::uint32_t rx_arm_errors{0U};
  std::uint32_t rx_timeouts{0U};
  std::uint32_t rx_captures{0U};
  std::uint32_t rx_decode_failures{0U};
  std::uint32_t rx_ambiguous{0U};
  std::uint32_t rx_self_tx{0U};
  std::uint32_t rx_interference{0U};
};

struct LoopbackEvidence {
  std::uint64_t tx_id{0U};
  bool tx_queued{false};
  bool tx_started{false};
  bool tx_completed{false};
  std::uint32_t tx_started_at_ms{0U};
  std::uint32_t tx_completed_at_ms{0U};
  bool rx_captured{false};
  std::uint32_t rx_started_at_ms{0U};
  std::uint32_t rx_finished_at_ms{0U};
  DecodeResult decoded{};
  TemporalRxClassification classification{TemporalRxClassification::NotDuringTx};
};

class Rf433RmtLoopback final {
public:
  struct Config {
    int tx_gpio{8};
    int rx_gpio{14};
  };

  explicit Rf433RmtLoopback(Config config) noexcept;
  ~Rf433RmtLoopback();

  Rf433RmtLoopback(const Rf433RmtLoopback&) = delete;
  Rf433RmtLoopback& operator=(const Rf433RmtLoopback&) = delete;

  bool begin() noexcept;
  bool transmitAndReceive(const FrameConfig& frame,
                          std::uint32_t timeout_ms,
                          LoopbackEvidence& evidence) noexcept;

  const LoopbackDiagnostics& diagnostics() const noexcept { return diagnostics_; }

private:
  static bool onRxDone(rmt_channel_handle_t channel,
                       const rmt_rx_done_event_data_t* event,
                       void* user_data) noexcept;

  void close() noexcept;
  static std::uint32_t monotonicMilliseconds() noexcept;

  Config config_{};
  rmt_channel_handle_t tx_channel_{nullptr};
  rmt_channel_handle_t rx_channel_{nullptr};
  rmt_encoder_handle_t copy_encoder_{nullptr};
  SemaphoreHandle_t rx_done_{nullptr};
  bool tx_enabled_{false};
  bool rx_enabled_{false};

  std::array<rmt_symbol_word_t, kEncodedFrameSymbolCount> tx_symbols_{};
  std::array<rmt_symbol_word_t, kRxCaptureSymbolCapacity> rx_symbols_{};
  volatile std::size_t rx_symbol_count_{0U};
  volatile bool rx_overflow_{false};

  std::uint64_t next_tx_id_{1U};
  LoopbackDiagnostics diagnostics_{};
};

}  // namespace growbox::app::climate_io::rf433
