#pragma once

#include "climate/ClimateCompositeInput.h"
#include "climate/native/NativeI2cBus.h"

#include <driver/i2c_master.h>

#include <cstdint>

namespace growbox::app::climate_io::native {

class Ds3231ClockSource final : public ClimateClockSource {
public:
  ~Ds3231ClockSource();

  bool begin(NativeI2cBus& bus) noexcept;
  bool sample(std::uint64_t monotonic_ms, ClimateWallClockSnapshot& output) noexcept override;
  bool setUnixTimeUtc(std::uint64_t unix_time_s) noexcept;

  bool available() const noexcept {
    return available_;
  }
  bool trusted() const noexcept {
    return trusted_;
  }
  std::uint32_t successfulReadCount() const noexcept {
    return successful_read_count_;
  }
  std::uint32_t readErrorCount() const noexcept {
    return read_error_count_;
  }
  std::uint32_t successfulWriteCount() const noexcept {
    return successful_write_count_;
  }
  std::uint32_t writeErrorCount() const noexcept {
    return write_error_count_;
  }
  std::uint32_t untrustedReadCount() const noexcept {
    return untrusted_read_count_;
  }
  std::uint64_t lastSuccessfulReadMs() const noexcept {
    return last_successful_read_ms_;
  }
  std::uint64_t lastTrustedReadMs() const noexcept {
    return last_trusted_read_ms_;
  }
  std::uint64_t lastTrustedUnixTimeS() const noexcept {
    return last_trusted_unix_time_s_;
  }

private:
  i2c_master_dev_handle_t device_ = nullptr;
  bool available_ = false;
  bool trusted_ = false;
  std::uint32_t successful_read_count_ = 0U;
  std::uint32_t read_error_count_ = 0U;
  std::uint32_t successful_write_count_ = 0U;
  std::uint32_t write_error_count_ = 0U;
  std::uint32_t untrusted_read_count_ = 0U;
  std::uint64_t last_successful_read_ms_ = 0U;
  std::uint64_t last_trusted_read_ms_ = 0U;
  std::uint64_t last_trusted_unix_time_s_ = 0U;
};

} // namespace growbox::app::climate_io::native
