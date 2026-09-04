#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

namespace growbox::app::climate_io::rf433 {

inline constexpr std::uint32_t kRmtResolutionHz = 100000U;
inline constexpr std::uint8_t kProtocolCount = 12U;
inline constexpr std::uint8_t kMinBitLength = 1U;
inline constexpr std::uint8_t kMaxBitLength = 32U;
inline constexpr std::uint8_t kMinRepeat = 1U;
inline constexpr std::uint8_t kMaxRepeat = 50U;
inline constexpr std::uint16_t kMinPulseUs = 40U;
inline constexpr std::uint16_t kMaxPulseUs = 2000U;
inline constexpr std::size_t kEncodedFrameSymbolCount = kMaxBitLength + 1U;
inline constexpr std::size_t kRxCaptureSymbolCapacity = 256U;
inline constexpr std::uint64_t kMaxTxAirtimeTicks = 500000ULL;

struct PulsePair {
  std::uint8_t high;
  std::uint8_t low;
};

struct ProtocolSpec {
  std::uint16_t default_pulse_us;
  PulsePair sync;
  PulsePair zero;
  PulsePair one;
  bool inverted;
};

struct FrameKey {
  std::uint32_t code{0U};
  std::uint8_t bit_length{0U};
  std::uint8_t protocol{0U};

  bool operator==(const FrameKey& other) const noexcept {
    return code == other.code && bit_length == other.bit_length && protocol == other.protocol;
  }
};

struct FrameConfig {
  FrameKey key{};
  std::uint8_t repeat{0U};
  std::uint16_t pulse_us{0U}; // 0 selects the protocol default.
};

struct PulseSymbol {
  std::uint16_t duration0_ticks{0U};
  std::uint16_t duration1_ticks{0U};
  bool level0{false};
  bool level1{false};
};

enum class CodecStatus : std::uint8_t {
  Ok = 0,
  InvalidCode,
  InvalidBitLength,
  InvalidProtocol,
  InvalidRepeat,
  InvalidPulseLength,
  DurationOverflow,
  AirtimeExceeded,
};

struct EncodedFrame {
  std::array<PulseSymbol, kEncodedFrameSymbolCount> symbols{};
  std::uint8_t symbol_count{0U};
  std::uint64_t frame_ticks{0U};
  std::uint64_t total_ticks{0U};
};

enum class DecodeStatus : std::uint8_t {
  Decoded = 0,
  NoFrame,
  Ambiguous,
  InvalidCapture,
};

struct DecodeResult {
  DecodeStatus status{DecodeStatus::NoFrame};
  FrameKey frame{};
  FrameKey alternate{};
  std::uint16_t estimated_pulse_us{0U};
  std::uint8_t observed_repeats{0U};
  std::uint8_t candidate_count{0U};
};

struct DecodeWorkspace {
  struct Candidate {
    FrameKey frame{};
    std::uint32_t pulse_ticks_x1000{0U};
    std::uint64_t score{0U};
    std::uint8_t occurrences{0U};
  };
  std::array<Candidate, 128U> candidates{};
  std::size_t candidate_count{0U};
};

const ProtocolSpec* protocolSpec(std::uint8_t protocol) noexcept;
CodecStatus validateFrameConfig(const FrameConfig& config) noexcept;
CodecStatus encodeFrame(const FrameConfig& config, EncodedFrame& output) noexcept;
DecodeResult decodeFrame(const PulseSymbol* symbols, std::size_t symbol_count,
                         DecodeWorkspace& workspace) noexcept;

std::uint32_t microsecondsToTicks(std::uint64_t duration_us) noexcept;
std::uint32_t ticksToMicroseconds(std::uint64_t ticks) noexcept;
std::uint32_t captureDurationMilliseconds(const PulseSymbol* symbols,
                                          std::size_t symbol_count) noexcept;
std::uint32_t captureStartMilliseconds(std::uint32_t finished_at_ms, const PulseSymbol* symbols,
                                       std::size_t symbol_count) noexcept;

} // namespace growbox::app::climate_io::rf433
