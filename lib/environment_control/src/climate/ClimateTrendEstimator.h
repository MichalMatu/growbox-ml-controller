#pragma once
#include "ClimateTypes.h"
#include <array>
#include <cstddef>
#include <cstdint>
namespace growbox::climate {
class ClimateTrendEstimator {
public:
  static constexpr std::uint64_t kWindowMs = contract::kTrendWindowMs,
                                 kMinimumSampleSpacingMs = 5'000ULL,
                                 kMinimumTrendSpanMs = 10'000ULL;
  static constexpr std::size_t kMaximumSamples = 16U;
  ClimateTrends update(const ClimateMeasurements& measurements, std::uint64_t monotonic_ms,
                       std::uint64_t sensor_timeout_ms = kDefaultSensorTimeoutMs) noexcept;
  void reset() noexcept;

private:
  struct Sample {
    std::uint64_t timestamp_ms = 0U;
    float value = 0.0F;
  };
  class Channel {
  public:
    TrendValue update(const MeasuredValue&, std::uint64_t, std::uint64_t) noexcept;
    void reset() noexcept;

  private:
    void add(float, std::uint64_t) noexcept;
    void prune(std::uint64_t) noexcept;
    TrendValue estimate() const noexcept;
    std::array<Sample, kMaximumSamples> samples_{};
    std::size_t size_ = 0U;
  };
  Channel temperature_{}, humidity_{}, co2_{};
  std::uint64_t last_monotonic_ms_ = 0U;
  bool has_monotonic_ = false;
};
} // namespace growbox::climate
