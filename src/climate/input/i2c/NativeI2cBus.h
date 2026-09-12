#pragma once

#include <driver/i2c_master.h>
#include <esp_err.h>

#include <cstdint>

namespace growbox::app::climate_io::native {

class NativeI2cBus final {
public:
  NativeI2cBus(int sda_gpio, int scl_gpio) noexcept : sda_gpio_(sda_gpio), scl_gpio_(scl_gpio) {}
  ~NativeI2cBus();

  NativeI2cBus(const NativeI2cBus&) = delete;
  NativeI2cBus& operator=(const NativeI2cBus&) = delete;

  esp_err_t begin() noexcept;
  esp_err_t addDevice(std::uint8_t address, std::uint32_t clock_hz,
                      i2c_master_dev_handle_t& device) noexcept;
  esp_err_t probe(std::uint8_t address, int timeout_ms = 100) noexcept;

  bool ready() const noexcept {
    return bus_ != nullptr;
  }

private:
  int sda_gpio_ = -1;
  int scl_gpio_ = -1;
  i2c_master_bus_handle_t bus_ = nullptr;
};

} // namespace growbox::app::climate_io::native
