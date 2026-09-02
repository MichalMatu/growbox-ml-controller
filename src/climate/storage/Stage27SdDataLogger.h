#pragma once

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
