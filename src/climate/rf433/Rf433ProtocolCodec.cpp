#include "climate/rf433/Rf433ProtocolCodec.h"

#include <algorithm>
#include <array>
#include <limits>

namespace growbox::app::climate_io::rf433 {
namespace {

constexpr std::array<ProtocolSpec, kProtocolCount> kSpecs{{
    {350, {1, 31}, {1, 3}, {3, 1}, false},
    {650, {1, 10}, {1, 2}, {2, 1}, false},
    {100, {30, 71}, {4, 11}, {9, 6}, false},
    {380, {1, 6}, {1, 3}, {3, 1}, false},
    {500, {6, 14}, {1, 2}, {2, 1}, false},
    {450, {23, 1}, {1, 2}, {2, 1}, true},
    {150, {2, 62}, {1, 6}, {6, 1}, false},
    {200, {3, 130}, {7, 16}, {3, 16}, false},
    {200, {130, 7}, {16, 7}, {16, 3}, true},
    {365, {18, 1}, {3, 1}, {1, 3}, true},
    {270, {36, 1}, {1, 2}, {2, 1}, true},
    {320, {36, 1}, {1, 2}, {2, 1}, true},
}};
constexpr std::uint32_t kDurationLimitTicks = 0x7FFFU;
constexpr std::uint32_t kTolerancePercent = 30U;
constexpr std::uint32_t kMinimumToleranceTicks = 2U;

std::uint32_t roundedDivide(std::uint64_t numerator, std::uint32_t denominator) noexcept {
  return denominator == 0U ? 0U
                           : static_cast<std::uint32_t>((numerator + denominator / 2U) /
                                                        denominator);
}

bool codeFits(std::uint32_t code, std::uint8_t bit_length) noexcept {
  if (code == 0U || bit_length < kMinBitLength || bit_length > kMaxBitLength) {
    return false;
  }
  return bit_length == 32U || static_cast<std::uint64_t>(code) < (1ULL << bit_length);
}

std::uint16_t effectivePulseUs(const FrameConfig& config, const ProtocolSpec& spec) noexcept {
  return config.pulse_us == 0U ? spec.default_pulse_us : config.pulse_us;
}

bool appendSymbol(EncodedFrame& output,
                  const ProtocolSpec& spec,
                  PulsePair pair,
                  std::uint16_t pulse_us) noexcept {
  if (output.symbol_count >= output.symbols.size()) {
    return false;
  }
  const std::uint32_t first =
      microsecondsToTicks(static_cast<std::uint64_t>(pulse_us) * pair.high);
  const std::uint32_t second =
      microsecondsToTicks(static_cast<std::uint64_t>(pulse_us) * pair.low);
  if (first == 0U || second == 0U || first > kDurationLimitTicks ||
      second > kDurationLimitTicks) {
    return false;
  }
  auto& symbol = output.symbols[output.symbol_count++];
  symbol.duration0_ticks = static_cast<std::uint16_t>(first);
  symbol.duration1_ticks = static_cast<std::uint16_t>(second);
  symbol.level0 = !spec.inverted;
  symbol.level1 = spec.inverted;
  output.frame_ticks += static_cast<std::uint64_t>(first) + second;
  return true;
}

struct PairMatch {
  bool valid{false};
  std::uint64_t error{0U};
};

PairMatch matchPair(const PulseSymbol& symbol,
                    const ProtocolSpec& spec,
                    PulsePair pair,
                    std::uint32_t pulse_ticks_x1000) noexcept {
  const bool expected_first_level = !spec.inverted;
  if (symbol.level0 != expected_first_level || symbol.level1 == expected_first_level) {
    return {};
  }
  const std::uint32_t expected_first =
      roundedDivide(static_cast<std::uint64_t>(pulse_ticks_x1000) * pair.high, 1000U);
  const std::uint32_t expected_second =
      roundedDivide(static_cast<std::uint64_t>(pulse_ticks_x1000) * pair.low, 1000U);
  if (expected_first == 0U || expected_second == 0U) {
    return {};
  }
  const std::uint32_t first_tolerance =
      std::max(kMinimumToleranceTicks,
               roundedDivide(static_cast<std::uint64_t>(expected_first) *
                                 kTolerancePercent,
                             100U));
  const std::uint32_t second_tolerance =
      std::max(kMinimumToleranceTicks,
               roundedDivide(static_cast<std::uint64_t>(expected_second) *
                                 kTolerancePercent,
                             100U));
  const std::uint32_t first_error =
      symbol.duration0_ticks > expected_first ? symbol.duration0_ticks - expected_first
                                              : expected_first - symbol.duration0_ticks;
  const std::uint32_t second_error =
      symbol.duration1_ticks > expected_second ? symbol.duration1_ticks - expected_second
                                               : expected_second - symbol.duration1_ticks;
  if (first_error > first_tolerance || second_error > second_tolerance) {
    return {};
  }
  return {true, static_cast<std::uint64_t>(first_error) + second_error};
}

bool matchSync(const PulseSymbol& symbol,
               const ProtocolSpec& spec,
               std::uint32_t& pulse_ticks_x1000,
               std::uint64_t& error) noexcept {
  const std::uint32_t multiplier =
      static_cast<std::uint32_t>(spec.sync.high) + spec.sync.low;
  pulse_ticks_x1000 = roundedDivide(
      (static_cast<std::uint64_t>(symbol.duration0_ticks) + symbol.duration1_ticks) *
          1000ULL,
      multiplier);
  const std::uint32_t min_ticks_x1000 = microsecondsToTicks(kMinPulseUs) * 1000U;
  const std::uint32_t max_ticks_x1000 = microsecondsToTicks(kMaxPulseUs) * 1000U;
  if (pulse_ticks_x1000 < min_ticks_x1000 || pulse_ticks_x1000 > max_ticks_x1000) {
    return false;
  }
  const PairMatch match = matchPair(symbol, spec, spec.sync, pulse_ticks_x1000);
  error = match.error;
  return match.valid;
}

bool decodeData(const PulseSymbol* symbols,
                std::size_t start,
                std::uint8_t bit_length,
                const ProtocolSpec& spec,
                std::uint32_t pulse_ticks_x1000,
                std::uint32_t& code,
                std::uint64_t& error) noexcept {
  code = 0U;
  error = 0U;
  for (std::uint8_t bit = 0U; bit < bit_length; ++bit) {
    const PulseSymbol& symbol = symbols[start + bit];
    const PairMatch zero = matchPair(symbol, spec, spec.zero, pulse_ticks_x1000);
    const PairMatch one = matchPair(symbol, spec, spec.one, pulse_ticks_x1000);
    if (!zero.valid && !one.valid) {
      return false;
    }
    if (zero.valid && one.valid && zero.error == one.error) {
      return false;
    }
    const bool value = one.valid && (!zero.valid || one.error < zero.error);
    code = static_cast<std::uint32_t>((code << 1U) | (value ? 1U : 0U));
    error += value ? one.error : zero.error;
  }
  return true;
}

void addCandidate(DecodeWorkspace& workspace,
                  FrameKey frame,
                  std::uint32_t pulse_ticks_x1000,
                  std::uint64_t score) noexcept {
  for (std::size_t i = 0U; i < workspace.candidate_count; ++i) {
    auto& candidate = workspace.candidates[i];
    if (candidate.frame == frame) {
      if (candidate.occurrences < std::numeric_limits<std::uint8_t>::max()) {
        ++candidate.occurrences;
      }
      if (score < candidate.score) {
        candidate.score = score;
        candidate.pulse_ticks_x1000 = pulse_ticks_x1000;
      }
      return;
    }
  }
  if (workspace.candidate_count >= workspace.candidates.size()) {
    return;
  }
  auto& candidate = workspace.candidates[workspace.candidate_count++];
  candidate.frame = frame;
  candidate.pulse_ticks_x1000 = pulse_ticks_x1000;
  candidate.score = score;
  candidate.occurrences = 1U;
}

}  // namespace

const ProtocolSpec* protocolSpec(std::uint8_t protocol) noexcept {
  return protocol >= 1U && protocol <= kProtocolCount ? &kSpecs[protocol - 1U] : nullptr;
}

std::uint32_t microsecondsToTicks(std::uint64_t duration_us) noexcept {
  return static_cast<std::uint32_t>(
      (duration_us * kRmtResolutionHz + 500000ULL) / 1000000ULL);
}

std::uint32_t ticksToMicroseconds(std::uint64_t ticks) noexcept {
  return static_cast<std::uint32_t>(
      (ticks * 1000000ULL + kRmtResolutionHz / 2U) / kRmtResolutionHz);
}

CodecStatus validateFrameConfig(const FrameConfig& config) noexcept {
  const ProtocolSpec* spec = protocolSpec(config.key.protocol);
  if (spec == nullptr) {
    return CodecStatus::InvalidProtocol;
  }
  if (config.key.bit_length < kMinBitLength || config.key.bit_length > kMaxBitLength) {
    return CodecStatus::InvalidBitLength;
  }
  if (!codeFits(config.key.code, config.key.bit_length)) {
    return CodecStatus::InvalidCode;
  }
  if (config.repeat < kMinRepeat || config.repeat > kMaxRepeat) {
    return CodecStatus::InvalidRepeat;
  }
  const std::uint16_t pulse_us = effectivePulseUs(config, *spec);
  if (pulse_us < kMinPulseUs || pulse_us > kMaxPulseUs) {
    return CodecStatus::InvalidPulseLength;
  }

  const auto durationFits = [pulse_us](PulsePair pair) {
    return microsecondsToTicks(static_cast<std::uint64_t>(pulse_us) * pair.high) <=
               kDurationLimitTicks &&
           microsecondsToTicks(static_cast<std::uint64_t>(pulse_us) * pair.low) <=
               kDurationLimitTicks;
  };
  if (!durationFits(spec->sync) || !durationFits(spec->zero) || !durationFits(spec->one)) {
    return CodecStatus::DurationOverflow;
  }
  return CodecStatus::Ok;
}

CodecStatus encodeFrame(const FrameConfig& config, EncodedFrame& output) noexcept {
  output = {};
  const CodecStatus validation = validateFrameConfig(config);
  if (validation != CodecStatus::Ok) {
    return validation;
  }
  const ProtocolSpec& spec = *protocolSpec(config.key.protocol);
  const std::uint16_t pulse_us = effectivePulseUs(config, spec);
  for (std::uint8_t offset = 0U; offset < config.key.bit_length; ++offset) {
    const std::uint8_t shift =
        static_cast<std::uint8_t>(config.key.bit_length - 1U - offset);
    const bool value = ((config.key.code >> shift) & 1U) != 0U;
    if (!appendSymbol(output, spec, value ? spec.one : spec.zero, pulse_us)) {
      output = {};
      return CodecStatus::DurationOverflow;
    }
  }
  if (!appendSymbol(output, spec, spec.sync, pulse_us)) {
    output = {};
    return CodecStatus::DurationOverflow;
  }
  output.total_ticks = output.frame_ticks * config.repeat;
  if (output.total_ticks > kMaxTxAirtimeTicks) {
    output = {};
    return CodecStatus::AirtimeExceeded;
  }
  return CodecStatus::Ok;
}

DecodeResult decodeFrame(const PulseSymbol* symbols,
                         std::size_t symbol_count,
                         DecodeWorkspace& workspace) noexcept {
  workspace = {};
  if (symbols == nullptr || symbol_count == 0U ||
      symbol_count > kRxCaptureSymbolCapacity) {
    return {DecodeStatus::InvalidCapture};
  }

  for (std::uint8_t protocol = 1U; protocol <= kProtocolCount; ++protocol) {
    const ProtocolSpec& spec = *protocolSpec(protocol);
    for (std::size_t sync_index = 0U; sync_index < symbol_count; ++sync_index) {
      std::uint32_t pulse_ticks_x1000 = 0U;
      std::uint64_t sync_error = 0U;
      if (!matchSync(symbols[sync_index], spec, pulse_ticks_x1000, sync_error) ||
          sync_index == 0U) {
        continue;
      }

      const std::size_t max_bits =
          std::min<std::size_t>(kMaxBitLength, sync_index);
      std::uint8_t best_length = 0U;
      std::uint32_t best_code = 0U;
      std::uint64_t best_data_error = 0U;
      for (std::size_t length = 1U; length <= max_bits; ++length) {
        const std::size_t start = sync_index - length;
        std::uint32_t code = 0U;
        std::uint64_t data_error = 0U;
        if (!decodeData(symbols,
                        start,
                        static_cast<std::uint8_t>(length),
                        spec,
                        pulse_ticks_x1000,
                        code,
                        data_error)) {
          continue;
        }
        if (codeFits(code, static_cast<std::uint8_t>(length))) {
          best_length = static_cast<std::uint8_t>(length);
          best_code = code;
          best_data_error = data_error;
        }
      }
      if (best_length == 0U) {
        continue;
      }

      const std::uint32_t pulse_us =
          ticksToMicroseconds((pulse_ticks_x1000 + 500U) / 1000U);
      const std::uint64_t default_error =
          pulse_us > spec.default_pulse_us ? pulse_us - spec.default_pulse_us
                                           : spec.default_pulse_us - pulse_us;
      const std::uint64_t score =
          (best_data_error + sync_error) * 1000ULL + default_error;
      addCandidate(workspace,
                   {best_code, best_length, protocol},
                   pulse_ticks_x1000,
                   score);
    }
  }

  if (workspace.candidate_count == 0U) {
    return {DecodeStatus::NoFrame};
  }

  std::size_t best = 0U;
  for (std::size_t i = 1U; i < workspace.candidate_count; ++i) {
    const auto& left = workspace.candidates[i];
    const auto& right = workspace.candidates[best];
    if (left.occurrences > right.occurrences ||
        (left.occurrences == right.occurrences && left.score < right.score)) {
      best = i;
    }
  }

  const auto& winner = workspace.candidates[best];
  DecodeResult result{};
  result.status = DecodeStatus::Decoded;
  result.frame = winner.frame;
  result.estimated_pulse_us =
      static_cast<std::uint16_t>(
          ticksToMicroseconds((winner.pulse_ticks_x1000 + 500U) / 1000U));
  result.observed_repeats = winner.occurrences;
  result.candidate_count = static_cast<std::uint8_t>(
      std::min<std::size_t>(workspace.candidate_count, 255U));

  for (std::size_t i = 0U; i < workspace.candidate_count; ++i) {
    if (i == best) {
      continue;
    }
    const auto& candidate = workspace.candidates[i];
    if (candidate.occurrences == winner.occurrences &&
        candidate.score == winner.score && !(candidate.frame == winner.frame)) {
      result.status = DecodeStatus::Ambiguous;
      result.alternate = candidate.frame;
      break;
    }
  }
  return result;
}

std::uint32_t captureDurationMilliseconds(const PulseSymbol* symbols,
                                          std::size_t symbol_count) noexcept {
  if (symbols == nullptr) {
    return 0U;
  }
  std::uint64_t ticks = 0U;
  for (std::size_t i = 0U; i < symbol_count; ++i) {
    ticks += symbols[i].duration0_ticks;
    ticks += symbols[i].duration1_ticks;
  }
  return static_cast<std::uint32_t>(
      (ticks * 1000ULL + kRmtResolutionHz - 1ULL) / kRmtResolutionHz);
}

std::uint32_t captureStartMilliseconds(std::uint32_t finished_at_ms,
                                       const PulseSymbol* symbols,
                                       std::size_t symbol_count) noexcept {
  return finished_at_ms - captureDurationMilliseconds(symbols, symbol_count);
}

}  // namespace growbox::app::climate_io::rf433
