#include "climate/storage/Stage27SdDataLogger.h"

#include <driver/gpio.h>
#include <driver/sdspi_host.h>
#include <driver/spi_master.h>
#include <esp_err.h>
#include <esp_log.h>
#include <esp_random.h>
#include <esp_vfs_fat.h>

#include <cerrno>
#include <cinttypes>
#include <cstdio>
#include <cstring>
#include <sys/stat.h>

namespace growbox::app::climate_io::storage {
namespace {

constexpr char kTag[] = "stage27_sd";
constexpr char kMountPoint[] = "/sdcard";
constexpr char kDataDirectory[] = "/sdcard/growbox";
constexpr std::size_t kRecordBufferBytes = 2048U;
constexpr std::uint32_t kTaskStackBytes = 6144U;
constexpr spi_host_device_t kSdSpiHost = SPI3_HOST;
constexpr std::uint32_t kPowerOnDelayMs = 100U;
constexpr std::uint32_t kSdProbeFrequencyHz = 400'000U;

bool transferProbeByte(spi_device_handle_t device, std::uint8_t tx, std::uint8_t& rx) noexcept {
  spi_transaction_t transaction{};
  transaction.length = 8U;
  transaction.tx_buffer = &tx;
  transaction.rx_buffer = &rx;
  return spi_device_polling_transmit(device, &transaction) == ESP_OK;
}

bool preconditionCardForIdfMount(int cs_pin) noexcept {
  spi_device_interface_config_t device_config{};
  device_config.clock_speed_hz = static_cast<int>(kSdProbeFrequencyHz);
  device_config.mode = 0;
  device_config.spics_io_num = -1;
  device_config.queue_size = 1;

  spi_device_handle_t device = nullptr;
  const esp_err_t add_error = spi_bus_add_device(kSdSpiHost, &device_config, &device);
  if (add_error != ESP_OK) {
    ESP_LOGW(kTag, "SD precondition device add failed: %s", esp_err_to_name(add_error));
    return false;
  }

  const auto cs = static_cast<gpio_num_t>(cs_pin);
  auto cleanup = [&]() noexcept {
    gpio_set_level(cs, 1);
    const esp_err_t remove_error = spi_bus_remove_device(device);
    if (remove_error != ESP_OK) {
      ESP_LOGW(kTag, "SD precondition device remove failed: %s", esp_err_to_name(remove_error));
    }
  };

  if (gpio_set_direction(cs, GPIO_MODE_OUTPUT) != ESP_OK || gpio_set_level(cs, 1) != ESP_OK) {
    ESP_LOGW(kTag, "SD precondition CS setup failed on GPIO%d", cs_pin);
    cleanup();
    return false;
  }

  std::uint8_t clocks[20];
  std::memset(clocks, 0xFF, sizeof(clocks));
  spi_transaction_t clock_transaction{};
  clock_transaction.length = sizeof(clocks) * 8U;
  clock_transaction.tx_buffer = clocks;
  if (spi_device_polling_transmit(device, &clock_transaction) != ESP_OK) {
    ESP_LOGW(kTag, "SD precondition startup clocks failed");
    cleanup();
    return false;
  }

  if (gpio_set_level(cs, 0) != ESP_OK) {
    ESP_LOGW(kTag, "SD precondition CS select failed");
    cleanup();
    return false;
  }

  // The proven Arduino transport on this CrowPanel intentionally ignores the
  // initial busy/wait result and sends CMD0 anyway. Reproduce only that narrow
  // compatibility preamble before handing the card back to ESP-IDF SDSPI.
  std::uint8_t ignored = 0xFF;
  if (!transferProbeByte(device, 0xFF, ignored)) {
    ESP_LOGW(kTag, "SD precondition initial probe failed");
    cleanup();
    return false;
  }

  const std::uint8_t cmd0[6] = {0x40, 0x00, 0x00, 0x00, 0x00, 0x95};
  spi_transaction_t cmd_transaction{};
  cmd_transaction.length = sizeof(cmd0) * 8U;
  cmd_transaction.tx_buffer = cmd0;
  if (spi_device_polling_transmit(device, &cmd_transaction) != ESP_OK) {
    ESP_LOGW(kTag, "SD precondition CMD0 transmit failed");
    cleanup();
    return false;
  }

  std::uint8_t response = 0xFF;
  bool response_seen = false;
  unsigned response_bytes = 0U;
  for (unsigned attempt = 0; attempt < 16U; ++attempt) {
    if (!transferProbeByte(device, 0xFF, response)) {
      ESP_LOGW(kTag, "SD precondition response read failed");
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
    ESP_LOGW(kTag, "SD precondition CMD0 response=0x%02x after=%u", response, response_bytes);
    return false;
  }

  ESP_LOGI(kTag, "SD precondition CMD0 response=0x01 after=%u", response_bytes);
  return true;
}

} // namespace

bool Stage27SdDataLogger::begin(const char* firmware_sha) noexcept {
  if (queue_ != nullptr || task_ != nullptr) {
    return true;
  }

  if (pins_.power >= 0) {
    const auto power_gpio = static_cast<gpio_num_t>(pins_.power);
    const esp_err_t direction_error = gpio_set_direction(power_gpio, GPIO_MODE_OUTPUT);
    if (direction_error != ESP_OK) {
      ESP_LOGE(kTag, "Failed to configure SD power GPIO %d: %s", pins_.power,
               esp_err_to_name(direction_error));
      return false;
    }
    const esp_err_t level_error = gpio_set_level(power_gpio, 1);
    if (level_error != ESP_OK) {
      ESP_LOGE(kTag, "Failed to initialize SD power GPIO %d high: %s", pins_.power,
               esp_err_to_name(level_error));
      return false;
    }
    ESP_LOGI(kTag, "SD power diagnostic: GPIO%d held HIGH continuously", pins_.power);
  }

  std::snprintf(firmware_sha_, sizeof(firmware_sha_), "%s",
                firmware_sha != nullptr ? firmware_sha : "unknown");
  queue_ = xQueueCreate(kQueueDepth, sizeof(telemetry::Stage27TelemetrySnapshot));
  if (queue_ == nullptr) {
    ESP_LOGE(kTag, "Failed to allocate telemetry queue");
    return false;
  }

  if (xTaskCreate(&Stage27SdDataLogger::taskEntry, "stage27_sd", kTaskStackBytes, this,
                  tskIDLE_PRIORITY + 1U, &task_) != pdPASS) {
    vQueueDelete(queue_);
    queue_ = nullptr;
    ESP_LOGE(kTag, "Failed to create SD logger task");
    return false;
  }

  return true;
}

bool Stage27SdDataLogger::enqueue(const telemetry::Stage27TelemetrySnapshot& snapshot) noexcept {
  if (queue_ == nullptr) {
    return false;
  }
  if (xQueueSend(queue_, &snapshot, 0U) != pdTRUE) {
    queue_drops_.fetch_add(1U, std::memory_order_relaxed);
    return false;
  }
  return true;
}

void Stage27SdDataLogger::taskEntry(void* context) noexcept {
  static_cast<Stage27SdDataLogger*>(context)->taskLoop();
}

void Stage27SdDataLogger::taskLoop() noexcept {
  telemetry::Stage27TelemetrySnapshot snapshot{};
  while (true) {
    if (xQueueReceive(queue_, &snapshot, portMAX_DELAY) != pdTRUE) {
      continue;
    }
    if (!ensureStorage(snapshot) || !writeRecord(snapshot)) {
      records_skipped_.fetch_add(1U, std::memory_order_relaxed);
    }
  }
}

bool Stage27SdDataLogger::ensureStorage(
    const telemetry::Stage27TelemetrySnapshot& snapshot) noexcept {
  if (!mounted_.load(std::memory_order_relaxed)) {
    if (snapshot.uptime_ms < next_mount_attempt_ms_) {
      return false;
    }
    next_mount_attempt_ms_ = snapshot.uptime_ms + kMountRetryMs;
    if (!mountStorage(snapshot)) {
      return false;
    }
  }
  return file_ != nullptr || openSession(snapshot);
}

bool Stage27SdDataLogger::mountStorage(
    const telemetry::Stage27TelemetrySnapshot& snapshot) noexcept {
  if (!enableStoragePower()) {
    mount_errors_.fetch_add(1U, std::memory_order_relaxed);
    return false;
  }

  if (!spi_initialized_) {
    spi_bus_config_t bus_config{};
    bus_config.mosi_io_num = pins_.mosi;
    bus_config.miso_io_num = pins_.miso;
    bus_config.sclk_io_num = pins_.sclk;
    bus_config.quadwp_io_num = -1;
    bus_config.quadhd_io_num = -1;
    bus_config.max_transfer_sz = 4096;

    const esp_err_t spi_error = spi_bus_initialize(kSdSpiHost, &bus_config, SPI_DMA_CH_AUTO);
    if (spi_error != ESP_OK) {
      mount_errors_.fetch_add(1U, std::memory_order_relaxed);
      ESP_LOGW(kTag, "SPI3 bus init failed: %s", esp_err_to_name(spi_error));
      disableStoragePower();
      return false;
    }
    spi_initialized_ = true;
  }

  if (!preconditionCardForIdfMount(pins_.cs)) {
    mount_errors_.fetch_add(1U, std::memory_order_relaxed);
    releaseSpiBus();
    disableStoragePower();
    return false;
  }

  sdmmc_host_t host = SDSPI_HOST_DEFAULT();
  host.slot = kSdSpiHost;
  sdspi_device_config_t slot_config = SDSPI_DEVICE_CONFIG_DEFAULT();
  slot_config.gpio_cs = static_cast<gpio_num_t>(pins_.cs);
  slot_config.host_id = kSdSpiHost;
  esp_vfs_fat_sdmmc_mount_config_t mount_config{};
  mount_config.format_if_mount_failed = false;
  mount_config.max_files = 2;
  mount_config.allocation_unit_size = 16U * 1024U;

  card_ = nullptr;
  if (pins_.power >= 0) {
    ESP_LOGI(kTag, "SD power diagnostic: level before mount=%d",
             gpio_get_level(static_cast<gpio_num_t>(pins_.power)));
  }
  const esp_err_t mount_error =
      esp_vfs_fat_sdspi_mount(kMountPoint, &host, &slot_config, &mount_config, &card_);
  if (mount_error != ESP_OK) {
    mount_errors_.fetch_add(1U, std::memory_order_relaxed);
    if (pins_.power >= 0) {
      ESP_LOGI(kTag, "SD power diagnostic: level after mount failure=%d",
               gpio_get_level(static_cast<gpio_num_t>(pins_.power)));
    }
    ESP_LOGW(kTag, "SD mount failed at uptime=%llu: %s",
             static_cast<unsigned long long>(snapshot.uptime_ms), esp_err_to_name(mount_error));
    card_ = nullptr;
    releaseSpiBus();
    disableStoragePower();
    return false;
  }

  if (mkdir(kDataDirectory, 0775) != 0 && errno != EEXIST) {
    write_errors_.fetch_add(1U, std::memory_order_relaxed);
    ESP_LOGW(kTag, "Failed to create %s: errno=%d", kDataDirectory, errno);
    closeMountedStorage();
    return false;
  }

  mounted_.store(true, std::memory_order_relaxed);
  ESP_LOGI(kTag, "SD mounted on SPI3 MOSI=%d MISO=%d CLK=%d CS=%d POWER=%d", pins_.mosi, pins_.miso,
           pins_.sclk, pins_.cs, pins_.power);
  return openSession(snapshot);
}

bool Stage27SdDataLogger::openSession(
    const telemetry::Stage27TelemetrySnapshot& snapshot) noexcept {
  if (file_ != nullptr) {
    return true;
  }

  session_id_ = esp_random();
  if (snapshot.rtc_trusted && snapshot.unix_time_s != 0U) {
    std::snprintf(session_path_, sizeof(session_path_),
                  "%s/session-%" PRIu64 "-%08" PRIx32 ".ndjson", kDataDirectory,
                  snapshot.unix_time_s, session_id_);
  } else {
    std::snprintf(session_path_, sizeof(session_path_),
                  "%s/session-u%" PRIu64 "-%08" PRIx32 ".ndjson", kDataDirectory,
                  snapshot.uptime_ms, session_id_);
  }

  file_ = std::fopen(session_path_, "a");
  if (file_ == nullptr) {
    write_errors_.fetch_add(1U, std::memory_order_relaxed);
    ESP_LOGW(kTag, "Failed to open %s: errno=%d", session_path_, errno);
    closeMountedStorage();
    return false;
  }

  const int header_written = std::fprintf(
      file_,
      "{\"type\":\"session\",\"schema\":\"growbox-log-v1\",\"firmware_sha\":\"%s\","
      "\"session_id\":\"%08" PRIx32 "\",\"reset_reason\":%" PRId32 ",\"start_uptime_ms\":%" PRIu64
      ",\"rtc_trusted\":%s,\"start_unix_time_s\":%" PRIu64
      ",\"sd_spi\":{\"host\":%d,\"mosi\":%d,\"miso\":%d,\"clk\":%d,\"cs\":%d,\"power\":%d}}\n",
      firmware_sha_, session_id_, snapshot.reset_reason, snapshot.uptime_ms,
      snapshot.rtc_trusted ? "true" : "false", snapshot.unix_time_s, static_cast<int>(kSdSpiHost),
      pins_.mosi, pins_.miso, pins_.sclk, pins_.cs, pins_.power);
  if (header_written < 0 || std::fflush(file_) != 0) {
    write_errors_.fetch_add(1U, std::memory_order_relaxed);
    ESP_LOGW(kTag, "Failed to write session header: errno=%d", errno);
    closeMountedStorage();
    return false;
  }

  ESP_LOGI(kTag, "SD session opened: %s", session_path_);
  return true;
}

bool Stage27SdDataLogger::writeRecord(
    const telemetry::Stage27TelemetrySnapshot& snapshot) noexcept {
  if (file_ == nullptr) {
    return false;
  }

  char buffer[kRecordBufferBytes]{};
  const std::size_t length =
      telemetry::formatStage27TelemetryNdjson(buffer, sizeof(buffer), snapshot);
  if (length == 0U) {
    write_errors_.fetch_add(1U, std::memory_order_relaxed);
    ESP_LOGW(kTag, "Telemetry serialization overflow");
    return false;
  }

  const bool write_ok = std::fwrite(buffer, 1U, length, file_) == length &&
                        std::fputc('\n', file_) != EOF && std::fflush(file_) == 0;
  if (!write_ok) {
    write_errors_.fetch_add(1U, std::memory_order_relaxed);
    ESP_LOGW(kTag, "SD telemetry write failed: errno=%d", errno);
    closeMountedStorage();
    next_mount_attempt_ms_ = snapshot.uptime_ms + kMountRetryMs;
    return false;
  }

  records_written_.fetch_add(1U, std::memory_order_relaxed);
  last_write_ms_.store(snapshot.uptime_ms, std::memory_order_relaxed);
  return true;
}

void Stage27SdDataLogger::closeMountedStorage() noexcept {
  if (file_ != nullptr) {
    std::fclose(file_);
    file_ = nullptr;
  }
  if (card_ != nullptr) {
    esp_vfs_fat_sdcard_unmount(kMountPoint, card_);
    card_ = nullptr;
  }
  mounted_.store(false, std::memory_order_relaxed);
  releaseSpiBus();
  disableStoragePower();
}

bool Stage27SdDataLogger::enableStoragePower() noexcept {
  if (pins_.power < 0) {
    return true;
  }
  const esp_err_t error = gpio_set_level(static_cast<gpio_num_t>(pins_.power), 1);
  if (error != ESP_OK) {
    ESP_LOGW(kTag, "Failed to enable SD power GPIO %d: %s", pins_.power, esp_err_to_name(error));
    return false;
  }
  vTaskDelay(pdMS_TO_TICKS(kPowerOnDelayMs));
  return true;
}

void Stage27SdDataLogger::disableStoragePower() noexcept {
  if (pins_.power < 0) {
    return;
  }
  // Diagnostic only: keep the CrowPanel TF power/ground gate asserted continuously.
  const esp_err_t error = gpio_set_level(static_cast<gpio_num_t>(pins_.power), 1);
  if (error != ESP_OK) {
    ESP_LOGW(kTag, "Failed to keep SD power GPIO %d high: %s", pins_.power, esp_err_to_name(error));
  }
}

void Stage27SdDataLogger::releaseSpiBus() noexcept {
  if (!spi_initialized_) {
    return;
  }
  const esp_err_t error = spi_bus_free(kSdSpiHost);
  if (error == ESP_OK) {
    spi_initialized_ = false;
    return;
  }
  ESP_LOGW(kTag, "SPI3 bus release failed: %s", esp_err_to_name(error));
}

} // namespace growbox::app::climate_io::storage
