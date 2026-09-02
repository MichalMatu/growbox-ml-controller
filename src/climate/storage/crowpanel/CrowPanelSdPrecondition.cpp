#include "climate/storage/crowpanel/CrowPanelSdPrecondition.h"

#include <driver/gpio.h>
#include <esp_err.h>
#include <esp_log.h>

#include <cstdint>
#include <cstring>

namespace growbox::app::climate_io::storage::crowpanel {
namespace {

constexpr char kTag[] = "stage27_sd_compat";
constexpr std::uint32_t kProbeFrequencyHz = 400'000U;

bool transferProbeByte(spi_device_handle_t device, std::uint8_t tx, std::uint8_t& rx) noexcept {
  spi_transaction_t transaction{};
  transaction.length = 8U;
  transaction.tx_buffer = &tx;
  transaction.rx_buffer = &rx;
  return spi_device_polling_transmit(device, &transaction) == ESP_OK;
}

} // namespace

bool runSdCmd0Precondition(spi_host_device_t host, int cs_pin) noexcept {
  spi_device_interface_config_t device_config{};
  device_config.clock_speed_hz = static_cast<int>(kProbeFrequencyHz);
  device_config.mode = 0;
  device_config.spics_io_num = -1;
  device_config.queue_size = 1;

  spi_device_handle_t device = nullptr;
  const esp_err_t add_error = spi_bus_add_device(host, &device_config, &device);
  if (add_error != ESP_OK) {
    ESP_LOGW(kTag, "CMD0 precondition device add failed: %s", esp_err_to_name(add_error));
    return false;
  }

  const auto cs = static_cast<gpio_num_t>(cs_pin);
  auto cleanup = [&]() noexcept {
    static_cast<void>(gpio_set_level(cs, 1));
    const esp_err_t remove_error = spi_bus_remove_device(device);
    if (remove_error != ESP_OK) {
      ESP_LOGW(kTag, "CMD0 precondition device remove failed: %s", esp_err_to_name(remove_error));
    }
  };

  if (gpio_set_direction(cs, GPIO_MODE_OUTPUT) != ESP_OK || gpio_set_level(cs, 1) != ESP_OK) {
    ESP_LOGW(kTag, "CMD0 precondition CS setup failed on GPIO%d", cs_pin);
    cleanup();
    return false;
  }

  std::uint8_t clocks[20]{};
  std::memset(clocks, 0xFF, sizeof(clocks));
  spi_transaction_t clock_transaction{};
  clock_transaction.length = sizeof(clocks) * 8U;
  clock_transaction.tx_buffer = clocks;
  if (spi_device_polling_transmit(device, &clock_transaction) != ESP_OK) {
    ESP_LOGW(kTag, "CMD0 precondition startup clocks failed");
    cleanup();
    return false;
  }

  if (gpio_set_level(cs, 0) != ESP_OK) {
    ESP_LOGW(kTag, "CMD0 precondition CS select failed");
    cleanup();
    return false;
  }

  // The known-working CrowPanel Arduino transport ignores the initial busy
  // probe and sends GO_IDLE_STATE. Keep that hardware compatibility quirk
  // isolated here so it can be removed after a native-IDF A/B hardware gate.
  std::uint8_t ignored = 0xFF;
  if (!transferProbeByte(device, 0xFF, ignored)) {
    ESP_LOGW(kTag, "CMD0 precondition initial probe failed");
    cleanup();
    return false;
  }

  const std::uint8_t cmd0[6] = {0x40, 0x00, 0x00, 0x00, 0x00, 0x95};
  spi_transaction_t command{};
  command.length = sizeof(cmd0) * 8U;
  command.tx_buffer = cmd0;
  if (spi_device_polling_transmit(device, &command) != ESP_OK) {
    ESP_LOGW(kTag, "CMD0 precondition transmit failed");
    cleanup();
    return false;
  }

  std::uint8_t response = 0xFF;
  bool response_seen = false;
  unsigned response_bytes = 0U;
  for (unsigned attempt = 0U; attempt < 16U; ++attempt) {
    if (!transferProbeByte(device, 0xFF, response)) {
      ESP_LOGW(kTag, "CMD0 precondition response read failed");
      cleanup();
      return false;
    }
    if ((response & 0x80U) == 0U) {
      response_seen = true;
      response_bytes = attempt + 1U;
      break;
    }
  }

  cleanup();
  if (!response_seen || response != 0x01U) {
    ESP_LOGW(kTag, "CMD0 precondition response=0x%02x after=%u", response, response_bytes);
    return false;
  }

  ESP_LOGI(kTag, "CMD0 precondition response=0x01 after=%u", response_bytes);
  return true;
}

} // namespace growbox::app::climate_io::storage::crowpanel
