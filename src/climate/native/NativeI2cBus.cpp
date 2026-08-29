#include "climate/native/NativeI2cBus.h"

#include <driver/gpio.h>

namespace growbox::app::climate_io::native {

NativeI2cBus::~NativeI2cBus() {
  if (bus_ != nullptr) {
    i2c_del_master_bus(bus_);
  }
}

esp_err_t NativeI2cBus::begin() noexcept {
  if (bus_ != nullptr) {
    return ESP_OK;
  }

  i2c_master_bus_config_t config{};
  config.i2c_port = I2C_NUM_0;
  config.sda_io_num = static_cast<gpio_num_t>(sda_gpio_);
  config.scl_io_num = static_cast<gpio_num_t>(scl_gpio_);
  config.clk_source = I2C_CLK_SRC_DEFAULT;
  config.glitch_ignore_cnt = 7U;
  config.flags.enable_internal_pullup = true;
  return i2c_new_master_bus(&config, &bus_);
}

esp_err_t NativeI2cBus::addDevice(std::uint8_t address, std::uint32_t clock_hz,
                                  i2c_master_dev_handle_t& device) noexcept {
  device = nullptr;
  if (bus_ == nullptr) {
    return ESP_ERR_INVALID_STATE;
  }

  i2c_device_config_t config{};
  config.dev_addr_length = I2C_ADDR_BIT_LEN_7;
  config.device_address = address;
  config.scl_speed_hz = clock_hz;
  return i2c_master_bus_add_device(bus_, &config, &device);
}

} // namespace growbox::app::climate_io::native
