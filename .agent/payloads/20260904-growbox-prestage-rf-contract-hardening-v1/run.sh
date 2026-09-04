#!/usr/bin/env bash
set -euo pipefail

EXPECTED=a215cae35bbdee155a40fce0c7481a87191a3716
BRANCH=mvp/environment-controller

test "$(git rev-parse HEAD)" = "$EXPECTED"
git fetch -q origin "$BRANCH"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
test -z "$(git status --porcelain)"

python3 - <<'PY'
from pathlib import Path

root = Path('.')

# Keep hardware-qualified RMT tuning in a small pure header so host tests can
# lock the Stage28C receive contract without importing ESP-IDF driver headers.
tuning = root / 'src/climate/rf433/Rf433RmtTuning.h'
tuning.write_text(r'''#pragma once

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

}  // namespace growbox::app::climate_io::rf433
''', encoding='utf-8')

header = root / 'src/climate/rf433/Rf433RmtLoopback.h'
h = header.read_text(encoding='utf-8')
needle = '''  void close() noexcept;\n  static std::uint32_t monotonicMilliseconds() noexcept;\n'''
replacement = '''  void close() noexcept;\n  bool armReceive() noexcept;\n  bool collectReceive(std::uint32_t timeout_ms, ReceiveEvidence& evidence) noexcept;\n  static std::uint32_t monotonicMilliseconds() noexcept;\n'''
if needle not in h:
    raise SystemExit('Rf433RmtLoopback.h helper insertion point not found')
header.write_text(h.replace(needle, replacement, 1), encoding='utf-8')

cpp_path = root / 'src/climate/rf433/Rf433RmtLoopback.cpp'
cpp = cpp_path.read_text(encoding='utf-8')
cpp = cpp.replace('#include "climate/rf433/Rf433RmtLoopback.h"\n',
                  '#include "climate/rf433/Rf433RmtLoopback.h"\n#include "climate/rf433/Rf433RmtTuning.h"\n', 1)
old_constants = '''constexpr std::size_t kRmtMemorySymbols = 64U;\n// Stage28C RX hardening: reject sub-10 us chatter. A 20 ms idle threshold is\n// hardware-qualified with the known 32-bit protocol-2 ON/OFF pair at repeat=10;\n// 300 ms did not terminate capture reliably on this receiver in the same setup.\nconstexpr std::uint32_t kRxMinimumSignalNs = 10'000U;\nconstexpr std::uint32_t kRxMaximumSignalNs = 20'000'000U;\nconstexpr std::uint32_t kRxResolutionHz = kRmtResolutionHz;\nconstexpr std::uint32_t kRxToCodecTickRatio = kRxResolutionHz / kRmtResolutionHz;\nstatic_assert(kRxResolutionHz % kRmtResolutionHz == 0U);\nconstexpr std::uint32_t kSelfTxGuardMs = 50U;\n'''
new_constants = '''constexpr std::uint32_t kRxToCodecTickRatio = kRxResolutionHz / kRmtResolutionHz;\n'''
if old_constants not in cpp:
    raise SystemExit('Rf433RmtLoopback.cpp tuning block not found')
cpp = cpp.replace(old_constants, new_constants, 1)

start = cpp.index('bool Rf433RmtLoopback::receiveOnce(')
end = cpp.index('bool Rf433RmtLoopback::transmitAndReceive(', start)
old_receive = cpp[start:end]
new_receive = r'''bool Rf433RmtLoopback::armReceive() noexcept {
  if (!rx_enabled_ || rx_done_ == nullptr) {
    return false;
  }

  while (xSemaphoreTake(rx_done_, 0U) == pdTRUE) {
  }
  rx_symbol_count_ = 0U;
  rx_overflow_ = false;

  rmt_receive_config_t receive_config{};
  receive_config.signal_range_min_ns = kRxMinimumSignalNs;
  receive_config.signal_range_max_ns = kRxMaximumSignalNs;
  if (rmt_receive(rx_channel_, rx_symbols_.data(),
                  rx_symbols_.size() * sizeof(rx_symbols_[0]),
                  &receive_config) != ESP_OK) {
    ++diagnostics_.rx_arm_errors;
    return false;
  }
  return true;
}

bool Rf433RmtLoopback::collectReceive(std::uint32_t timeout_ms,
                                      ReceiveEvidence& evidence) noexcept {
  evidence = {};
  if (timeout_ms == 0U || rx_done_ == nullptr) {
    return false;
  }

  if (xSemaphoreTake(rx_done_, pdMS_TO_TICKS(timeout_ms)) != pdTRUE) {
    ++diagnostics_.rx_timeouts;
    return false;
  }

  evidence.rx_finished_at_ms = monotonicMilliseconds();
  const std::size_t received =
      std::min<std::size_t>(rx_symbol_count_, rx_symbols_.size());
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

bool Rf433RmtLoopback::receiveOnce(std::uint32_t timeout_ms,
                                   ReceiveEvidence& evidence) noexcept {
  evidence = {};
  if (timeout_ms == 0U || !armReceive()) {
    return false;
  }
  return collectReceive(timeout_ms, evidence);
}

'''
cpp = cpp[:start] + new_receive + cpp[end:]

# Replace the duplicated RX arm block in transmitAndReceive with the shared helper.
old_arm = r'''  while (xSemaphoreTake(rx_done_, 0U) == pdTRUE) {
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
'''
if old_arm not in cpp:
    raise SystemExit('transmitAndReceive RX arm block not found')
cpp = cpp.replace(old_arm, '  if (!armReceive()) {\n    return false;\n  }\n', 1)

# Replace duplicated wait/conversion/decode block with collectReceive and copy the
# receive evidence into the loopback evidence before temporal classification.
wait_start = cpp.index('  if (xSemaphoreTake(rx_done_, pdMS_TO_TICKS(timeout_ms)) != pdTRUE) {',
                       cpp.index('bool Rf433RmtLoopback::transmitAndReceive('))
classify_anchor = cpp.index('  const std::array<TxFingerprint, 1U> fingerprints{{', wait_start)
old_wait = cpp[wait_start:classify_anchor]
new_wait = r'''  ReceiveEvidence receive{};
  if (!collectReceive(timeout_ms, receive) || !receive.rx_captured ||
      receive.overflow) {
    return false;
  }

  evidence.rx_captured = receive.rx_captured;
  evidence.rx_started_at_ms = receive.rx_started_at_ms;
  evidence.rx_finished_at_ms = receive.rx_finished_at_ms;
  evidence.decoded = receive.decoded;

'''
cpp = cpp[:wait_start] + new_wait + cpp[classify_anchor:]
cpp_path.write_text(cpp, encoding='utf-8')

# Lock both the frozen socket identity and the hardware-qualified RMT receive
# envelope in host tests. Also document that repeat=10 can exceed a single raw
# capture buffer; decode correctness relies on complete repeated frames, not on
# claiming the entire RF burst fits in one capture.
test_path = root / 'test/test_rf433_protocol/test_main.cpp'
t = test_path.read_text(encoding='utf-8')
t = t.replace('#include "climate/rf433/Rf433ProtocolCodec.h"\n',
              '#include "climate/rf433/Rf433ProtocolCodec.h"\n#include "climate/rf433/Rf433RmtTuning.h"\n', 1)
insert_before = 'void testValidationBounds() {'
if insert_before not in t:
    raise SystemExit('RF test insertion point not found')
new_test = r'''void testHardwareQualifiedRmtReceiveContract() {
  static_assert(kRmtResolutionHz == 100'000U);
  static_assert(kRxResolutionHz == 100'000U);
  static_assert(kRxMinimumSignalNs == 10'000U);
  static_assert(kRxMaximumSignalNs == 20'000'000U);
  static_assert(kSelfTxGuardMs == 50U);

  const ProtocolSpec* protocol = protocolSpec(kRemoteSocket1On.key.protocol);
  assert(protocol != nullptr);
  const std::uint8_t longest_multiplier = std::max(
      {protocol->sync.high, protocol->sync.low, protocol->zero.high,
       protocol->zero.low, protocol->one.high, protocol->one.low});
  const std::uint64_t longest_symbol_ns =
      static_cast<std::uint64_t>(longest_multiplier) *
      kRemoteSocket1On.pulse_us * 1'000ULL;
  assert(longest_symbol_ns < kRxMaximumSignalNs);
  assert(kRxMinimumSignalNs <
         static_cast<std::uint64_t>(kRemoteSocket1On.pulse_us) * 1'000ULL);

  constexpr std::size_t symbols_per_frame = 33U;
  static_assert(symbols_per_frame * 7U <= kRxCaptureSymbolCapacity);
  static_assert(symbols_per_frame * 10U > kRxCaptureSymbolCapacity);
}

'''
t = t.replace(insert_before, new_test + insert_before, 1)
t = t.replace('  testFrozenRemoteSocketHardwareConfig();\n  testValidationBounds();',
              '  testFrozenRemoteSocketHardwareConfig();\n  testHardwareQualifiedRmtReceiveContract();\n  testValidationBounds();', 1)
# std::max initializer-list overload is declared in <algorithm>.
t = t.replace('#include <array>\n', '#include <algorithm>\n#include <array>\n', 1)
test_path.write_text(t, encoding='utf-8')
PY

if command -v clang-format >/dev/null 2>&1; then
  clang-format -i \
    src/climate/rf433/Rf433RmtTuning.h \
    src/climate/rf433/Rf433RmtLoopback.h \
    src/climate/rf433/Rf433RmtLoopback.cpp \
    test/test_rf433_protocol/test_main.cpp
fi

git diff --check

cmake -S test/host -B build/host-prestage-rf-contract-hardening-v1
cmake --build build/host-prestage-rf-contract-hardening-v1 -j2
ctest --test-dir build/host-prestage-rf-contract-hardening-v1 --output-on-failure

export GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED"
export GROWBOX_RF433_LOOPBACK_ENABLED=1
export GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0
export GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0
export STAGE27C_BUILD_DIR=build/idf-prestage-rf-contract-hardening-v1
scripts/stage27c_crowpanel.sh build

git diff --check

git add \
  src/climate/rf433/Rf433RmtTuning.h \
  src/climate/rf433/Rf433RmtLoopback.h \
  src/climate/rf433/Rf433RmtLoopback.cpp \
  test/test_rf433_protocol/test_main.cpp

git commit -m "Harden RF433 receive contract and reuse capture path"
git push origin HEAD:"$BRANCH"
NEW=$(git rev-parse HEAD)
test "$(git rev-parse origin/$BRANCH)" = "$NEW"
test -z "$(git status --porcelain)"
printf 'PRESTAGE_RF_CONTRACT_HARDENING_READY commit=%s rx_hz=100000 min_ns=10000 max_ns=20000000\n' "$NEW"
