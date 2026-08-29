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

  bool available() const noexcept {
    return available_;
  }
  bool trusted() const noexcept {
    return trusted_;
  }

private:
  i2c_master_dev_handle_t device_ = nullptr;
  bool available_ = false;
  bool trusted_ = false;
};

} // namespace growbox::app::climate_io::native
