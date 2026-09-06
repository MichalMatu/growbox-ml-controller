#include "climate/storage/Stage27TelemetryLogger.h"

#include "climate/telemetry/Stage27LogFormat.h"

#include <esp_log.h>
#include <esp_random.h>

#include <cstdio>

namespace growbox::app::climate_io::storage {
namespace {

constexpr char kTag[] = "stage27_store";
constexpr std::size_t kRecordBufferBytes = 1024U;
constexpr std::size_t kSessionBufferBytes = 512U;

} // namespace

bool Stage27TelemetryLogger::begin(const char* firmware_sha) noexcept {
  if (queue_ != nullptr || task_ != nullptr) {
    return true;
  }
  if (!config_.sd_enabled && !config_.flash_fallback_enabled) {
    ESP_LOGW(kTag, "No telemetry storage backend enabled");
    return false;
  }

  std::snprintf(firmware_sha_, sizeof(firmware_sha_), "%s",
                firmware_sha != nullptr ? firmware_sha : "unknown");
  session_id_ = esp_random();

  if (config_.sd_enabled) {
    sd_initialized_ = sd_backend_.initialize();
    if (!sd_initialized_) {
      sd_mount_errors_.fetch_add(1U, std::memory_order_relaxed);
    }
  }
  if (config_.flash_fallback_enabled) {
    flash_initialized_ = flash_backend_.initialize();
    if (!flash_initialized_) {
      flash_mount_errors_.fetch_add(1U, std::memory_order_relaxed);
    }
  }

  queue_ = xQueueCreate(kQueueDepth, sizeof(telemetry::Stage27TelemetrySnapshot));
  if (queue_ == nullptr) {
    ESP_LOGE(kTag, "Failed to allocate telemetry storage queue");
    return false;
  }

  if (xTaskCreate(&Stage27TelemetryLogger::taskEntry, "stage27_store", taskStackBytes(), this,
                  tskIDLE_PRIORITY + 1U, &task_) != pdPASS) {
    vQueueDelete(queue_);
    queue_ = nullptr;
    ESP_LOGE(kTag, "Failed to create telemetry storage task");
    return false;
  }

  ESP_LOGI(kTag, "Telemetry storage started: sd=%d flash_fallback=%d cmd0_compat=%d",
           config_.sd_enabled, config_.flash_fallback_enabled, config_.sd_cmd0_precondition);
  return true;
}

bool Stage27TelemetryLogger::enqueue(const telemetry::Stage27TelemetrySnapshot& snapshot) noexcept {
  if (queue_ == nullptr) {
    return false;
  }
  if (xQueueSend(queue_, &snapshot, 0U) != pdTRUE) {
    queue_drops_.fetch_add(1U, std::memory_order_relaxed);
    return false;
  }
  return true;
}

Stage27StorageStatus Stage27TelemetryLogger::status() const noexcept {
  Stage27StorageStatus result{};
  result.active_backend =
      static_cast<Stage27StorageBackendKind>(active_backend_kind_.load(std::memory_order_relaxed));
  result.sd_mounted = sd_mounted_.load(std::memory_order_relaxed);
  result.flash_mounted = flash_mounted_.load(std::memory_order_relaxed);
  result.sd_mount_errors = sd_mount_errors_.load(std::memory_order_relaxed);
  result.flash_mount_errors = flash_mount_errors_.load(std::memory_order_relaxed);
  result.write_errors = write_errors_.load(std::memory_order_relaxed);
  result.queue_drops = queue_drops_.load(std::memory_order_relaxed);
  result.records_written = records_written_.load(std::memory_order_relaxed);
  result.records_skipped = records_skipped_.load(std::memory_order_relaxed);
  result.fallback_activations = fallback_activations_.load(std::memory_order_relaxed);
  result.sd_recoveries = sd_recoveries_.load(std::memory_order_relaxed);
  result.last_write_ms = last_write_ms_.load(std::memory_order_relaxed);
  return result;
}

void Stage27TelemetryLogger::taskEntry(void* context) noexcept {
  static_cast<Stage27TelemetryLogger*>(context)->taskLoop();
}

void Stage27TelemetryLogger::taskLoop() noexcept {
  telemetry::Stage27TelemetrySnapshot snapshot{};
  while (true) {
    if (xQueueReceive(queue_, &snapshot, portMAX_DELAY) != pdTRUE) {
      continue;
    }

    bool persisted = false;
    for (unsigned attempt = 0U; attempt < 2U && !persisted; ++attempt) {
      if (!ensureActiveStorage(snapshot)) {
        break;
      }

      const PersistResult result = persistSnapshot(snapshot);
      if (result == PersistResult::Ok) {
        persisted = true;
        break;
      }
      if (result == PersistResult::FormatError) {
        write_errors_.fetch_add(1U, std::memory_order_relaxed);
        break;
      }

      write_errors_.fetch_add(1U, std::memory_order_relaxed);
      deactivateFailedBackend(snapshot.uptime_ms);
    }

    if (!persisted) {
      records_skipped_.fetch_add(1U, std::memory_order_relaxed);
    }
  }
}

bool Stage27TelemetryLogger::ensureActiveStorage(
    const telemetry::Stage27TelemetrySnapshot& snapshot) noexcept {
  if (active_backend_ == &sd_backend_) {
    return true;
  }

  if (active_backend_ == &flash_backend_) {
    if (config_.sd_enabled && snapshot.uptime_ms >= next_sd_attempt_ms_) {
      static_cast<void>(tryActivateSd(snapshot));
    }
    return active_backend_ != nullptr;
  }

  if (config_.sd_enabled && snapshot.uptime_ms >= next_sd_attempt_ms_ && tryActivateSd(snapshot)) {
    return true;
  }

  if (config_.flash_fallback_enabled && snapshot.uptime_ms >= next_flash_attempt_ms_ &&
      tryActivateFlash(snapshot)) {
    return true;
  }
  return false;
}

bool Stage27TelemetryLogger::tryActivateSd(
    const telemetry::Stage27TelemetrySnapshot& snapshot) noexcept {
  next_sd_attempt_ms_ = snapshot.uptime_ms + kMountRetryMs;

  if (!sd_initialized_) {
    sd_initialized_ = sd_backend_.initialize();
    if (!sd_initialized_) {
      sd_mount_errors_.fetch_add(1U, std::memory_order_relaxed);
      return false;
    }
  }

  if (!sd_backend_.mount()) {
    sd_mount_errors_.fetch_add(1U, std::memory_order_relaxed);
    return false;
  }
  sd_mounted_.store(true, std::memory_order_relaxed);

  if (active_backend_ == &flash_backend_) {
    flash_backend_.close();
    flash_mounted_.store(false, std::memory_order_relaxed);
    sd_recoveries_.fetch_add(1U, std::memory_order_relaxed);
    ESP_LOGI(kTag, "Telemetry storage recovered from flash fallback to SD");
  }

  setActiveBackend(&sd_backend_);
  return true;
}

bool Stage27TelemetryLogger::tryActivateFlash(
    const telemetry::Stage27TelemetrySnapshot& snapshot) noexcept {
  next_flash_attempt_ms_ = snapshot.uptime_ms + kMountRetryMs;

  if (!flash_initialized_) {
    flash_initialized_ = flash_backend_.initialize();
    if (!flash_initialized_) {
      flash_mount_errors_.fetch_add(1U, std::memory_order_relaxed);
      return false;
    }
  }

  if (!flash_backend_.mount()) {
    flash_mount_errors_.fetch_add(1U, std::memory_order_relaxed);
    return false;
  }
  flash_mounted_.store(true, std::memory_order_relaxed);
  fallback_activations_.fetch_add(1U, std::memory_order_relaxed);
  ESP_LOGW(kTag, "Telemetry storage using internal flash fallback");

  setActiveBackend(&flash_backend_);
  return true;
}

void Stage27TelemetryLogger::deactivateFailedBackend(std::uint64_t now_ms) noexcept {
  if (active_backend_ == nullptr) {
    return;
  }

  const Stage27StorageBackendKind failed_kind = active_backend_->kind();
  active_backend_->close();
  if (failed_kind == Stage27StorageBackendKind::Sd) {
    sd_mounted_.store(false, std::memory_order_relaxed);
    next_sd_attempt_ms_ = now_ms + kMountRetryMs;
  } else if (failed_kind == Stage27StorageBackendKind::Flash) {
    flash_mounted_.store(false, std::memory_order_relaxed);
    next_flash_attempt_ms_ = now_ms + kMountRetryMs;
  }
  setActiveBackend(nullptr);
}

void Stage27TelemetryLogger::setActiveBackend(Stage27LogStorageBackend* backend) noexcept {
  active_backend_ = backend;
  const Stage27StorageBackendKind kind =
      backend != nullptr ? backend->kind() : Stage27StorageBackendKind::None;
  active_backend_kind_.store(static_cast<std::uint8_t>(kind), std::memory_order_relaxed);
  session_open_ = false;
  next_sample_due_ms_ = 0U;
  next_health_due_ms_ = 0U;
}

Stage27TelemetryLogger::PersistResult Stage27TelemetryLogger::ensureActiveSession(
    const telemetry::Stage27TelemetrySnapshot& snapshot) noexcept {
  if (session_open_) {
    return PersistResult::Ok;
  }
  if (active_backend_ == nullptr) {
    return PersistResult::BackendError;
  }

  telemetry::Stage27LogSessionMetadata session{};
  session.firmware_sha = firmware_sha_;
  session.session_id = session_id_;
  session.backend = active_backend_->kind();
  session.reset_reason = snapshot.reset_reason;
  session.start_uptime_ms = snapshot.uptime_ms;
  session.rtc_trusted = snapshot.rtc_trusted;
  session.start_unix_time_s = snapshot.unix_time_s;

  char header[kSessionBufferBytes]{};
  const std::size_t header_length =
      telemetry::formatStage27SessionNdjson(header, sizeof(header), session);
  if (header_length == 0U) {
    ESP_LOGE(kTag, "Session header serialization overflow");
    return PersistResult::FormatError;
  }
  if (!active_backend_->beginSession(header, session_id_)) {
    return PersistResult::BackendError;
  }

  session_open_ = true;
  return PersistResult::Ok;
}

Stage27TelemetryLogger::PersistResult Stage27TelemetryLogger::persistSnapshot(
    const telemetry::Stage27TelemetrySnapshot& snapshot) noexcept {
  const PersistResult session_result = ensureActiveSession(snapshot);
  if (session_result != PersistResult::Ok) {
    return session_result;
  }

  const Stage27StorageBackendKind backend = active_backend_->kind();
  const std::uint64_t sample_interval_ms = stage27SampleIntervalMs(backend);
  const std::uint64_t health_interval_ms = stage27HealthIntervalMs(backend);
  const bool sample_due = next_sample_due_ms_ == 0U || snapshot.uptime_ms >= next_sample_due_ms_;
  const bool health_due = next_health_due_ms_ == 0U || snapshot.uptime_ms >= next_health_due_ms_;

  char line[kRecordBufferBytes]{};
  if (sample_due) {
    const std::size_t length = telemetry::formatStage27SampleNdjson(line, sizeof(line), snapshot);
    if (length == 0U) {
      ESP_LOGE(kTag, "Sample serialization overflow");
      return PersistResult::FormatError;
    }
    const PersistResult result = appendFormatted(line, length, snapshot.uptime_ms);
    if (result != PersistResult::Ok) {
      return result;
    }
    next_sample_due_ms_ = snapshot.uptime_ms + sample_interval_ms;
  }

  if (health_due) {
    const Stage27StorageStatus storage_status = status();
    const std::size_t length =
        telemetry::formatStage27HealthNdjson(line, sizeof(line), snapshot, storage_status);
    if (length == 0U) {
      ESP_LOGE(kTag, "Health serialization overflow");
      return PersistResult::FormatError;
    }
    const PersistResult result = appendFormatted(line, length, snapshot.uptime_ms);
    if (result != PersistResult::Ok) {
      return result;
    }
    next_health_due_ms_ = snapshot.uptime_ms + health_interval_ms;
  }

  return PersistResult::Ok;
}

Stage27TelemetryLogger::PersistResult
Stage27TelemetryLogger::appendFormatted(const char* line, std::size_t length,
                                        std::uint64_t now_ms) noexcept {
  if (active_backend_ == nullptr || !active_backend_->appendLine(line, length)) {
    return PersistResult::BackendError;
  }
  records_written_.fetch_add(1U, std::memory_order_relaxed);
  last_write_ms_.store(now_ms, std::memory_order_relaxed);
  return PersistResult::Ok;
}

} // namespace growbox::app::climate_io::storage
