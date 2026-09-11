#pragma once

#include <cstdint>

namespace growbox::app::climate_io::storage {

enum class Stage27StorageBackendKind : std::uint8_t {
  None = 0U,
  Sd = 1U,
  Flash = 2U,
};

struct Stage27StorageStatus {
  Stage27StorageBackendKind active_backend = Stage27StorageBackendKind::None;
  bool sd_mounted = false;
  bool flash_mounted = false;
  std::uint32_t sd_mount_errors = 0U;
  std::uint32_t flash_mount_errors = 0U;
  std::uint32_t write_errors = 0U;
  std::uint32_t queue_drops = 0U;
  std::uint32_t records_written = 0U;
  std::uint32_t records_skipped = 0U;
  std::uint32_t fallback_activations = 0U;
  std::uint32_t sd_recoveries = 0U;
  std::uint64_t last_write_ms = 0U;
};

constexpr const char* stage27StorageBackendName(Stage27StorageBackendKind backend) noexcept {
  switch (backend) {
  case Stage27StorageBackendKind::Sd:
    return "sd";
  case Stage27StorageBackendKind::Flash:
    return "flash";
  case Stage27StorageBackendKind::None:
  default:
    return "none";
  }
}

constexpr std::uint64_t stage27SampleIntervalMs(Stage27StorageBackendKind backend) noexcept {
  switch (backend) {
  case Stage27StorageBackendKind::Sd:
    return 10'000U;
  case Stage27StorageBackendKind::Flash:
    return 60'000U;
  case Stage27StorageBackendKind::None:
  default:
    return 0U;
  }
}

constexpr std::uint64_t stage27HealthIntervalMs(Stage27StorageBackendKind backend) noexcept {
  switch (backend) {
  case Stage27StorageBackendKind::Sd:
    return 60'000U;
  case Stage27StorageBackendKind::Flash:
    return 300'000U;
  case Stage27StorageBackendKind::None:
  default:
    return 0U;
  }
}

} // namespace growbox::app::climate_io::storage
