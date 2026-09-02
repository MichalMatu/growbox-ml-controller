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
      ESP_LOGE(kTag, "Failed to enable SD power GPIO %d: %s", pins_.power,
               esp_err_to_name(level_error));
      return false;
    }
    vTaskDelay(pdMS_TO_TICKS(10));
    ESP_LOGI(kTag, "SD power enabled on GPIO%d", pins_.power);
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
  if (!spi_initialized_) {
    spi_bus_config_t bus_config{};
    bus_config.mosi_io_num = pins_.mosi;
    bus_config.miso_io_num = pins_.miso;
    bus_config.sclk_io_num = pins_.sclk;
    bus_config.quadwp_io_num = -1;
    bus_config.quadhd_io_num = -1;
    bus_config.max_transfer_sz = 4096;

    const esp_err_t spi_error = spi_bus_initialize(SPI2_HOST, &bus_config, SPI_DMA_CH_AUTO);
    if (spi_error != ESP_OK && spi_error != ESP_ERR_INVALID_STATE) {
      mount_errors_.fetch_add(1U, std::memory_order_relaxed);
      ESP_LOGW(kTag, "SPI bus init failed: %s", esp_err_to_name(spi_error));
      return false;
    }
    spi_initialized_ = true;
  }

  sdmmc_host_t host = SDSPI_HOST_DEFAULT();
  host.slot = SPI2_HOST;
  sdspi_device_config_t slot_config = SDSPI_DEVICE_CONFIG_DEFAULT();
  slot_config.gpio_cs = static_cast<gpio_num_t>(pins_.cs);
  slot_config.host_id = SPI2_HOST;
  esp_vfs_fat_sdmmc_mount_config_t mount_config{};
  mount_config.format_if_mount_failed = false;
  mount_config.max_files = 2;
  mount_config.allocation_unit_size = 16U * 1024U;

  card_ = nullptr;
  const esp_err_t mount_error =
      esp_vfs_fat_sdspi_mount(kMountPoint, &host, &slot_config, &mount_config, &card_);
  if (mount_error != ESP_OK) {
    mount_errors_.fetch_add(1U, std::memory_order_relaxed);
    ESP_LOGW(kTag, "SD mount failed at uptime=%llu: %s",
             static_cast<unsigned long long>(snapshot.uptime_ms), esp_err_to_name(mount_error));
    card_ = nullptr;
    return false;
  }

  if (mkdir(kDataDirectory, 0775) != 0 && errno != EEXIST) {
    write_errors_.fetch_add(1U, std::memory_order_relaxed);
    ESP_LOGW(kTag, "Failed to create %s: errno=%d", kDataDirectory, errno);
    closeMountedStorage();
    return false;
  }

  mounted_.store(true, std::memory_order_relaxed);
  ESP_LOGI(kTag, "SD mounted on SPI2 MOSI=%d MISO=%d CLK=%d CS=%d POWER=%d", pins_.mosi, pins_.miso,
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
      ",\"sd_spi\":{\"host\":2,\"mosi\":%d,\"miso\":%d,\"clk\":%d,\"cs\":%d,\"power\":%d}}\n",
      firmware_sha_, session_id_, snapshot.reset_reason, snapshot.uptime_ms,
      snapshot.rtc_trusted ? "true" : "false", snapshot.unix_time_s, pins_.mosi, pins_.miso,
      pins_.sclk, pins_.cs, pins_.power);
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
}

} // namespace growbox::app::climate_io::storage
