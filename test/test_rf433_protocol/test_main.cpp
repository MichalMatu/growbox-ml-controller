#include "climate/rf433/Rf433HardwareConfig.h"
#include "climate/rf433/Rf433ProtocolCodec.h"
#include "climate/rf433/Rf433RmtTuning.h"
#include "climate/rf433/Rf433TemporalPolicy.h"

#include <algorithm>
#include <array>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <string_view>

using namespace growbox::app::climate_io::rf433;

namespace {

void testEncodeDecodeAllProtocols() {
  for (std::uint8_t protocol = 1U; protocol <= kProtocolCount; ++protocol) {
    FrameConfig config{{0xA55AU, 16U, protocol}, 3U, 0U};
    EncodedFrame encoded{};
    assert(encodeFrame(config, encoded) == CodecStatus::Ok);
    assert(encoded.symbol_count == 17U);
    assert(encoded.frame_ticks > 0U);
    assert(encoded.total_ticks == encoded.frame_ticks * 3U);

    DecodeWorkspace workspace{};
    const DecodeResult decoded =
        decodeFrame(encoded.symbols.data(), encoded.symbol_count, workspace);
    assert(decoded.status == DecodeStatus::Decoded);
    assert(decoded.frame == config.key);
    // The Stage28 RF transport uses a fixed 100 kHz RMT clock, so pulse lengths are
    // represented in 10 us ticks. Protocol 10's nominal 365 us therefore round-trips
    // as 370 us; verify the codec's quantized value rather than an unrepresentable ideal.
    const auto nominal_pulse_us =
        static_cast<std::uint32_t>(protocolSpec(protocol)->default_pulse_us);
    const auto expected_quantized_pulse_us =
        static_cast<std::uint16_t>(((nominal_pulse_us + 5U) / 10U) * 10U);
    assert(decoded.estimated_pulse_us == expected_quantized_pulse_us);
  }
}

void testRepeatedCapturePrefersExactFingerprint() {
  FrameConfig config{{0x5A3C1U, 20U, 1U}, 4U, 420U};
  EncodedFrame encoded{};
  assert(encodeFrame(config, encoded) == CodecStatus::Ok);

  std::array<PulseSymbol, 128U> capture{};
  std::size_t count = 0U;
  for (int repeat = 0; repeat < 3; ++repeat) {
    for (std::size_t i = 0U; i < encoded.symbol_count; ++i) {
      capture[count++] = encoded.symbols[i];
    }
  }

  DecodeWorkspace workspace{};
  const DecodeResult decoded = decodeFrame(capture.data(), count, workspace);
  assert(decoded.status == DecodeStatus::Decoded);
  assert(decoded.frame == config.key);
  assert(decoded.observed_repeats >= 3U);
  assert(decoded.estimated_pulse_us == 420U);
}

void testKnownRemoteSocketPairCodec() {
  constexpr std::array<std::uint32_t, 2U> codes{{906118656U, 1040336384U}};
  for (const std::uint32_t code : codes) {
    const FrameConfig config{{code, 32U, 2U}, 10U, 575U};
    EncodedFrame encoded{};
    assert(encodeFrame(config, encoded) == CodecStatus::Ok);
    assert(encoded.symbol_count == 33U);
    assert(encoded.total_ticks == encoded.frame_ticks * 10U);

    DecodeWorkspace workspace{};
    const DecodeResult decoded =
        decodeFrame(encoded.symbols.data(), encoded.symbol_count, workspace);
    assert(decoded.status == DecodeStatus::Decoded);
    assert(decoded.frame == config.key);
    assert(decoded.estimated_pulse_us == 580U);

    std::array<PulseSymbol, kRxCaptureSymbolCapacity> repeated{};
    std::size_t repeated_count = 0U;
    for (std::uint8_t repeat = 0U; repeat < 7U; ++repeat) {
      for (std::size_t i = 0U; i < encoded.symbol_count; ++i) {
        repeated[repeated_count++] = encoded.symbols[i];
      }
    }
    DecodeWorkspace repeated_workspace{};
    const DecodeResult repeated_decoded =
        decodeFrame(repeated.data(), repeated_count, repeated_workspace);
    assert(repeated_decoded.status == DecodeStatus::Decoded);
    assert(repeated_decoded.frame == config.key);
    assert(repeated_decoded.observed_repeats >= 7U);
  }
}


void testFrozenRemoteSocketHardwareConfig() {
  static_assert(kRemoteSocket1On.key.code == 906118656U);
  static_assert(kRemoteSocket1Off.key.code == 1040336384U);
  static_assert(kRemoteSocket1On.key.bit_length == 32U);
  static_assert(kRemoteSocket1Off.key.bit_length == 32U);
  static_assert(kRemoteSocket1On.key.protocol == 2U);
  static_assert(kRemoteSocket1Off.key.protocol == 2U);
  static_assert(kRemoteSocket1On.pulse_us == 575U);
  static_assert(kRemoteSocket1Off.pulse_us == 575U);
  static_assert(kRemoteSocket1On.repeat == 10U);
  static_assert(kRemoteSocket1Off.repeat == 10U);

  assert(std::string_view(kRemoteSocket1.label) == "remote_socket_1");
  assert(validateFrameConfig(kRemoteSocket1.on) == CodecStatus::Ok);
  assert(validateFrameConfig(kRemoteSocket1.off) == CodecStatus::Ok);
}

void testHardwareQualifiedRmtReceiveContract() {
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

void testValidationBounds() {
  EncodedFrame encoded{};
  assert(encodeFrame({{0U, 24U, 1U}, 3U, 350U}, encoded) ==
         CodecStatus::InvalidCode);
  assert(encodeFrame({{1U, 0U, 1U}, 3U, 350U}, encoded) ==
         CodecStatus::InvalidBitLength);
  assert(encodeFrame({{1U, 1U, 13U}, 3U, 350U}, encoded) ==
         CodecStatus::InvalidProtocol);
  assert(encodeFrame({{1U, 1U, 1U}, 0U, 350U}, encoded) ==
         CodecStatus::InvalidRepeat);
  assert(encodeFrame({{1U, 1U, 1U}, 3U, 20U}, encoded) ==
         CodecStatus::InvalidPulseLength);

  DecodeWorkspace workspace{};
  assert(decodeFrame(nullptr, 0U, workspace).status == DecodeStatus::InvalidCapture);
}

void testCaptureTiming() {
  FrameConfig config{{0xAU, 4U, 1U}, 1U, 350U};
  EncodedFrame encoded{};
  assert(encodeFrame(config, encoded) == CodecStatus::Ok);
  const std::uint32_t duration =
      captureDurationMilliseconds(encoded.symbols.data(), encoded.symbol_count);
  assert(duration > 0U);
  assert(captureStartMilliseconds(1000U, encoded.symbols.data(),
                                  encoded.symbol_count) ==
         1000U - duration);
}

void testTemporalClassification() {
  constexpr FrameKey expected{0x12345U, 20U, 1U};
  constexpr FrameKey other{0x12344U, 20U, 1U};
  const std::array<TxFingerprint, 2> fingerprints{{
      {true, 7U, expected, 1000U, 1120U},
      {},
  }};

  assert(classifyTemporalRx(
             {1030U, 1080U, DecodeStatus::Decoded, expected}, fingerprints) ==
         TemporalRxClassification::SelfTx);
  assert(classifyTemporalRx(
             {1030U, 1080U, DecodeStatus::Decoded, other}, fingerprints) ==
         TemporalRxClassification::InterferenceDuringTx);
  assert(classifyTemporalRx(
             {1030U, 1080U, DecodeStatus::NoFrame, {}}, fingerprints) ==
         TemporalRxClassification::InterferenceDuringTx);
  assert(classifyTemporalRx(
             {1200U, 1210U, DecodeStatus::Decoded, expected}, fingerprints) ==
         TemporalRxClassification::NotDuringTx);
}

void testTemporalWrapAround() {
  constexpr FrameKey frame{0x3U, 2U, 1U};
  const std::array<TxFingerprint, 1> fingerprints{{
      {true, 9U, frame, 0xFFFFFFF0U, 0x00000020U},
  }};
  assert(classifyTemporalRx(
             {0x00000005U, 0x00000010U, DecodeStatus::Decoded, frame},
             fingerprints) == TemporalRxClassification::SelfTx);
}

}  // namespace

int main() {
  testEncodeDecodeAllProtocols();
  testRepeatedCapturePrefersExactFingerprint();
  testKnownRemoteSocketPairCodec();
  testFrozenRemoteSocketHardwareConfig();
  testHardwareQualifiedRmtReceiveContract();
  testValidationBounds();
  testCaptureTiming();
  testTemporalClassification();
  testTemporalWrapAround();
  return 0;
}
