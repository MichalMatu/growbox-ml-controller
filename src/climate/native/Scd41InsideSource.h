#pragma once

#include "climate/ClimateCompositeInput.h"
#include "climate/native/NativeI2cBus.h"

#include <driver/i2c_master.h>

#include <cstdint>

namespace growbox::app::climate_io::native {

class Scd41InsideSource final : public InsideEnvironmentSource {
public:
  ~Scd41InsideSource();

  bool begin(NativeI2cBus& bus) noexcept;
  bool sample(std::uint64_t monotonic_ms, InsideEnvironmentSnapshot& output) noexcept override;

  bool available() const noexcept {
    return available_;
  }
  bool hasMeasurement() const noexcept {
    return has_measurement_;
  }
  std::uint64_t lastSuccessfulMeasurementMs() const noexcept {
    return last_measurement_ms_;
  }
  std::uint32_t readErrorCount() const noexcept {
    return read_error_count_;
  }
  std::uint32_t invalidMeasurementCount() const noexcept {
    return invalid_measurement_count_;
  }
  std::uint32_t successfulMeasurementCount() const noexcept {
    return successful_measurement_count_;
  }

private:
  bool fillCached(std::uint64_t monotonic_ms, InsideEnvironmentSnapshot& output) const noexcept;

  i2c_master_dev_handle_t device_ = nullptr;
  bool started_ = false;
  bool available_ = false;
  bool has_measurement_ = false;
  std::uint64_t last_measurement_ms_ = 0U;
  float temperature_c_ = 0.0F;
  float relative_humidity_pct_ = 0.0F;
  float co2_ppm_ = 0.0F;
  std::uint32_t read_error_count_ = 0U;
  std::uint32_t invalid_measurement_count_ = 0U;
  std::uint32_t successful_measurement_count_ = 0U;
};

} // namespace growbox::app::climate_io::native
