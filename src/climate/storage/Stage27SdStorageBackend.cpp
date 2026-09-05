#include "climate/storage/Stage27SdStorageBackend.h"

#include "climate/storage/Stage27FileDurability.h"

#include "climate/storage/crowpanel/CrowPanelSdPrecondition.h"

#include <driver/gpio.h>
#include <driver/sdspi_host.h>
#include <driver/spi_master.h>
#include <esp_err.h>
#include <esp_log.h>
#include <esp_vfs_fat.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include <cerrno>
#include <cinttypes>
#include <cstring>
#include <sys/stat.h>

namespace growbox::app::climate_io::storage {
namespace {

constexpr char kTag[] = "stage27_sd";
constexpr char kMountPoint[] = "/sdcard";
constexpr char kDataDirectory[] = "/sdcard/GBLOG";
constexpr spi_host_device_t kSpiHost = SPI3_HOST;
constexpr std::uint32_t kPowerOnDelayMs = 100U;

bool writeLineDurably(std::FILE* file, const char* data, std::size_t length,
                      const char* context) noexcept {
  if (file == nullptr || data == nullptr || length == 0U) {
    return false;
  }

  errno = 0;
  const std::size_t written = std::fwrite(data, 1U, length, file);
  if (written != length) {
    const int error_number = errno;
    ESP_LOGW(kTag, "%s fwrite short write expected=%u actual=%u errno=%d ferror=%d", context,
             static_cast<unsigned>(length), static_cast<unsigned>(written), error_number,
             std::ferror(file));
    return false;
  }
  errno = 0;
  if (std::fputc('\n', file) == EOF) {
    ESP_LOGW(kTag, "%s newline write failed errno=%d ferror=%d", context, errno,
             std::ferror(file));
    return false;
  }

  const Stage27FileDurabilityResult durability = stage27FlushSyncAndStat(file);
  if (!durability.ok) {
    ESP_LOGW(kTag, "%s durability failed step=%s errno=%d", context,
             stage27FileDurabilityStepName(durability.failed_step), durability.error_number);
    return false;
  }
  if (durability.size_bytes == 0U) {
    ESP_LOGW(kTag, "%s durability invariant failed: file size is zero after sync", context);
    return false;
  }
  return true;
}

} // namespace

bool Stage27SdStorageBackend::initialize() noexcept {
  if (pins_.power < 0) {
    power_configured_ = true;
    return true;
  }

  const auto power_gpio = static_cast<gpio_num_t>(pins_.power);
  const esp_err_t direction_error = gpio_set_direction(power_gpio, GPIO_MODE_OUTPUT);
  if (direction_error != ESP_OK) {
    ESP_LOGE(kTag, "Failed to configure SD power GPIO %d: %s", pins_.power,
             esp_err_to_name(direction_error));
    return false;
  }
  const esp_err_t level_error = gpio_set_level(power_gpio, 0);
  if (level_error != ESP_OK) {
    ESP_LOGE(kTag, "Failed to initialize SD power GPIO %d low: %s", pins_.power,
             esp_err_to_name(level_error));
    return false;
  }
  power_configured_ = true;
  ESP_LOGI(kTag, "SD power GPIO%d initialized LOW", pins_.power);
  return true;
}

bool Stage27SdStorageBackend::mount() noexcept {
  if (card_ != nullptr) {
    return true;
  }
  if (!power_configured_ && !initialize()) {
    return false;
  }
  if (!enablePower()) {
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

    const esp_err_t spi_error = spi_bus_initialize(kSpiHost, &bus_config, SPI_DMA_CH_AUTO);
    if (spi_error != ESP_OK) {
      ESP_LOGW(kTag, "SPI3 bus init failed: %s", esp_err_to_name(spi_error));
      disablePower();
      return false;
    }
    spi_initialized_ = true;
  }

  if (use_cmd0_precondition_ && !crowpanel::runSdCmd0Precondition(kSpiHost, pins_.cs)) {
    releaseSpiBus();
    disablePower();
    return false;
  }

  sdmmc_host_t host = SDSPI_HOST_DEFAULT();
  host.slot = kSpiHost;
  sdspi_device_config_t slot_config = SDSPI_DEVICE_CONFIG_DEFAULT();
  slot_config.gpio_cs = static_cast<gpio_num_t>(pins_.cs);
  slot_config.host_id = kSpiHost;
  esp_vfs_fat_sdmmc_mount_config_t mount_config{};
  mount_config.format_if_mount_failed = false;
  mount_config.max_files = 2;
  mount_config.allocation_unit_size = 16U * 1024U;

  card_ = nullptr;
  const esp_err_t mount_error =
      esp_vfs_fat_sdspi_mount(kMountPoint, &host, &slot_config, &mount_config, &card_);
  if (mount_error != ESP_OK) {
    ESP_LOGW(kTag, "SD mount failed: %s", esp_err_to_name(mount_error));
    card_ = nullptr;
    releaseSpiBus();
    disablePower();
    return false;
  }

  if (mkdir(kDataDirectory, 0775) != 0 && errno != EEXIST) {
    ESP_LOGW(kTag, "Failed to create %s: errno=%d", kDataDirectory, errno);
    close();
    return false;
  }

  ESP_LOGI(kTag, "SD mounted SPI3 MOSI=%d MISO=%d CLK=%d CS=%d POWER=%d", pins_.mosi, pins_.miso,
           pins_.sclk, pins_.cs, pins_.power);
  return true;
}

bool Stage27SdStorageBackend::beginSession(const char* session_header,
                                           std::uint32_t session_id) noexcept {
  if (card_ == nullptr || session_header == nullptr) {
    return false;
  }
  closeFile();

  std::snprintf(session_path_, sizeof(session_path_), "%s/%08" PRIx32 ".JL", kDataDirectory,
                session_id);
  file_ = std::fopen(session_path_, "a");
  if (file_ == nullptr) {
    ESP_LOGW(kTag, "Failed to open %s: errno=%d", session_path_, errno);
    return false;
  }

  const std::size_t header_length = std::strlen(session_header);
  if (!writeLineDurably(file_, session_header, header_length, "session_header")) {
    closeFile();
    return false;
  }

  ESP_LOGI(kTag, "SD session opened: %s", session_path_);
  return true;
}

bool Stage27SdStorageBackend::appendLine(const char* data, std::size_t length) noexcept {
  if (file_ == nullptr || data == nullptr || length == 0U) {
    return false;
  }
  return writeLineDurably(file_, data, length, "telemetry_record");
}

void Stage27SdStorageBackend::close() noexcept {
  closeFile();
  if (card_ != nullptr) {
    const esp_err_t unmount_error = esp_vfs_fat_sdcard_unmount(kMountPoint, card_);
    if (unmount_error != ESP_OK) {
      ESP_LOGW(kTag, "SD unmount failed: %s", esp_err_to_name(unmount_error));
    }
    card_ = nullptr;
  }
  releaseSpiBus();
  disablePower();
}

bool Stage27SdStorageBackend::enablePower() noexcept {
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

void Stage27SdStorageBackend::disablePower() noexcept {
  if (pins_.power < 0 || !power_configured_) {
    return;
  }
  const esp_err_t error = gpio_set_level(static_cast<gpio_num_t>(pins_.power), 0);
  if (error != ESP_OK) {
    ESP_LOGW(kTag, "Failed to disable SD power GPIO %d: %s", pins_.power, esp_err_to_name(error));
  }
}

void Stage27SdStorageBackend::releaseSpiBus() noexcept {
  if (!spi_initialized_) {
    return;
  }
  const esp_err_t error = spi_bus_free(kSpiHost);
  if (error == ESP_OK) {
    spi_initialized_ = false;
    return;
  }
  ESP_LOGW(kTag, "SPI3 bus release failed: %s", esp_err_to_name(error));
}

void Stage27SdStorageBackend::closeFile() noexcept {
  if (file_ != nullptr) {
    std::fclose(file_);
    file_ = nullptr;
  }
}

} // namespace growbox::app::climate_io::storage
