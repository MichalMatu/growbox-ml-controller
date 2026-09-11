#include "climate/storage/Stage27FlashStorageBackend.h"

#include <esp_err.h>
#include <esp_log.h>
#include <esp_vfs_fat.h>

#include <cerrno>
#include <cinttypes>
#include <cstring>

namespace growbox::app::climate_io::storage {
namespace {

constexpr char kTag[] = "stage27_flash";
constexpr char kMountPoint[] = "/flog";
constexpr char kPartitionLabel[] = "telemetry";

} // namespace

bool Stage27FlashStorageBackend::mount() noexcept {
  if (mounted_) {
    return true;
  }

  esp_vfs_fat_mount_config_t mount_config{};
  mount_config.format_if_mount_failed = true;
  mount_config.max_files = 1;
  mount_config.allocation_unit_size = 4096U;

  wl_handle_ = WL_INVALID_HANDLE;
  const esp_err_t error =
      esp_vfs_fat_spiflash_mount_rw_wl(kMountPoint, kPartitionLabel, &mount_config, &wl_handle_);
  if (error != ESP_OK) {
    ESP_LOGW(kTag, "Flash fallback mount failed: %s", esp_err_to_name(error));
    wl_handle_ = WL_INVALID_HANDLE;
    return false;
  }

  mounted_ = true;
  ESP_LOGI(kTag, "Flash fallback mounted from partition '%s'", kPartitionLabel);
  return true;
}

bool Stage27FlashStorageBackend::beginSession(const char* session_header,
                                              std::uint32_t session_id) noexcept {
  if (!mounted_ || session_header == nullptr) {
    return false;
  }

  const std::size_t header_length = std::strlen(session_header);
  if (header_length == 0U || header_length >= sizeof(session_header_)) {
    ESP_LOGW(kTag, "Flash session header too large");
    return false;
  }

  closeFile();
  std::memcpy(session_header_, session_header, header_length + 1U);
  if (session_known_ && session_id_ == session_id) {
    current_slot_ = (current_slot_ + 1U) % kSegmentSlots;
    ++segment_number_;
  } else {
    session_known_ = true;
    session_id_ = session_id;
    current_slot_ = session_id % kSegmentSlots;
    segment_number_ = 0U;
  }
  return openSegment();
}

bool Stage27FlashStorageBackend::appendLine(const char* data, std::size_t length) noexcept {
  if (file_ == nullptr || data == nullptr || length == 0U || length >= kSegmentMaxBytes) {
    return false;
  }

  if (bytes_in_segment_ + length + 1U > kSegmentMaxBytes) {
    closeFile();
    current_slot_ = (current_slot_ + 1U) % kSegmentSlots;
    ++segment_number_;
    if (!openSegment()) {
      return false;
    }
  }

  const bool ok = std::fwrite(data, 1U, length, file_) == length &&
                  std::fputc('\n', file_) != EOF && std::fflush(file_) == 0;
  if (!ok) {
    ESP_LOGW(kTag, "Flash fallback write failed: errno=%d", errno);
    return false;
  }
  bytes_in_segment_ += length + 1U;
  return true;
}

void Stage27FlashStorageBackend::close() noexcept {
  closeFile();
  if (!mounted_) {
    return;
  }
  const esp_err_t error = esp_vfs_fat_spiflash_unmount_rw_wl(kMountPoint, wl_handle_);
  if (error != ESP_OK) {
    ESP_LOGW(kTag, "Flash fallback unmount failed: %s", esp_err_to_name(error));
  }
  mounted_ = false;
  wl_handle_ = WL_INVALID_HANDLE;
}

bool Stage27FlashStorageBackend::openSegment() noexcept {
  std::snprintf(session_path_, sizeof(session_path_), "%s/F%" PRIu32 ".JL", kMountPoint,
                current_slot_);
  file_ = std::fopen(session_path_, "w");
  if (file_ == nullptr) {
    ESP_LOGW(kTag, "Failed to open flash segment %s: errno=%d", session_path_, errno);
    return false;
  }

  const std::size_t header_length = std::strlen(session_header_);
  const int marker_length = std::fprintf(file_, "%s\n{\"t\":\"seg\",\"n\":%" PRIu32 "}\n",
                                         session_header_, segment_number_);
  if (marker_length < 0 || std::fflush(file_) != 0) {
    ESP_LOGW(kTag, "Failed to initialize flash segment %s: errno=%d", session_path_, errno);
    closeFile();
    return false;
  }

  // marker_length includes the session header, both newlines and the segment marker.
  bytes_in_segment_ = static_cast<std::size_t>(marker_length);
  if (bytes_in_segment_ < header_length) {
    closeFile();
    return false;
  }
  ESP_LOGI(kTag, "Flash fallback segment opened: %s", session_path_);
  return true;
}

void Stage27FlashStorageBackend::closeFile() noexcept {
  if (file_ != nullptr) {
    std::fclose(file_);
    file_ = nullptr;
  }
  bytes_in_segment_ = 0U;
}

} // namespace growbox::app::climate_io::storage
