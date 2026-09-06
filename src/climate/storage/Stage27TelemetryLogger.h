#pragma once

#include "climate/storage/Stage27FlashStorageBackend.h"
#include "climate/storage/Stage27SdStorageBackend.h"
#include "climate/storage/Stage27StorageTypes.h"
#include "climate/telemetry/Stage27Telemetry.h"

#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <freertos/task.h>

#include <atomic>
#include <cstdint>

namespace growbox::app::climate_io::storage {

class Stage27TelemetryLogger {
public:
  struct Config {
    Stage27SdStorageBackend::Pins sd_pins{};
    bool sd_enabled = true;
    bool flash_fallback_enabled = false;
    bool sd_cmd0_precondition = false;
  };

  explicit Stage27TelemetryLogger(Config config) noexcept
      : config_(config), sd_backend_(config.sd_pins, config.sd_cmd0_precondition) {}

  bool begin(const char* firmware_sha) noexcept;
  bool enqueue(const telemetry::Stage27TelemetrySnapshot& snapshot) noexcept;
  Stage27StorageStatus status() const noexcept;

  static constexpr std::uint32_t taskStackBytes() noexcept { return 7168U; }

private:
  enum class PersistResult : std::uint8_t {
    Ok,
    BackendError,
    FormatError,
  };

  static void taskEntry(void* context) noexcept;
  void taskLoop() noexcept;

  bool ensureActiveStorage(const telemetry::Stage27TelemetrySnapshot& snapshot) noexcept;
  bool tryActivateSd(const telemetry::Stage27TelemetrySnapshot& snapshot) noexcept;
  bool tryActivateFlash(const telemetry::Stage27TelemetrySnapshot& snapshot) noexcept;
  void deactivateFailedBackend(std::uint64_t now_ms) noexcept;
  void setActiveBackend(Stage27LogStorageBackend* backend) noexcept;

  PersistResult ensureActiveSession(const telemetry::Stage27TelemetrySnapshot& snapshot) noexcept;
  PersistResult persistSnapshot(const telemetry::Stage27TelemetrySnapshot& snapshot) noexcept;
  PersistResult appendFormatted(const char* line, std::size_t length,
                                std::uint64_t now_ms) noexcept;

  static constexpr std::uint32_t kQueueDepth = 16U;
  static constexpr std::uint64_t kMountRetryMs = 60'000U;

  Config config_{};
  Stage27SdStorageBackend sd_backend_;
  Stage27FlashStorageBackend flash_backend_;
  Stage27LogStorageBackend* active_backend_ = nullptr;
  bool sd_initialized_ = false;
  bool flash_initialized_ = false;
  bool session_open_ = false;
  std::uint64_t next_sd_attempt_ms_ = 0U;
  std::uint64_t next_flash_attempt_ms_ = 0U;
  std::uint64_t next_sample_due_ms_ = 0U;
  std::uint64_t next_health_due_ms_ = 0U;
  std::uint32_t session_id_ = 0U;
  char firmware_sha_[48]{};

  QueueHandle_t queue_ = nullptr;
  TaskHandle_t task_ = nullptr;

  std::atomic<std::uint8_t> active_backend_kind_{
      static_cast<std::uint8_t>(Stage27StorageBackendKind::None)};
  std::atomic<bool> sd_mounted_{false};
  std::atomic<bool> flash_mounted_{false};
  std::atomic<std::uint32_t> sd_mount_errors_{0U};
  std::atomic<std::uint32_t> flash_mount_errors_{0U};
  std::atomic<std::uint32_t> write_errors_{0U};
  std::atomic<std::uint32_t> queue_drops_{0U};
  std::atomic<std::uint32_t> records_written_{0U};
  std::atomic<std::uint32_t> records_skipped_{0U};
  std::atomic<std::uint32_t> fallback_activations_{0U};
  std::atomic<std::uint32_t> sd_recoveries_{0U};
  std::atomic<std::uint64_t> last_write_ms_{0U};
};

} // namespace growbox::app::climate_io::storage
