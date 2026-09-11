#pragma once

#include <cstdint>

#include "climate/rf433/Rf433ProtocolCodec.h"

namespace growbox::app::climate_io::rf433 {

enum class TemporalRxClassification : std::uint8_t {
  NotDuringTx = 0,
  SelfTx,
  InterferenceDuringTx,
};

struct RxTemporalSample {
  std::uint32_t capture_started_at_ms{0U};
  std::uint32_t capture_finished_at_ms{0U};
  DecodeStatus decode_status{DecodeStatus::InvalidCapture};
  FrameKey frame{};
};

struct TxFingerprint {
  bool valid{false};
  std::uint64_t tx_id{0U};
  FrameKey frame{};
  std::uint32_t started_at_ms{0U};
  std::uint32_t guard_until_ms{0U};
};

inline bool timeInClosedWindow(std::uint32_t value, std::uint32_t start,
                               std::uint32_t finish) noexcept {
  return static_cast<std::int32_t>(value - start) >= 0 &&
         static_cast<std::int32_t>(finish - value) >= 0;
}

inline bool closedTimeWindowsOverlap(std::uint32_t left_start, std::uint32_t left_finish,
                                     std::uint32_t right_start,
                                     std::uint32_t right_finish) noexcept {
  return timeInClosedWindow(left_start, right_start, right_finish) ||
         timeInClosedWindow(left_finish, right_start, right_finish) ||
         timeInClosedWindow(right_start, left_start, left_finish);
}

template <typename FingerprintRange>
TemporalRxClassification classifyTemporalRx(const RxTemporalSample& sample,
                                            const FingerprintRange& fingerprints) noexcept {
  bool overlaps_tx = false;
  for (const auto& fingerprint : fingerprints) {
    if (!fingerprint.valid ||
        !closedTimeWindowsOverlap(sample.capture_started_at_ms, sample.capture_finished_at_ms,
                                  fingerprint.started_at_ms, fingerprint.guard_until_ms)) {
      continue;
    }
    overlaps_tx = true;
    if (sample.decode_status == DecodeStatus::Decoded && sample.frame == fingerprint.frame) {
      return TemporalRxClassification::SelfTx;
    }
  }
  return overlaps_tx ? TemporalRxClassification::InterferenceDuringTx
                     : TemporalRxClassification::NotDuringTx;
}

} // namespace growbox::app::climate_io::rf433
