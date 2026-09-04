#!/usr/bin/env bash
set -euo pipefail

EXPECTED=1e14f50bcb6ee20d48c14c2af2ce1a40808b5aff

test "$(git rev-parse HEAD)" = "$EXPECTED"
git fetch -q origin agent-control mvp/environment-controller
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
test -z "$(git status --porcelain)"

python3 - <<'PY'
from pathlib import Path

# 1) Expose a bounded passive RX evidence object/API without changing TX semantics.
path = Path('src/climate/rf433/Rf433RmtLoopback.h')
text = path.read_text(encoding='utf-8')
needle = '''struct LoopbackEvidence {
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
'''
replacement = needle + '''\nstruct ReceiveEvidence {
  bool rx_captured{false};
  std::uint32_t rx_started_at_ms{0U};
  std::uint32_t rx_finished_at_ms{0U};
  std::size_t symbol_count{0U};
  bool overflow{false};
  DecodeResult decoded{};
  std::array<PulseSymbol, kRxCaptureSymbolCapacity> symbols{};
};
'''
if needle not in text:
    raise SystemExit('Rf433RmtLoopback.h evidence anchor not found')
text = text.replace(needle, replacement, 1)
needle = '''  bool transmitAndReceive(const FrameConfig& frame,
                          std::uint32_t timeout_ms,
                          LoopbackEvidence& evidence) noexcept;
'''
replacement = needle + '''  bool receiveOnce(std::uint32_t timeout_ms, ReceiveEvidence& evidence) noexcept;
'''
if needle not in text:
    raise SystemExit('Rf433RmtLoopback.h public API anchor not found')
path.write_text(text.replace(needle, replacement, 1), encoding='utf-8')

# 2) Implement RX-only capture. No rmt_transmit() is reachable from this method.
path = Path('src/climate/rf433/Rf433RmtLoopback.cpp')
text = path.read_text(encoding='utf-8')
anchor = '''bool Rf433RmtLoopback::transmitAndReceive(const FrameConfig& frame,
                                         std::uint32_t timeout_ms,
                                         LoopbackEvidence& evidence) noexcept {
'''
method = r'''bool Rf433RmtLoopback::receiveOnce(std::uint32_t timeout_ms,
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

'''
if anchor not in text:
    raise SystemExit('Rf433RmtLoopback.cpp transmit anchor not found')
path.write_text(text.replace(anchor, method + anchor, 1), encoding='utf-8')

# 3) Add a diagnostic-only, build-time gated remote capture mode to the real-input runtime.
path = Path('src/climate/ClimateV6RealInputRuntime.cpp')
text = path.read_text(encoding='utf-8')
needle = '''#ifndef GROWBOX_RF433_LOOPBACK_AUTO_SMOKE
#define GROWBOX_RF433_LOOPBACK_AUTO_SMOKE 0
#endif
'''
replacement = needle + '''#ifndef GROWBOX_RF433_REMOTE_CAPTURE_ENABLED
#define GROWBOX_RF433_REMOTE_CAPTURE_ENABLED 0
#endif
'''
if needle not in text:
    raise SystemExit('runtime RF macro anchor not found')
text = text.replace(needle, replacement, 1)
needle = '''  std::uint32_t diagnostic_tick = 0U;
  bool rf_smoke_attempted = false;
  while (true) {
    const std::uint64_t now_ms = monotonicMilliseconds();
    if (rf_loopback_ready && GROWBOX_RF433_LOOPBACK_AUTO_SMOKE != 0 &&
        !rf_smoke_attempted && now_ms >= 3'000U) {
'''
replacement = r'''  std::uint32_t diagnostic_tick = 0U;
  bool rf_smoke_attempted = false;
  bool rf_capture_ready_logged = false;
  std::uint32_t rf_capture_id = 0U;
  while (true) {
    const std::uint64_t now_ms = monotonicMilliseconds();
    if (rf_loopback_ready && GROWBOX_RF433_REMOTE_CAPTURE_ENABLED != 0) {
      if (!rf_capture_ready_logged) {
        rf_capture_ready_logged = true;
        ESP_LOGI(kTag,
                 "rf433_remote_capture_ready_v=1 rx_gpio=%d passive_rx_only=1 "
                 "outputs=fake-locked",
                 GROWBOX_RF433_RX_GPIO);
      }

      rf433::ReceiveEvidence capture{};
      if (rf_loopback.receiveOnce(250U, capture)) {
        const std::uint32_t capture_id = ++rf_capture_id;
        ESP_LOGI(
            kTag,
            "rf433_remote_capture_v=1 capture_id=%lu rx_start_ms=%lu rx_finish_ms=%lu "
            "symbol_count=%u overflow=%d decode_status=%u decoded_code=%lu "
            "decoded_bits=%u decoded_protocol=%u estimated_pulse_us=%u "
            "observed_repeats=%u candidate_count=%u outputs=fake-locked",
            static_cast<unsigned long>(capture_id),
            static_cast<unsigned long>(capture.rx_started_at_ms),
            static_cast<unsigned long>(capture.rx_finished_at_ms),
            static_cast<unsigned>(capture.symbol_count), capture.overflow,
            static_cast<unsigned>(capture.decoded.status),
            static_cast<unsigned long>(capture.decoded.frame.code),
            capture.decoded.frame.bit_length, capture.decoded.frame.protocol,
            capture.decoded.estimated_pulse_us, capture.decoded.observed_repeats,
            capture.decoded.candidate_count);
        for (std::size_t i = 0U; i < capture.symbol_count; ++i) {
          const auto& symbol = capture.symbols[i];
          ESP_LOGI(
              kTag,
              "rf433_remote_symbol_v=1 capture_id=%lu index=%u d0_us=%lu l0=%d "
              "d1_us=%lu l1=%d",
              static_cast<unsigned long>(capture_id), static_cast<unsigned>(i),
              static_cast<unsigned long>(rf433::ticksToMicroseconds(symbol.duration0_ticks)),
              symbol.level0,
              static_cast<unsigned long>(rf433::ticksToMicroseconds(symbol.duration1_ticks)),
              symbol.level1);
        }
      }
    }

    if (rf_loopback_ready && GROWBOX_RF433_LOOPBACK_AUTO_SMOKE != 0 &&
        GROWBOX_RF433_REMOTE_CAPTURE_ENABLED == 0 && !rf_smoke_attempted &&
        now_ms >= 3'000U) {
'''
if needle not in text:
    raise SystemExit('runtime loop anchor not found')
path.write_text(text.replace(needle, replacement, 1), encoding='utf-8')

# 4) Wire the build flag through ESP-IDF CMake.
path = Path('src/CMakeLists.txt')
text = path.read_text(encoding='utf-8')
needle = '''set(GROWBOX_RF433_LOOPBACK_AUTO_SMOKE "0" CACHE STRING "Run one Stage28 RF433 boot loopback smoke")
'''
replacement = needle + '''set(GROWBOX_RF433_REMOTE_CAPTURE_ENABLED "0" CACHE STRING "Enable Stage28C passive remote capture diagnostics")
'''
if needle not in text:
    raise SystemExit('CMake RF option anchor not found')
text = text.replace(needle, replacement, 1)
needle = '''    GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=${GROWBOX_RF433_LOOPBACK_AUTO_SMOKE}
'''
replacement = needle + '''    GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=${GROWBOX_RF433_REMOTE_CAPTURE_ENABLED}
'''
if needle not in text:
    raise SystemExit('CMake RF definition anchor not found')
path.write_text(text.replace(needle, replacement, 1), encoding='utf-8')

# 5) Expose the flag through the established Stage27C/28 hardware build wrapper.
path = Path('scripts/stage27c_crowpanel.sh')
text = path.read_text(encoding='utf-8')
needle = '''RF433_LOOPBACK_AUTO_SMOKE="${GROWBOX_RF433_LOOPBACK_AUTO_SMOKE:-0}"
'''
replacement = needle + '''RF433_REMOTE_CAPTURE_ENABLED="${GROWBOX_RF433_REMOTE_CAPTURE_ENABLED:-0}"
'''
if needle not in text:
    raise SystemExit('build wrapper env anchor not found')
text = text.replace(needle, replacement, 1)
needle = '''  -D "GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=$RF433_LOOPBACK_AUTO_SMOKE"
'''
replacement = needle + '''  -D "GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=$RF433_REMOTE_CAPTURE_ENABLED"
'''
if needle not in text:
    raise SystemExit('build wrapper CMake arg anchor not found')
path.write_text(text.replace(needle, replacement, 1), encoding='utf-8')
PY

git diff --check

cmake -S test/host -B build/host-stage28c-passive-capture
cmake --build build/host-stage28c-passive-capture -j2
ctest --test-dir build/host-stage28c-passive-capture --output-on-failure

export GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED"
export GROWBOX_RF433_LOOPBACK_ENABLED=1
export GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0
export GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=1
export STAGE27C_BUILD_DIR=build/idf-stage28c-passive-capture-v1
scripts/stage27c_crowpanel.sh build

git diff --check
git status --short

git add \
  src/climate/rf433/Rf433RmtLoopback.h \
  src/climate/rf433/Rf433RmtLoopback.cpp \
  src/climate/ClimateV6RealInputRuntime.cpp \
  src/CMakeLists.txt \
  scripts/stage27c_crowpanel.sh

git commit -m 'Add bounded RF433 remote capture mode'
NEW_SHA="$(git rev-parse HEAD)"

git fetch -q origin mvp/environment-controller
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
git push origin HEAD:mvp/environment-controller

printf 'STAGE28C_PASSIVE_CAPTURE_READY commit=%s\n' "$NEW_SHA"
