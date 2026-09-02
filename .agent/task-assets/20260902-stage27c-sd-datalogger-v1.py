from pathlib import Path


def write(path: str, content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"expected exactly one match in {path}: {old[:80]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


write(
    "src/climate/telemetry/Stage27Telemetry.h",
    r'''#pragma once

#include <cstddef>
#include <cstdint>

namespace growbox::app::climate_io::telemetry {

struct Stage27TelemetrySnapshot {
  std::uint64_t uptime_ms = 0U;
  std::uint64_t unix_time_s = 0U;
  std::int32_t reset_reason = 0;
  bool input_sampled = false;
  std::uint32_t io_status = 0U;

  std::uint32_t heap_internal = 0U;
  std::uint32_t heap_internal_min = 0U;
  std::uint32_t heap_internal_largest = 0U;
  std::uint32_t heap_psram = 0U;
  std::uint32_t heap_psram_min = 0U;
  std::uint32_t heap_psram_largest = 0U;
  std::uint32_t stack_free = 0U;

  bool scd_available = false;
  bool scd_sample = false;
  float scd_temperature_c = 0.0F;
  float scd_humidity_pct = 0.0F;
  float scd_co2_ppm = 0.0F;
  std::uint64_t scd_age_ms = 0U;
  std::uint32_t scd_read_errors = 0U;
  std::uint32_t scd_invalid = 0U;
  std::uint32_t scd_samples = 0U;

  bool rtc_available = false;
  bool rtc_trusted = false;
  std::uint32_t rtc_reads = 0U;
  std::uint32_t rtc_read_errors = 0U;
  std::uint32_t rtc_untrusted = 0U;
  std::uint64_t rtc_last_success_ms = 0U;
  std::uint64_t rtc_last_trusted_ms = 0U;

  bool ble_scanning = false;
  std::uint32_t ble_scan_starts = 0U;
  std::uint32_t ble_scan_errors = 0U;
  std::uint32_t ble_scan_restarts = 0U;
  std::uint32_t ble_scan_completes = 0U;
  std::uint32_t ble_adv_lock_drops = 0U;

  bool tp_sample = false;
  float tp_temperature_c = 0.0F;
  float tp_humidity_pct = 0.0F;
  std::uint64_t tp_age_ms = 0U;
  std::uint32_t tp_packets = 0U;
  std::uint32_t tp_accepted = 0U;
  std::uint32_t tp_rejected = 0U;

  bool xiaomi_sample = false;
  float xiaomi_temperature_c = 0.0F;
  float xiaomi_humidity_pct = 0.0F;
  std::uint64_t xiaomi_age_ms = 0U;
  std::uint32_t xiaomi_packets = 0U;
  std::uint32_t xiaomi_accepted = 0U;
  std::uint32_t xiaomi_rejected = 0U;

  std::uint32_t runtime_status = 0U;
  std::uint32_t runtime_mode = 0U;
  std::uint32_t rule_arbitration_interventions = 0U;
  std::uint32_t rule_safety_interventions = 0U;
  float applied_heater = 0.0F;
  float applied_cooler = 0.0F;
  float applied_exhaust_fan = 0.0F;
  float applied_humidifier = 0.0F;
  float applied_dehumidifier = 0.0F;
  float applied_co2_doser = 0.0F;

  bool sd_mounted = false;
  std::uint32_t sd_mount_errors = 0U;
  std::uint32_t sd_write_errors = 0U;
  std::uint32_t sd_queue_drops = 0U;
  std::uint32_t sd_records_written = 0U;
  std::uint32_t sd_records_skipped = 0U;
  std::uint64_t sd_last_write_ms = 0U;
};

std::size_t formatStage27TelemetryNdjson(char* buffer, std::size_t buffer_size,
                                         const Stage27TelemetrySnapshot& snapshot) noexcept;

} // namespace growbox::app::climate_io::telemetry
''',
)

write(
    "src/climate/telemetry/Stage27Telemetry.cpp",
    r'''#include "climate/telemetry/Stage27Telemetry.h"

#include <cstdio>

namespace growbox::app::climate_io::telemetry {
namespace {

const char* jsonBool(bool value) noexcept {
  return value ? "true" : "false";
}

} // namespace

std::size_t formatStage27TelemetryNdjson(char* buffer, std::size_t buffer_size,
                                         const Stage27TelemetrySnapshot& snapshot) noexcept {
  if (buffer == nullptr || buffer_size == 0U) {
    return 0U;
  }

  const int written = std::snprintf(
      buffer, buffer_size,
      "{\"type\":\"telemetry\",\"schema\":\"growbox-log-v1\","
      "\"uptime_ms\":%llu,\"unix_time_s\":%llu,\"reset_reason\":%d,"
      "\"input_sampled\":%s,\"io_status\":%u,"
      "\"sensors\":{"
      "\"scd41\":{\"sample\":%s,\"available\":%s,\"temperature_c\":%.2f,"
      "\"humidity_pct\":%.2f,\"co2_ppm\":%.0f,\"age_ms\":%llu,"
      "\"read_errors\":%u,\"invalid\":%u,\"samples\":%u},"
      "\"tp357\":{\"sample\":%s,\"temperature_c\":%.2f,\"humidity_pct\":%.2f,"
      "\"age_ms\":%llu,\"packets\":%u,\"accepted\":%u,\"rejected\":%u},"
      "\"xiaomi\":{\"sample\":%s,\"temperature_c\":%.2f,\"humidity_pct\":%.2f,"
      "\"age_ms\":%llu,\"packets\":%u,\"accepted\":%u,\"rejected\":%u}},"
      "\"rtc\":{\"available\":%s,\"trusted\":%s,\"reads\":%u,"
      "\"read_errors\":%u,\"untrusted\":%u,\"last_success_ms\":%llu,"
      "\"last_trusted_ms\":%llu},"
      "\"ble\":{\"scanning\":%s,\"scan_starts\":%u,\"scan_errors\":%u,"
      "\"scan_restarts\":%u,\"scan_completes\":%u,\"adv_lock_drops\":%u},"
      "\"controller\":{\"runtime_status\":%u,\"runtime_mode\":%u,"
      "\"rule_arbitration_interventions\":%u,\"rule_safety_interventions\":%u,"
      "\"applied\":{\"heater\":%.3f,\"cooler\":%.3f,\"exhaust_fan\":%.3f,"
      "\"humidifier\":%.3f,\"dehumidifier\":%.3f,\"co2_doser\":%.3f},"
      "\"outputs\":\"fake-locked\"},"
      "\"system\":{\"heap_internal\":%u,\"heap_internal_min\":%u,"
      "\"heap_internal_largest\":%u,\"heap_psram\":%u,\"heap_psram_min\":%u,"
      "\"heap_psram_largest\":%u,\"stack_free\":%u},"
      "\"storage\":{\"mounted\":%s,\"mount_errors\":%u,\"write_errors\":%u,"
      "\"queue_drops\":%u,\"records_written\":%u,\"records_skipped\":%u,"
      "\"last_write_ms\":%llu}}",
      static_cast<unsigned long long>(snapshot.uptime_ms),
      static_cast<unsigned long long>(snapshot.unix_time_s), snapshot.reset_reason,
      jsonBool(snapshot.input_sampled), static_cast<unsigned>(snapshot.io_status),
      jsonBool(snapshot.scd_sample), jsonBool(snapshot.scd_available),
      static_cast<double>(snapshot.scd_temperature_c), static_cast<double>(snapshot.scd_humidity_pct),
      static_cast<double>(snapshot.scd_co2_ppm),
      static_cast<unsigned long long>(snapshot.scd_age_ms), snapshot.scd_read_errors,
      snapshot.scd_invalid, snapshot.scd_samples, jsonBool(snapshot.tp_sample),
      static_cast<double>(snapshot.tp_temperature_c), static_cast<double>(snapshot.tp_humidity_pct),
      static_cast<unsigned long long>(snapshot.tp_age_ms), snapshot.tp_packets, snapshot.tp_accepted,
      snapshot.tp_rejected, jsonBool(snapshot.xiaomi_sample),
      static_cast<double>(snapshot.xiaomi_temperature_c),
      static_cast<double>(snapshot.xiaomi_humidity_pct),
      static_cast<unsigned long long>(snapshot.xiaomi_age_ms), snapshot.xiaomi_packets,
      snapshot.xiaomi_accepted, snapshot.xiaomi_rejected, jsonBool(snapshot.rtc_available),
      jsonBool(snapshot.rtc_trusted), snapshot.rtc_reads, snapshot.rtc_read_errors,
      snapshot.rtc_untrusted, static_cast<unsigned long long>(snapshot.rtc_last_success_ms),
      static_cast<unsigned long long>(snapshot.rtc_last_trusted_ms), jsonBool(snapshot.ble_scanning),
      snapshot.ble_scan_starts, snapshot.ble_scan_errors, snapshot.ble_scan_restarts,
      snapshot.ble_scan_completes, snapshot.ble_adv_lock_drops, snapshot.runtime_status,
      snapshot.runtime_mode, snapshot.rule_arbitration_interventions,
      snapshot.rule_safety_interventions, static_cast<double>(snapshot.applied_heater),
      static_cast<double>(snapshot.applied_cooler), static_cast<double>(snapshot.applied_exhaust_fan),
      static_cast<double>(snapshot.applied_humidifier),
      static_cast<double>(snapshot.applied_dehumidifier),
      static_cast<double>(snapshot.applied_co2_doser), snapshot.heap_internal,
      snapshot.heap_internal_min, snapshot.heap_internal_largest, snapshot.heap_psram,
      snapshot.heap_psram_min, snapshot.heap_psram_largest, snapshot.stack_free,
      jsonBool(snapshot.sd_mounted), snapshot.sd_mount_errors, snapshot.sd_write_errors,
      snapshot.sd_queue_drops, snapshot.sd_records_written, snapshot.sd_records_skipped,
      static_cast<unsigned long long>(snapshot.sd_last_write_ms));

  if (written < 0 || static_cast<std::size_t>(written) >= buffer_size) {
    buffer[0] = '\0';
    return 0U;
  }
  return static_cast<std::size_t>(written);
}

} // namespace growbox::app::climate_io::telemetry
''',
)

write(
    "src/climate/storage/Stage27SdDataLogger.h",
    r'''#pragma once

#include "climate/telemetry/Stage27Telemetry.h"

#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <freertos/task.h>
#include <sdmmc_cmd.h>

#include <atomic>
#include <cstdint>
#include <cstdio>

namespace growbox::app::climate_io::storage {

class Stage27SdDataLogger {
public:
  struct Pins {
    int mosi = 40;
    int miso = 13;
    int sclk = 39;
    int cs = 10;
  };

  explicit Stage27SdDataLogger(Pins pins) noexcept : pins_(pins) {}

  bool begin(const char* firmware_sha) noexcept;
  bool enqueue(const telemetry::Stage27TelemetrySnapshot& snapshot) noexcept;

  bool mounted() const noexcept {
    return mounted_.load(std::memory_order_relaxed);
  }
  std::uint32_t mountErrorCount() const noexcept {
    return mount_errors_.load(std::memory_order_relaxed);
  }
  std::uint32_t writeErrorCount() const noexcept {
    return write_errors_.load(std::memory_order_relaxed);
  }
  std::uint32_t queueDropCount() const noexcept {
    return queue_drops_.load(std::memory_order_relaxed);
  }
  std::uint32_t recordsWritten() const noexcept {
    return records_written_.load(std::memory_order_relaxed);
  }
  std::uint32_t recordsSkipped() const noexcept {
    return records_skipped_.load(std::memory_order_relaxed);
  }
  std::uint64_t lastWriteMs() const noexcept {
    return last_write_ms_.load(std::memory_order_relaxed);
  }

private:
  static void taskEntry(void* context) noexcept;
  void taskLoop() noexcept;
  bool ensureStorage(const telemetry::Stage27TelemetrySnapshot& snapshot) noexcept;
  bool mountStorage(const telemetry::Stage27TelemetrySnapshot& snapshot) noexcept;
  bool openSession(const telemetry::Stage27TelemetrySnapshot& snapshot) noexcept;
  bool writeRecord(const telemetry::Stage27TelemetrySnapshot& snapshot) noexcept;
  void closeMountedStorage() noexcept;

  static constexpr std::uint32_t kQueueDepth = 16U;
  static constexpr std::uint64_t kMountRetryMs = 30'000U;

  Pins pins_{};
  QueueHandle_t queue_ = nullptr;
  TaskHandle_t task_ = nullptr;
  sdmmc_card_t* card_ = nullptr;
  std::FILE* file_ = nullptr;
  bool spi_initialized_ = false;
  std::uint64_t next_mount_attempt_ms_ = 0U;
  std::uint32_t session_id_ = 0U;
  char firmware_sha_[48]{};
  char session_path_[160]{};

  std::atomic<bool> mounted_{false};
  std::atomic<std::uint32_t> mount_errors_{0U};
  std::atomic<std::uint32_t> write_errors_{0U};
  std::atomic<std::uint32_t> queue_drops_{0U};
  std::atomic<std::uint32_t> records_written_{0U};
  std::atomic<std::uint32_t> records_skipped_{0U};
  std::atomic<std::uint64_t> last_write_ms_{0U};
};

} // namespace growbox::app::climate_io::storage
''',
)

write(
    "src/climate/storage/Stage27SdDataLogger.cpp",
    r'''#include "climate/storage/Stage27SdDataLogger.h"

#include <driver/sdspi_host.h>
#include <driver/spi_master.h>
#include <esp_err.h>
#include <esp_log.h>
#include <esp_random.h>
#include <esp_vfs_fat.h>

#include <cerrno>
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
  slot_config.gpio_cs = pins_.cs;
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
  ESP_LOGI(kTag, "SD mounted on SPI2 MOSI=%d MISO=%d CLK=%d CS=%d", pins_.mosi, pins_.miso,
           pins_.sclk, pins_.cs);
  return openSession(snapshot);
}

bool Stage27SdDataLogger::openSession(
    const telemetry::Stage27TelemetrySnapshot& snapshot) noexcept {
  if (file_ != nullptr) {
    return true;
  }

  session_id_ = esp_random();
  if (snapshot.rtc_trusted && snapshot.unix_time_s != 0U) {
    std::snprintf(session_path_, sizeof(session_path_), "%s/session-%llu-%08x.ndjson",
                  kDataDirectory, static_cast<unsigned long long>(snapshot.unix_time_s),
                  session_id_);
  } else {
    std::snprintf(session_path_, sizeof(session_path_), "%s/session-u%llu-%08x.ndjson",
                  kDataDirectory, static_cast<unsigned long long>(snapshot.uptime_ms), session_id_);
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
      "\"session_id\":\"%08x\",\"reset_reason\":%d,\"start_uptime_ms\":%llu,"
      "\"rtc_trusted\":%s,\"start_unix_time_s\":%llu,"
      "\"sd_spi\":{\"host\":2,\"mosi\":%d,\"miso\":%d,\"clk\":%d,\"cs\":%d}}\n",
      firmware_sha_, session_id_, snapshot.reset_reason,
      static_cast<unsigned long long>(snapshot.uptime_ms), snapshot.rtc_trusted ? "true" : "false",
      static_cast<unsigned long long>(snapshot.unix_time_s), pins_.mosi, pins_.miso, pins_.sclk,
      pins_.cs);
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
  const std::size_t length = telemetry::formatStage27TelemetryNdjson(buffer, sizeof(buffer), snapshot);
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
''',
)

write(
    "test/test_stage27_telemetry/test_main.cpp",
    r'''#include "climate/telemetry/Stage27Telemetry.h"

#include <cassert>
#include <cstring>

using growbox::app::climate_io::telemetry::formatStage27TelemetryNdjson;
using growbox::app::climate_io::telemetry::Stage27TelemetrySnapshot;

int main() {
  Stage27TelemetrySnapshot snapshot{};
  snapshot.uptime_ms = 123456U;
  snapshot.unix_time_s = 1788292800U;
  snapshot.reset_reason = 1;
  snapshot.input_sampled = true;
  snapshot.scd_available = true;
  snapshot.scd_sample = true;
  snapshot.scd_temperature_c = 24.25F;
  snapshot.scd_humidity_pct = 59.5F;
  snapshot.scd_co2_ppm = 721.0F;
  snapshot.rtc_available = true;
  snapshot.rtc_trusted = true;
  snapshot.ble_scanning = true;
  snapshot.tp_sample = true;
  snapshot.tp_temperature_c = 23.8F;
  snapshot.tp_humidity_pct = 71.0F;
  snapshot.xiaomi_sample = true;
  snapshot.xiaomi_temperature_c = 25.1F;
  snapshot.xiaomi_humidity_pct = 55.0F;
  snapshot.applied_exhaust_fan = 0.5F;
  snapshot.sd_mounted = true;
  snapshot.sd_records_written = 7U;

  char buffer[2048]{};
  const auto length = formatStage27TelemetryNdjson(buffer, sizeof(buffer), snapshot);
  assert(length > 0U);
  assert(std::strstr(buffer, "\"schema\":\"growbox-log-v1\"") != nullptr);
  assert(std::strstr(buffer, "\"uptime_ms\":123456") != nullptr);
  assert(std::strstr(buffer, "\"tp357\":{\"sample\":true") != nullptr);
  assert(std::strstr(buffer, "\"outputs\":\"fake-locked\"") != nullptr);
  assert(std::strstr(buffer, "\"mounted\":true") != nullptr);
  assert(std::strstr(buffer, "\"records_written\":7") != nullptr);

  char too_small[32]{};
  assert(formatStage27TelemetryNdjson(too_small, sizeof(too_small), snapshot) == 0U);
  return 0;
}
''',
)

replace_once(
    "src/climate/native/Ds3231ClockSource.h",
    "  std::uint64_t lastTrustedReadMs() const noexcept {\n    return last_trusted_read_ms_;\n  }\n",
    "  std::uint64_t lastTrustedReadMs() const noexcept {\n    return last_trusted_read_ms_;\n  }\n  std::uint64_t lastTrustedUnixTimeS() const noexcept {\n    return last_trusted_unix_time_s_;\n  }\n",
)
replace_once(
    "src/climate/native/Ds3231ClockSource.h",
    "  std::uint64_t last_trusted_read_ms_ = 0U;\n",
    "  std::uint64_t last_trusted_read_ms_ = 0U;\n  std::uint64_t last_trusted_unix_time_s_ = 0U;\n",
)
replace_once(
    "src/climate/native/Ds3231ClockSource.cpp",
    "  if (trusted_) {\n    last_trusted_read_ms_ = monotonic_ms;\n  } else {\n",
    "  if (trusted_) {\n    last_trusted_read_ms_ = monotonic_ms;\n    last_trusted_unix_time_s_ = decoded.unix_time_s;\n  } else {\n",
)

replace_once(
    "src/CMakeLists.txt",
    '    nvs_flash\n    sensirion_scd4x\n',
    '    nvs_flash\n    sensirion_scd4x\n    fatfs\n    sdmmc\n    esp_driver_spi\n    esp_driver_sdspi\n',
)
replace_once(
    "src/CMakeLists.txt",
    '      "climate/ClimateV6RealInputRuntime.cpp"\n',
    '      "climate/ClimateV6RealInputRuntime.cpp"\n      "climate/telemetry/Stage27Telemetry.cpp"\n      "climate/storage/Stage27SdDataLogger.cpp"\n',
)
replace_once(
    "src/CMakeLists.txt",
    'set(GROWBOX_FIRMWARE_GIT_SHA "unknown" CACHE STRING "Exact Git SHA embedded in Stage27 firmware")\n',
    'set(GROWBOX_FIRMWARE_GIT_SHA "unknown" CACHE STRING "Exact Git SHA embedded in Stage27 firmware")\nset(GROWBOX_STAGE27_SD_ENABLED "0" CACHE STRING "Enable Stage27 SD telemetry logger")\nset(GROWBOX_SD_MOSI_GPIO "40" CACHE STRING "Stage27 SD SPI MOSI GPIO")\nset(GROWBOX_SD_MISO_GPIO "13" CACHE STRING "Stage27 SD SPI MISO GPIO")\nset(GROWBOX_SD_SCLK_GPIO "39" CACHE STRING "Stage27 SD SPI clock GPIO")\nset(GROWBOX_SD_CS_GPIO "10" CACHE STRING "Stage27 SD SPI chip-select GPIO")\n',
)
replace_once(
    "src/CMakeLists.txt",
    '    GROWBOX_FIRMWARE_GIT_SHA="${GROWBOX_FIRMWARE_GIT_SHA}"\n',
    '    GROWBOX_FIRMWARE_GIT_SHA="${GROWBOX_FIRMWARE_GIT_SHA}"\n    GROWBOX_STAGE27_SD_ENABLED=${GROWBOX_STAGE27_SD_ENABLED}\n    GROWBOX_SD_MOSI_GPIO=${GROWBOX_SD_MOSI_GPIO}\n    GROWBOX_SD_MISO_GPIO=${GROWBOX_SD_MISO_GPIO}\n    GROWBOX_SD_SCLK_GPIO=${GROWBOX_SD_SCLK_GPIO}\n    GROWBOX_SD_CS_GPIO=${GROWBOX_SD_CS_GPIO}\n',
)

replace_once(
    "test/host/CMakeLists.txt",
    'add_executable(\n  ble_climate_state_tests\n',
    'add_executable(\n  stage27_telemetry_tests\n  "${PROJECT_ROOT}/test/test_stage27_telemetry/test_main.cpp"\n  "${PROJECT_ROOT}/src/climate/telemetry/Stage27Telemetry.cpp"\n)\ntarget_include_directories(stage27_telemetry_tests PRIVATE "${PROJECT_ROOT}/src")\ntarget_compile_features(stage27_telemetry_tests PRIVATE cxx_std_17)\ntarget_compile_options(stage27_telemetry_tests PRIVATE -Wall -Wextra -Wpedantic)\n\nadd_executable(\n  ble_climate_state_tests\n',
)
replace_once(
    "test/host/CMakeLists.txt",
    '  target_link_libraries(climate_semantic_output_tests PRIVATE m)\n',
    '  target_link_libraries(climate_semantic_output_tests PRIVATE m)\n  target_link_libraries(stage27_telemetry_tests PRIVATE m)\n',
)
replace_once(
    "test/host/CMakeLists.txt",
    'add_test(NAME tp357_decoder_tests COMMAND tp357_decoder_tests)\n',
    'add_test(NAME tp357_decoder_tests COMMAND tp357_decoder_tests)\nadd_test(NAME stage27_telemetry_tests COMMAND stage27_telemetry_tests)\n',
)

write(
    "scripts/stage27c_crowpanel.sh",
    r'''#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
source "$ROOT/scripts/source_idf.sh"

COMMAND="${1:-build}"
BUILD_DIR="${STAGE27C_BUILD_DIR:-build/idf-stage27c-crowpanel}"
SDKCONFIG_PATH="${STAGE27C_SDKCONFIG:-${BUILD_DIR}/sdkconfig}"
BLE_TP357_MAC="${GROWBOX_BLE_TP357_MAC:-F7:5F:8D:0F:76:20}"
BLE_XIAOMI_MAC="${GROWBOX_BLE_XIAOMI_MAC:-A4:C1:38:4F:24:CD}"
FIRMWARE_GIT_SHA="${GROWBOX_FIRMWARE_GIT_SHA:-$(git rev-parse HEAD)}"
STAGE27C_PYTHON="${STAGE27C_PYTHON:-$ROOT/.venv/bin/python}"
if [[ ! -x "$STAGE27C_PYTHON" ]]; then
  STAGE27C_PYTHON="$(command -v python3)"
fi

idf_args=(
  -B "$BUILD_DIR"
  -D "SDKCONFIG=$SDKCONFIG_PATH"
  -D "SDKCONFIG_DEFAULTS=config/idf/sdkconfig.defaults;config/idf/sdkconfig.defaults.n8r8;config/idf/sdkconfig.defaults.stage27"
  -D "GROWBOX_BOARD_PROFILE=crowpanel-esp32s3-2_9-n8r8"
  -D "GROWBOX_APP_MODE=climate-v6-real-inputs"
  -D "GROWBOX_I2C_SDA_GPIO=21"
  -D "GROWBOX_I2C_SCL_GPIO=38"
  -D "GROWBOX_BLE_TP357_MAC=$BLE_TP357_MAC"
  -D "GROWBOX_BLE_XIAOMI_MAC=$BLE_XIAOMI_MAC"
  -D "GROWBOX_FIRMWARE_GIT_SHA=$FIRMWARE_GIT_SHA"
  -D "GROWBOX_STAGE27_SD_ENABLED=1"
  -D "GROWBOX_SD_MOSI_GPIO=40"
  -D "GROWBOX_SD_MISO_GPIO=13"
  -D "GROWBOX_SD_SCLK_GPIO=39"
  -D "GROWBOX_SD_CS_GPIO=10"
)

resolved_port=""
resolve_crowpanel_port() {
  if [[ -n "${PORT:-}" ]]; then
    resolved_port="$PORT"
  else
    resolved_port="$($STAGE27C_PYTHON -c 'from tools.stage27c_soak import detect_ch340_port; print(detect_ch340_port())')"
  fi
  if [[ -z "$resolved_port" ]]; then
    echo "Unable to resolve CrowPanel serial port" >&2
    exit 2
  fi
  echo "CrowPanel serial port: $resolved_port" >&2
}

verify_esp32s3_port() {
  local probe
  if ! probe="$(esptool.py --port "$resolved_port" chip_id 2>&1)"; then
    echo "$probe" >&2
    echo "Unable to identify chip on $resolved_port; refusing to flash" >&2
    exit 2
  fi
  echo "$probe" >&2
  if ! grep -q "ESP32-S3" <<<"$probe"; then
    echo "Port $resolved_port is not ESP32-S3; refusing to flash" >&2
    exit 2
  fi
}

case "$COMMAND" in
  build)
    idf.py "${idf_args[@]}" build
    ;;
  flash)
    resolve_crowpanel_port
    verify_esp32s3_port
    idf.py "${idf_args[@]}" -p "$resolved_port" build flash
    ;;
  monitor)
    resolve_crowpanel_port
    idf.py -B "$BUILD_DIR" -p "$resolved_port" monitor
    ;;
  flash-monitor)
    resolve_crowpanel_port
    verify_esp32s3_port
    idf.py "${idf_args[@]}" -p "$resolved_port" build flash monitor
    ;;
  clean)
    rm -rf "$BUILD_DIR"
    ;;
  *)
    echo "Usage: $0 {build|flash|monitor|flash-monitor|clean}" >&2
    exit 2
    ;;
esac
''',
)

write(
    "src/climate/ClimateV6RealInputRuntime.cpp",
    r'''#include "climate/ClimateV6RealInputRuntime.h"

#include "climate/ClimateApplication.h"
#include "climate/ClimateCompositeInput.h"
#include "climate/native/BleClimateScanner.h"
#include "climate/native/Ds3231ClockSource.h"
#include "climate/native/NativeI2cBus.h"
#include "climate/native/Scd41InsideSource.h"
#include "climate/storage/Stage27SdDataLogger.h"
#include "climate/telemetry/Stage27Telemetry.h"
#include "demo/protocol/HeapDiagnostics.h"

#include <esp_err.h>
#include <esp_log.h>
#include <esp_system.h>
#include <esp_timer.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include <cstdint>

#ifndef GROWBOX_I2C_SDA_GPIO
#define GROWBOX_I2C_SDA_GPIO 8
#endif
#ifndef GROWBOX_I2C_SCL_GPIO
#define GROWBOX_I2C_SCL_GPIO 9
#endif
#ifndef GROWBOX_BLE_TP357_MAC
#define GROWBOX_BLE_TP357_MAC ""
#endif
#ifndef GROWBOX_BLE_XIAOMI_MAC
#define GROWBOX_BLE_XIAOMI_MAC ""
#endif
#ifndef GROWBOX_FIRMWARE_GIT_SHA
#define GROWBOX_FIRMWARE_GIT_SHA "unknown"
#endif
#ifndef GROWBOX_STAGE27_SD_ENABLED
#define GROWBOX_STAGE27_SD_ENABLED 0
#endif
#ifndef GROWBOX_SD_MOSI_GPIO
#define GROWBOX_SD_MOSI_GPIO 40
#endif
#ifndef GROWBOX_SD_MISO_GPIO
#define GROWBOX_SD_MISO_GPIO 13
#endif
#ifndef GROWBOX_SD_SCLK_GPIO
#define GROWBOX_SD_SCLK_GPIO 39
#endif
#ifndef GROWBOX_SD_CS_GPIO
#define GROWBOX_SD_CS_GPIO 10
#endif

namespace growbox::app::climate_io {
namespace {

constexpr char kTag[] = "climate_stage27";
constexpr std::uint64_t kTickIntervalMs = 1'000U;

class LockedFakeRoleDriver final : public ClimateRoleDriver {
public:
  bool apply(ClimateActuatorRole, float, std::uint64_t) noexcept override {
    return true;
  }
};

class Stage27InsideSource final : public InsideEnvironmentSource {
public:
  Stage27InsideSource(native::BleClimateScanner& ble, native::Scd41InsideSource& scd41) noexcept
      : ble_(ble), scd41_(scd41) {}

  bool sample(std::uint64_t monotonic_ms, InsideEnvironmentSnapshot& output) noexcept override {
    output = {};

    native::BleClimateReading tp357{};
    const bool tp357_sampled = ble_.sampleTp357(monotonic_ms, tp357);
    if (tp357_sampled) {
      output.air_temperature_c = {tp357.temperature_c, true, tp357.age_ms};
      output.relative_humidity_pct = {tp357.relative_humidity_pct, true, tp357.age_ms};
    }

    InsideEnvironmentSnapshot scd41{};
    if (scd41_.sample(monotonic_ms, scd41) && scd41.co2_ppm.valid) {
      output.co2_ppm = scd41.co2_ppm;
    }

    return tp357_sampled || output.co2_ppm.valid;
  }

private:
  native::BleClimateScanner& ble_;
  native::Scd41InsideSource& scd41_;
};

class Stage27NearbySource final : public OutsideEnvironmentSource {
public:
  explicit Stage27NearbySource(native::BleClimateScanner& ble) noexcept : ble_(ble) {}

  bool sample(std::uint64_t monotonic_ms, OutsideEnvironmentSnapshot& output) noexcept override {
    output = {};
    native::BleClimateReading xiaomi{};
    if (!ble_.sampleXiaomi(monotonic_ms, xiaomi)) {
      return false;
    }
    output.air_temperature_c = {xiaomi.temperature_c, true, xiaomi.age_ms};
    output.relative_humidity_pct = {xiaomi.relative_humidity_pct, true, xiaomi.age_ms};
    return true;
  }

private:
  native::BleClimateScanner& ble_;
};

class FixedStage27ScheduleConfigSource final : public ClimateScheduleConfigSource {
public:
  bool resolve(std::uint64_t, const ClimateWallClockSnapshot& clock,
               ClimateScheduleConfigSnapshot& output) noexcept override {
    if (!clock.valid) {
      return false;
    }
    output = {};
    output.sensor_timeout_ms = ::growbox::climate::kDefaultSensorTimeoutMs;
    output.humidity_control_mode = ::growbox::climate::HumidityControlMode::Rh;
    output.capabilities.heater = true;
    output.capabilities.cooler = true;
    output.capabilities.exhaust_fan = true;
    output.capabilities.humidifier = true;
    output.capabilities.dehumidifier = true;
    output.capabilities.co2_doser = true;

    const std::uint8_t hour = static_cast<std::uint8_t>((clock.unix_time_s / 3600U) % 24U);
    const bool day = hour >= 6U && hour < 22U;
    output.targets.air_temperature_c = day ? 24.5F : 21.5F;
    output.targets.relative_humidity_pct = day ? 58.0F : 65.0F;
    output.targets.air_vpd_kpa = day ? 1.2F : 0.9F;
    output.targets.co2_enabled = day;
    output.targets.co2_ppm = day ? 950.0F : 450.0F;
    output.schedule.light_level = day ? 1.0F : 0.0F;
    return true;
  }
};

std::uint64_t monotonicMilliseconds() noexcept {
  return static_cast<std::uint64_t>(esp_timer_get_time()) / 1000U;
}

::growbox::climate::ClimateRuntimeConfig runtimeConfig() noexcept {
  ::growbox::climate::ClimateRuntimeConfig config{};
  config.mode = ::growbox::climate::ClimatePolicyMode::Rule;
  config.sensor_timeout_ms = ::growbox::climate::kDefaultSensorTimeoutMs;
  config.timestep_s = 1.0F;
  return config;
}

} // namespace

[[noreturn]] void runClimateV6RealInputRuntime() noexcept {
  native::NativeI2cBus i2c(GROWBOX_I2C_SDA_GPIO, GROWBOX_I2C_SCL_GPIO);
  const bool i2c_ready = i2c.begin() == ESP_OK;
  const esp_err_t scd41_probe = i2c_ready ? i2c.probe(0x62U) : ESP_ERR_INVALID_STATE;
  const esp_err_t rtc_probe = i2c_ready ? i2c.probe(0x68U) : ESP_ERR_INVALID_STATE;
  ESP_LOGI(kTag, "I2C probe: scd41_0x62=%s ds3231_0x68=%s", esp_err_to_name(scd41_probe),
           esp_err_to_name(rtc_probe));

  native::Scd41InsideSource scd41;
  native::Ds3231ClockSource clock;
  native::BleClimateScanner ble;
  const bool scd41_ready = i2c_ready && scd41.begin(i2c);
  const bool rtc_ready = i2c_ready && clock.begin(i2c);
  const bool ble_ready = ble.begin(GROWBOX_BLE_TP357_MAC, GROWBOX_BLE_XIAOMI_MAC);

  storage::Stage27SdDataLogger sd_logger(
      {GROWBOX_SD_MOSI_GPIO, GROWBOX_SD_MISO_GPIO, GROWBOX_SD_SCLK_GPIO, GROWBOX_SD_CS_GPIO});
  const bool sd_enabled = GROWBOX_STAGE27_SD_ENABLED != 0;
  const bool sd_logger_ready = sd_enabled && sd_logger.begin(GROWBOX_FIRMWARE_GIT_SHA);

  Stage27InsideSource inside(ble, scd41);
  Stage27NearbySource outside(ble);
  FixedStage27ScheduleConfigSource schedule_config;
  CompositeClimateSnapshotProvider composite(inside, outside, clock, schedule_config);
  LockedFakeRoleDriver output_driver;
  ::growbox::climate::ClimateRuntimeController runtime(nullptr, runtimeConfig());
  ClimateApplication application(runtime, composite, output_driver);

  const esp_reset_reason_t reset_reason = esp_reset_reason();
  ESP_LOGI(kTag,
           "Stage27 real-input runtime: i2c=%d scd41=%d ds3231=%d ble=%d sd_enabled=%d "
           "sd_logger=%d outputs=fake-locked",
           i2c_ready, scd41_ready, rtc_ready, ble_ready, sd_enabled, sd_logger_ready);
  ESP_LOGI(kTag, "Stage27 soak boot: firmware_sha=%s reset_reason=%d", GROWBOX_FIRMWARE_GIT_SHA,
           static_cast<int>(reset_reason));

  std::uint32_t diagnostic_tick = 0U;
  while (true) {
    const std::uint64_t now_ms = monotonicMilliseconds();
    ::growbox::climate::ClimateRuntimeDecision decision{};
    const auto result = application.tick(now_ms, decision);
    if ((diagnostic_tick++ % 10U) == 0U) {
      native::BleClimateReading tp357{};
      native::BleClimateReading xiaomi{};
      const bool tp357_sampled = ble.sampleTp357(now_ms, tp357);
      const bool xiaomi_sampled = ble.sampleXiaomi(now_ms, xiaomi);

      InsideEnvironmentSnapshot scd_diag{};
      static_cast<void>(scd41.sample(now_ms, scd_diag));
      const auto heap = ::growbox::demo::wire::captureHeapSnapshot();
      const auto task = ::growbox::demo::wire::captureTaskSnapshot();

      telemetry::Stage27TelemetrySnapshot snapshot{};
      snapshot.uptime_ms = now_ms;
      snapshot.unix_time_s = clock.trusted() ? clock.lastTrustedUnixTimeS() : 0U;
      snapshot.reset_reason = static_cast<std::int32_t>(reset_reason);
      snapshot.input_sampled = result.input_sampled;
      snapshot.io_status = static_cast<std::uint32_t>(result.io_status);
      snapshot.heap_internal = heap.free_internal;
      snapshot.heap_internal_min = heap.min_free_internal;
      snapshot.heap_internal_largest = heap.largest_free_internal;
      snapshot.heap_psram = heap.free_psram;
      snapshot.heap_psram_min = heap.min_free_psram;
      snapshot.heap_psram_largest = heap.largest_free_psram;
      snapshot.stack_free = task.main_stack_free_bytes;

      snapshot.scd_available = scd41.available();
      snapshot.scd_sample = scd41.hasMeasurement();
      snapshot.scd_temperature_c =
          scd_diag.air_temperature_c.valid ? scd_diag.air_temperature_c.value : 0.0F;
      snapshot.scd_humidity_pct =
          scd_diag.relative_humidity_pct.valid ? scd_diag.relative_humidity_pct.value : 0.0F;
      snapshot.scd_co2_ppm = scd_diag.co2_ppm.valid ? scd_diag.co2_ppm.value : 0.0F;
      snapshot.scd_age_ms = scd_diag.co2_ppm.valid ? scd_diag.co2_ppm.age_ms : 0U;
      snapshot.scd_read_errors = scd41.readErrorCount();
      snapshot.scd_invalid = scd41.invalidMeasurementCount();
      snapshot.scd_samples = scd41.successfulMeasurementCount();

      snapshot.rtc_available = clock.available();
      snapshot.rtc_trusted = clock.trusted();
      snapshot.rtc_reads = clock.successfulReadCount();
      snapshot.rtc_read_errors = clock.readErrorCount();
      snapshot.rtc_untrusted = clock.untrustedReadCount();
      snapshot.rtc_last_success_ms = clock.lastSuccessfulReadMs();
      snapshot.rtc_last_trusted_ms = clock.lastTrustedReadMs();

      snapshot.ble_scanning = ble.scanning();
      snapshot.ble_scan_starts = ble.scanStartCount();
      snapshot.ble_scan_errors = ble.scanStartErrorCount();
      snapshot.ble_scan_restarts = ble.scanRestartCount();
      snapshot.ble_scan_completes = ble.scanCompleteCount();
      snapshot.ble_adv_lock_drops = ble.advertisementLockDropCount();

      snapshot.tp_sample = tp357_sampled;
      snapshot.tp_temperature_c = tp357_sampled ? tp357.temperature_c : 0.0F;
      snapshot.tp_humidity_pct = tp357_sampled ? tp357.relative_humidity_pct : 0.0F;
      snapshot.tp_age_ms = tp357_sampled ? tp357.age_ms : 0U;
      snapshot.tp_packets = ble.tp357PacketCount();
      snapshot.tp_accepted = ble.tp357AcceptedCount();
      snapshot.tp_rejected = ble.tp357RejectedCount();

      snapshot.xiaomi_sample = xiaomi_sampled;
      snapshot.xiaomi_temperature_c = xiaomi_sampled ? xiaomi.temperature_c : 0.0F;
      snapshot.xiaomi_humidity_pct = xiaomi_sampled ? xiaomi.relative_humidity_pct : 0.0F;
      snapshot.xiaomi_age_ms = xiaomi_sampled ? xiaomi.age_ms : 0U;
      snapshot.xiaomi_packets = ble.xiaomiPacketCount();
      snapshot.xiaomi_accepted = ble.xiaomiAcceptedCount();
      snapshot.xiaomi_rejected = ble.xiaomiRejectedCount();

      snapshot.runtime_status = static_cast<std::uint32_t>(decision.status);
      snapshot.runtime_mode = static_cast<std::uint32_t>(decision.mode);
      snapshot.rule_arbitration_interventions = decision.rule.arbitration_interventions;
      snapshot.rule_safety_interventions = decision.rule.safety_interventions;
      snapshot.applied_heater = decision.applied.heater;
      snapshot.applied_cooler = decision.applied.cooler;
      snapshot.applied_exhaust_fan = decision.applied.exhaust_fan;
      snapshot.applied_humidifier = decision.applied.humidifier;
      snapshot.applied_dehumidifier = decision.applied.dehumidifier;
      snapshot.applied_co2_doser = decision.applied.co2_doser;

      snapshot.sd_mounted = sd_logger.mounted();
      snapshot.sd_mount_errors = sd_logger.mountErrorCount();
      snapshot.sd_write_errors = sd_logger.writeErrorCount();
      snapshot.sd_queue_drops = sd_logger.queueDropCount();
      snapshot.sd_records_written = sd_logger.recordsWritten();
      snapshot.sd_records_skipped = sd_logger.recordsSkipped();
      snapshot.sd_last_write_ms = sd_logger.lastWriteMs();

      ESP_LOGI(
          kTag,
          "soak_v=2 firmware_sha=%s uptime_ms=%llu reset_reason=%d input_sampled=%d io_status=%u "
          "heap_internal=%u heap_internal_min=%u heap_internal_largest=%u "
          "heap_psram=%u heap_psram_min=%u heap_psram_largest=%u stack_free=%u "
          "scd_available=%d scd_sample=%d scd_t=%.2f scd_rh=%.2f scd_co2=%.0f "
          "scd_age_ms=%llu scd_read_errors=%u scd_invalid=%u scd_samples=%u "
          "rtc_available=%d rtc_trusted=%d rtc_reads=%u rtc_read_errors=%u rtc_untrusted=%u "
          "rtc_last_success_ms=%llu rtc_last_trusted_ms=%llu rtc_unix_time_s=%llu "
          "ble_scanning=%d ble_scan_starts=%u ble_scan_errors=%u ble_scan_restarts=%u "
          "ble_scan_completes=%u ble_adv_lock_drops=%u "
          "tp_sample=%d tp_t=%.2f tp_rh=%.2f tp_age_ms=%llu tp_packets=%u tp_accepted=%u "
          "tp_rejected=%u xiaomi_sample=%d xiaomi_t=%.2f xiaomi_rh=%.2f "
          "xiaomi_age_ms=%llu xiaomi_packets=%u xiaomi_accepted=%u xiaomi_rejected=%u "
          "runtime_status=%u runtime_mode=%u rule_arb=%u rule_safety=%u "
          "applied_heater=%.3f applied_cooler=%.3f applied_fan=%.3f applied_humidifier=%.3f "
          "applied_dehumidifier=%.3f applied_co2=%.3f "
          "sd_mounted=%d sd_mount_errors=%u sd_write_errors=%u sd_queue_drops=%u "
          "sd_records_written=%u sd_records_skipped=%u sd_last_write_ms=%llu outputs=fake-locked",
          GROWBOX_FIRMWARE_GIT_SHA, static_cast<unsigned long long>(snapshot.uptime_ms),
          snapshot.reset_reason, snapshot.input_sampled, snapshot.io_status, snapshot.heap_internal,
          snapshot.heap_internal_min, snapshot.heap_internal_largest, snapshot.heap_psram,
          snapshot.heap_psram_min, snapshot.heap_psram_largest, snapshot.stack_free,
          snapshot.scd_available, snapshot.scd_sample, static_cast<double>(snapshot.scd_temperature_c),
          static_cast<double>(snapshot.scd_humidity_pct), static_cast<double>(snapshot.scd_co2_ppm),
          static_cast<unsigned long long>(snapshot.scd_age_ms), snapshot.scd_read_errors,
          snapshot.scd_invalid, snapshot.scd_samples, snapshot.rtc_available, snapshot.rtc_trusted,
          snapshot.rtc_reads, snapshot.rtc_read_errors, snapshot.rtc_untrusted,
          static_cast<unsigned long long>(snapshot.rtc_last_success_ms),
          static_cast<unsigned long long>(snapshot.rtc_last_trusted_ms),
          static_cast<unsigned long long>(snapshot.unix_time_s), snapshot.ble_scanning,
          snapshot.ble_scan_starts, snapshot.ble_scan_errors, snapshot.ble_scan_restarts,
          snapshot.ble_scan_completes, snapshot.ble_adv_lock_drops, snapshot.tp_sample,
          static_cast<double>(snapshot.tp_temperature_c), static_cast<double>(snapshot.tp_humidity_pct),
          static_cast<unsigned long long>(snapshot.tp_age_ms), snapshot.tp_packets,
          snapshot.tp_accepted, snapshot.tp_rejected, snapshot.xiaomi_sample,
          static_cast<double>(snapshot.xiaomi_temperature_c),
          static_cast<double>(snapshot.xiaomi_humidity_pct),
          static_cast<unsigned long long>(snapshot.xiaomi_age_ms), snapshot.xiaomi_packets,
          snapshot.xiaomi_accepted, snapshot.xiaomi_rejected, snapshot.runtime_status,
          snapshot.runtime_mode, snapshot.rule_arbitration_interventions,
          snapshot.rule_safety_interventions, static_cast<double>(snapshot.applied_heater),
          static_cast<double>(snapshot.applied_cooler), static_cast<double>(snapshot.applied_exhaust_fan),
          static_cast<double>(snapshot.applied_humidifier),
          static_cast<double>(snapshot.applied_dehumidifier),
          static_cast<double>(snapshot.applied_co2_doser), snapshot.sd_mounted,
          snapshot.sd_mount_errors, snapshot.sd_write_errors, snapshot.sd_queue_drops,
          snapshot.sd_records_written, snapshot.sd_records_skipped,
          static_cast<unsigned long long>(snapshot.sd_last_write_ms));

      if (sd_logger_ready) {
        static_cast<void>(sd_logger.enqueue(snapshot));
      }
    }
    vTaskDelay(pdMS_TO_TICKS(kTickIntervalMs));
  }
}

} // namespace growbox::app::climate_io
''',
)

replace_once(
    "tools/stage27c_soak.py",
    '    "xiaomi_rejected",\n)\n',
    '    "xiaomi_rejected",\n    "sd_mount_errors",\n    "sd_write_errors",\n    "sd_queue_drops",\n    "sd_records_written",\n    "sd_records_skipped",\n)\n',
)
replace_once(
    "tools/stage27c_soak.py",
    '    max_ble_adv_lock_drops: int = 0\n',
    '    max_ble_adv_lock_drops: int = 0\n    sd_fields_seen: bool = False\n    sd_unmounted_records: int = 0\n    max_sd_mount_errors: int = 0\n    max_sd_write_errors: int = 0\n    max_sd_queue_drops: int = 0\n    max_sd_records_skipped: int = 0\n    last_sd_records_written: int = 0\n',
)
replace_once(
    "tools/stage27c_soak.py",
    '        self.max_ble_adv_lock_drops = max(\n            self.max_ble_adv_lock_drops, int(record["ble_adv_lock_drops"])\n        )\n        self.records += 1\n',
    '        self.max_ble_adv_lock_drops = max(\n            self.max_ble_adv_lock_drops, int(record["ble_adv_lock_drops"])\n        )\n        if "sd_mounted" in record:\n            self.sd_fields_seen = True\n            if int(record["sd_mounted"]) != 1:\n                self.sd_unmounted_records += 1\n            self.max_sd_mount_errors = max(\n                self.max_sd_mount_errors, int(record.get("sd_mount_errors", 0))\n            )\n            self.max_sd_write_errors = max(\n                self.max_sd_write_errors, int(record.get("sd_write_errors", 0))\n            )\n            self.max_sd_queue_drops = max(\n                self.max_sd_queue_drops, int(record.get("sd_queue_drops", 0))\n            )\n            self.max_sd_records_skipped = max(\n                self.max_sd_records_skipped, int(record.get("sd_records_skipped", 0))\n            )\n            self.last_sd_records_written = int(record.get("sd_records_written", 0))\n        self.records += 1\n',
)
replace_once(
    "tools/stage27c_soak.py",
    '        max_xiaomi_age_ms: int | None = None,\n    ) -> list[str]:\n',
    '        max_xiaomi_age_ms: int | None = None,\n        require_sd: bool = False,\n    ) -> list[str]:\n',
)
replace_once(
    "tools/stage27c_soak.py",
    '        failures.extend(label for label, failed in hard_checks.items() if failed)\n',
    '        failures.extend(label for label, failed in hard_checks.items() if failed)\n        if require_sd:\n            sd_checks = {\n                "SD telemetry fields missing": not self.sd_fields_seen,\n                "SD logger not continuously mounted": self.sd_unmounted_records > 1,\n                "SD mount errors": self.max_sd_mount_errors > 0,\n                "SD write errors": self.max_sd_write_errors > 0,\n                "SD queue drops": self.max_sd_queue_drops > 0,\n                "SD records skipped": self.max_sd_records_skipped > 0,\n                "SD wrote no telemetry records": self.last_sd_records_written == 0,\n            }\n            failures.extend(label for label, failed in sd_checks.items() if failed)\n',
)
replace_once(
    "tools/stage27c_soak.py",
    '                        max_xiaomi_age_ms=args.max_xiaomi_age_ms,\n                    )\n',
    '                        max_xiaomi_age_ms=args.max_xiaomi_age_ms,\n                        require_sd=args.require_sd,\n                    )\n',
)
replace_once(
    "tools/stage27c_soak.py",
    '        max_xiaomi_age_ms=args.max_xiaomi_age_ms,\n    )\n',
    '        max_xiaomi_age_ms=args.max_xiaomi_age_ms,\n        require_sd=args.require_sd,\n    )\n',
)
replace_once(
    "tools/stage27c_soak.py",
    '    parser.add_argument("--max-xiaomi-age-ms", type=int)\n',
    '    parser.add_argument("--max-xiaomi-age-ms", type=int)\n    parser.add_argument(\n        "--require-sd",\n        action="store_true",\n        help="Require onboard SD logging to stay healthy after the initial mount window.",\n    )\n',
)

replace_once(
    "tests/test_stage27c_soak.py",
    '        "xiaomi_rejected": 25,\n        "outputs": "fake-locked",\n',
    '        "xiaomi_rejected": 25,\n        "sd_mounted": 1,\n        "sd_mount_errors": 0,\n        "sd_write_errors": 0,\n        "sd_queue_drops": 0,\n        "sd_records_written": 10,\n        "sd_records_skipped": 0,\n        "sd_last_write_ms": 900,\n        "outputs": "fake-locked",\n',
)
replace_once(
    "tests/test_stage27c_soak.py",
    '    assert "Xiaomi age exceeded 30000 ms" in violations\n',
    '    assert "Xiaomi age exceeded 30000 ms" in violations\n\n\ndef test_summary_can_require_healthy_sd_logging() -> None:\n    summary = SoakSummary(expected_sha="a" * 40)\n    first = parse_soak_line(_line(sd_mounted=0, sd_records_written=0))\n    second = parse_soak_line(_line(uptime_ms=11000, sd_mounted=1, sd_records_written=1))\n    assert first is not None and second is not None\n    summary.observe(first)\n    summary.observe(second)\n    assert summary.violations(require_sd=True) == []\n\n    failing = SoakSummary(expected_sha="a" * 40)\n    record = parse_soak_line(_line(sd_write_errors=1, sd_records_skipped=1))\n    assert record is not None\n    failing.observe(record)\n    violations = failing.violations(require_sd=True)\n    assert "SD write errors" in violations\n    assert "SD records skipped" in violations\n',
)
