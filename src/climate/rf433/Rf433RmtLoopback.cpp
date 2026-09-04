#include "climate/rf433/Rf433RmtLoopback.h"

#include <algorithm>
#include <array>

#include <driver/gpio.h>
#include <esp_err.h>
#include <esp_timer.h>
#include <freertos/task.h>

namespace growbox::app::climate_io::rf433 {
namespace {

constexpr std::size_t kRmtMemorySymbols = 64U;
// Stage28C RX hardening: reject sub-10 us chatter. A 20 ms idle threshold is
// hardware-qualified with the known 32-bit protocol-2 ON/OFF pair at repeat=10;
// 300 ms did not terminate capture reliably on this receiver in the same setup.
constexpr std::uint32_t kRxMinimumSignalNs = 10'000U;
constexpr std::uint32_t kRxMaximumSignalNs = 20'000'000U;
constexpr std::uint32_t kRxResolutionHz = kRmtResolutionHz;
constexpr std::uint32_t kRxToCodecTickRatio = kRxResolutionHz / kRmtResolutionHz;
static_assert(kRxResolutionHz % kRmtResolutionHz == 0U);
constexpr std::uint32_t kSelfTxGuardMs = 50U;

}  // namespace

Rf433RmtLoopback::Rf433RmtLoopback(Config config) noexcept : config_(config) {}

Rf433RmtLoopback::~Rf433RmtLoopback() {
  close();
}

std::uint32_t Rf433RmtLoopback::monotonicMilliseconds() noexcept {
  return static_cast<std::uint32_t>(
      static_cast<std::uint64_t>(esp_timer_get_time()) / 1000ULL);
}

bool Rf433RmtLoopback::onRxDone(rmt_channel_handle_t,
                                const rmt_rx_done_event_data_t* event,
                                void* user_data) noexcept {
  auto* self = static_cast<Rf433RmtLoopback*>(user_data);
  if (self == nullptr || event == nullptr || self->rx_done_ == nullptr) {
    return false;
  }

  self->rx_symbol_count_ =
      std::min<std::size_t>(event->num_symbols, self->rx_symbols_.size());
  self->rx_overflow_ = event->num_symbols > self->rx_symbols_.size();

  BaseType_t higher_priority_task_woken = pdFALSE;
  xSemaphoreGiveFromISR(self->rx_done_, &higher_priority_task_woken);
  return higher_priority_task_woken == pdTRUE;
}

bool Rf433RmtLoopback::begin() noexcept {
  close();

  if (!GPIO_IS_VALID_OUTPUT_GPIO(config_.tx_gpio) ||
      !GPIO_IS_VALID_GPIO(config_.rx_gpio) || config_.tx_gpio == config_.rx_gpio) {
    return false;
  }

  rx_done_ = xSemaphoreCreateBinary();
  if (rx_done_ == nullptr) {
    return false;
  }

  rmt_tx_channel_config_t tx_config{};
  tx_config.gpio_num = static_cast<gpio_num_t>(config_.tx_gpio);
  tx_config.clk_src = RMT_CLK_SRC_DEFAULT;
  tx_config.resolution_hz = kRmtResolutionHz;
  tx_config.mem_block_symbols = kRmtMemorySymbols;
  tx_config.trans_queue_depth = 4U;
  if (rmt_new_tx_channel(&tx_config, &tx_channel_) != ESP_OK) {
    close();
    return false;
  }

  rmt_rx_channel_config_t rx_config{};
  rx_config.gpio_num = static_cast<gpio_num_t>(config_.rx_gpio);
  rx_config.clk_src = RMT_CLK_SRC_DEFAULT;
  rx_config.resolution_hz = kRxResolutionHz;
  rx_config.mem_block_symbols = kRmtMemorySymbols;
  if (rmt_new_rx_channel(&rx_config, &rx_channel_) != ESP_OK) {
    close();
    return false;
  }

  rmt_copy_encoder_config_t encoder_config{};
  if (rmt_new_copy_encoder(&encoder_config, &copy_encoder_) != ESP_OK) {
    close();
    return false;
  }

  rmt_rx_event_callbacks_t callbacks{};
  callbacks.on_recv_done = &Rf433RmtLoopback::onRxDone;
  if (rmt_rx_register_event_callbacks(rx_channel_, &callbacks, this) != ESP_OK) {
    close();
    return false;
  }

  if (rmt_enable(rx_channel_) != ESP_OK) {
    close();
    return false;
  }
  rx_enabled_ = true;

  if (rmt_enable(tx_channel_) != ESP_OK) {
    close();
    return false;
  }
  tx_enabled_ = true;
  return true;
}

void Rf433RmtLoopback::close() noexcept {
  if (tx_channel_ != nullptr) {
    if (tx_enabled_) {
      static_cast<void>(rmt_disable(tx_channel_));
    }
    static_cast<void>(rmt_del_channel(tx_channel_));
  }
  if (rx_channel_ != nullptr) {
    if (rx_enabled_) {
      static_cast<void>(rmt_disable(rx_channel_));
    }
    static_cast<void>(rmt_del_channel(rx_channel_));
  }
  if (copy_encoder_ != nullptr) {
    static_cast<void>(rmt_del_encoder(copy_encoder_));
  }
  if (rx_done_ != nullptr) {
    vSemaphoreDelete(rx_done_);
  }

  tx_channel_ = nullptr;
  rx_channel_ = nullptr;
  copy_encoder_ = nullptr;
  rx_done_ = nullptr;
  tx_enabled_ = false;
  rx_enabled_ = false;
  rx_symbol_count_ = 0U;
  rx_overflow_ = false;
}

bool Rf433RmtLoopback::receiveOnce(std::uint32_t timeout_ms,
                                   ReceiveEvidence& evidence) noexcept {
  evidence = {};
  if (!rx_enabled_ || rx_done_ == nullptr || timeout_ms == 0U) {
    return false;
  }

  while (xSemaphoreTake(rx_done_, 0U) == pdTRUE) {
  }
  rx_symbol_count_ = 0U;
  rx_overflow_ = false;

  rmt_receive_config_t receive_config{};
  receive_config.signal_range_min_ns = kRxMinimumSignalNs;
  receive_config.signal_range_max_ns = kRxMaximumSignalNs;
  if (rmt_receive(rx_channel_,
                  rx_symbols_.data(),
                  rx_symbols_.size() * sizeof(rx_symbols_[0]),
                  &receive_config) != ESP_OK) {
    ++diagnostics_.rx_arm_errors;
    return false;
  }

  if (xSemaphoreTake(rx_done_, pdMS_TO_TICKS(timeout_ms)) != pdTRUE) {
    ++diagnostics_.rx_timeouts;
    return false;
  }

  evidence.rx_finished_at_ms = monotonicMilliseconds();
  const std::size_t captured_symbol_count = rx_symbol_count_;
  const std::size_t received =
      std::min<std::size_t>(captured_symbol_count, rx_symbols_.size());
  evidence.symbol_count = received;
  evidence.overflow = rx_overflow_;
  if (received == 0U) {
    ++diagnostics_.rx_decode_failures;
    return false;
  }

  evidence.rx_captured = true;
  ++diagnostics_.rx_captures;
  for (std::size_t i = 0U; i < received; ++i) {
    const rmt_symbol_word_t& input = rx_symbols_[i];
    evidence.symbols[i] = PulseSymbol{
        static_cast<std::uint16_t>(
            (input.duration0 + (kRxToCodecTickRatio / 2U)) / kRxToCodecTickRatio),
        static_cast<std::uint16_t>(
            (input.duration1 + (kRxToCodecTickRatio / 2U)) / kRxToCodecTickRatio),
        input.level0 != 0U,
        input.level1 != 0U,
    };
  }

  evidence.rx_started_at_ms = captureStartMilliseconds(
      evidence.rx_finished_at_ms, evidence.symbols.data(), received);
  if (evidence.overflow) {
    evidence.decoded.status = DecodeStatus::InvalidCapture;
    ++diagnostics_.rx_decode_failures;
    return true;
  }

  DecodeWorkspace workspace{};
  evidence.decoded = decodeFrame(evidence.symbols.data(), received, workspace);
  if (evidence.decoded.status == DecodeStatus::Ambiguous) {
    ++diagnostics_.rx_ambiguous;
  } else if (evidence.decoded.status != DecodeStatus::Decoded) {
    ++diagnostics_.rx_decode_failures;
  }
  return true;
}

bool Rf433RmtLoopback::transmitAndReceive(const FrameConfig& frame,
                                         std::uint32_t timeout_ms,
                                         LoopbackEvidence& evidence) noexcept {
  evidence = {};
  ++diagnostics_.tx_requests;

  if (!tx_enabled_ || !rx_enabled_ || copy_encoder_ == nullptr || rx_done_ == nullptr ||
      timeout_ms == 0U) {
    return false;
  }

  EncodedFrame encoded{};
  if (encodeFrame(frame, encoded) != CodecStatus::Ok || encoded.symbol_count == 0U) {
    return false;
  }

  for (std::size_t i = 0U; i < encoded.symbol_count; ++i) {
    const PulseSymbol& input = encoded.symbols[i];
    rmt_symbol_word_t& output = tx_symbols_[i];
    output.duration0 = input.duration0_ticks;
    output.level0 = input.level0 ? 1U : 0U;
    output.duration1 = input.duration1_ticks;
    output.level1 = input.level1 ? 1U : 0U;
  }

  while (xSemaphoreTake(rx_done_, 0U) == pdTRUE) {
  }
  rx_symbol_count_ = 0U;
  rx_overflow_ = false;

  rmt_receive_config_t receive_config{};
  receive_config.signal_range_min_ns = kRxMinimumSignalNs;
  receive_config.signal_range_max_ns = kRxMaximumSignalNs;
  if (rmt_receive(rx_channel_,
                  rx_symbols_.data(),
                  rx_symbols_.size() * sizeof(rx_symbols_[0]),
                  &receive_config) != ESP_OK) {
    ++diagnostics_.rx_arm_errors;
    return false;
  }

  evidence.tx_id = next_tx_id_++;
  evidence.tx_started_at_ms = monotonicMilliseconds();

  rmt_transmit_config_t transmit_config{};
  for (std::uint8_t repeat = 0U; repeat < frame.repeat; ++repeat) {
    const esp_err_t queued =
        rmt_transmit(tx_channel_,
                     copy_encoder_,
                     tx_symbols_.data(),
                     encoded.symbol_count * sizeof(tx_symbols_[0]),
                     &transmit_config);
    if (queued != ESP_OK) {
      ++diagnostics_.tx_queue_errors;
      return false;
    }
    evidence.tx_queued = true;
    evidence.tx_started = true;
  }

  const esp_err_t tx_wait = rmt_tx_wait_all_done(tx_channel_, timeout_ms);
  evidence.tx_completed_at_ms = monotonicMilliseconds();
  if (tx_wait != ESP_OK) {
    ++diagnostics_.tx_wait_errors;
    return false;
  }
  evidence.tx_completed = true;

  if (xSemaphoreTake(rx_done_, pdMS_TO_TICKS(timeout_ms)) != pdTRUE) {
    ++diagnostics_.rx_timeouts;
    return false;
  }

  evidence.rx_finished_at_ms = monotonicMilliseconds();
  const std::size_t captured_symbol_count = rx_symbol_count_;
  const std::size_t received =
      std::min<std::size_t>(captured_symbol_count, rx_symbols_.size());
  if (received == 0U || rx_overflow_) {
    ++diagnostics_.rx_decode_failures;
    return false;
  }

  evidence.rx_captured = true;
  ++diagnostics_.rx_captures;

  std::array<PulseSymbol, kRxCaptureSymbolCapacity> captured{};
  for (std::size_t i = 0U; i < received; ++i) {
    const rmt_symbol_word_t& input = rx_symbols_[i];
    captured[i] = PulseSymbol{
        static_cast<std::uint16_t>((input.duration0 + (kRxToCodecTickRatio / 2U)) / kRxToCodecTickRatio),
        static_cast<std::uint16_t>((input.duration1 + (kRxToCodecTickRatio / 2U)) / kRxToCodecTickRatio),
        input.level0 != 0U,
        input.level1 != 0U,
    };
  }

  evidence.rx_started_at_ms =
      captureStartMilliseconds(evidence.rx_finished_at_ms, captured.data(), received);

  DecodeWorkspace workspace{};
  evidence.decoded = decodeFrame(captured.data(), received, workspace);
  if (evidence.decoded.status == DecodeStatus::Ambiguous) {
    ++diagnostics_.rx_ambiguous;
  } else if (evidence.decoded.status != DecodeStatus::Decoded) {
    ++diagnostics_.rx_decode_failures;
  }

  const std::array<TxFingerprint, 1U> fingerprints{{
      TxFingerprint{
          true,
          evidence.tx_id,
          frame.key,
          evidence.tx_started_at_ms,
          static_cast<std::uint32_t>(evidence.tx_completed_at_ms + kSelfTxGuardMs),
      },
  }};
  evidence.classification =
      classifyTemporalRx(RxTemporalSample{
                             evidence.rx_started_at_ms,
                             evidence.rx_finished_at_ms,
                             evidence.decoded.status,
                             evidence.decoded.frame,
                         },
                         fingerprints);

  if (evidence.classification == TemporalRxClassification::SelfTx) {
    ++diagnostics_.rx_self_tx;
  } else if (evidence.classification == TemporalRxClassification::InterferenceDuringTx) {
    ++diagnostics_.rx_interference;
  }

  return evidence.tx_queued && evidence.tx_started && evidence.tx_completed &&
         evidence.rx_captured && evidence.decoded.status == DecodeStatus::Decoded &&
         evidence.decoded.frame == frame.key &&
         evidence.classification == TemporalRxClassification::SelfTx;
}

}  // namespace growbox::app::climate_io::rf433
