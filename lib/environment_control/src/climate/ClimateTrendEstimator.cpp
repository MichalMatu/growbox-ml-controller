#include "ClimateTrendEstimator.h"
#include <cmath>
#include <cstddef>
namespace growbox::climate {
void ClimateTrendEstimator::Channel::reset() noexcept {
  size_ = 0U;
}
void ClimateTrendEstimator::Channel::prune(std::uint64_t newest) noexcept {
  std::size_t first = 0U;
  while (first < size_ && newest - samples_[first].timestamp_ms > kWindowMs)
    ++first;
  for (std::size_t i = first; i < size_; ++i)
    samples_[i - first] = samples_[i];
  size_ -= first;
}
void ClimateTrendEstimator::Channel::add(float value, std::uint64_t ts) noexcept {
  if (size_ > 0U && ts < samples_[size_ - 1U].timestamp_ms)
    reset();
  prune(ts);
  if (size_ > 0U) {
    auto& last = samples_[size_ - 1U];
    if (ts == last.timestamp_ms) {
      last.value = value;
      return;
    }
    if (ts - last.timestamp_ms < kMinimumSampleSpacingMs)
      return;
  }
  if (size_ == kMaximumSamples) {
    for (std::size_t i = 1U; i < size_; ++i)
      samples_[i - 1U] = samples_[i];
    --size_;
  }
  samples_[size_++] = {ts, value};
}
TrendValue ClimateTrendEstimator::Channel::estimate() const noexcept {
  if (size_ < 2U)
    return {};
  const auto first = samples_[0].timestamp_ms;
  const auto span = samples_[size_ - 1U].timestamp_ms - first;
  if (span < kMinimumTrendSpanMs)
    return {};
  double sx = 0, sy = 0, sxx = 0, sxy = 0;
  for (std::size_t i = 0U; i < size_; ++i) {
    const double x = static_cast<double>(samples_[i].timestamp_ms - first) / 60000.0,
                 y = samples_[i].value;
    sx += x;
    sy += y;
    sxx += x * x;
    sxy += x * y;
  }
  const double n = static_cast<double>(size_), d = n * sxx - sx * sx;
  if (std::abs(d) < 1e-12)
    return {};
  const double slope = (n * sxy - sx * sy) / d;
  return std::isfinite(slope) ? TrendValue{static_cast<float>(slope), true} : TrendValue{};
}
TrendValue ClimateTrendEstimator::Channel::update(const MeasuredValue& m, std::uint64_t now,
                                                  std::uint64_t timeout) noexcept {
  if (!m.valid || m.age_ms > timeout || !std::isfinite(m.value) || m.age_ms > now)
    return {};
  add(m.value, now - m.age_ms);
  return estimate();
}
ClimateTrends ClimateTrendEstimator::update(const ClimateMeasurements& m, std::uint64_t now,
                                            std::uint64_t timeout) noexcept {
  if (has_monotonic_ && now < last_monotonic_ms_)
    reset();
  last_monotonic_ms_ = now;
  has_monotonic_ = true;
  return {temperature_.update(m.air_temperature_c, now, timeout),
          humidity_.update(m.relative_humidity_pct, now, timeout),
          co2_.update(m.co2_ppm, now, timeout)};
}
void ClimateTrendEstimator::reset() noexcept {
  temperature_.reset();
  humidity_.reset();
  co2_.reset();
  last_monotonic_ms_ = 0U;
  has_monotonic_ = false;
}
} // namespace growbox::climate
