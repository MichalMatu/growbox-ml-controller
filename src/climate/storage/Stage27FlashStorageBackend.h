#pragma once

#include "climate/storage/Stage27LogStorageBackend.h"

#include <wear_levelling.h>

#include <cstddef>
#include <cstdint>
#include <cstdio>

namespace growbox::app::climate_io::storage {

class Stage27FlashStorageBackend final : public Stage27LogStorageBackend {
public:
  Stage27StorageBackendKind kind() const noexcept override {
    return Stage27StorageBackendKind::Flash;
  }

  bool initialize() noexcept override {
    return true;
  }
  bool mount() noexcept override;
  bool beginSession(const char* session_header, std::uint32_t session_id) noexcept override;
  bool appendLine(const char* data, std::size_t length) noexcept override;
  void close() noexcept override;

private:
  bool openSegment() noexcept;
  void closeFile() noexcept;

  static constexpr std::uint32_t kSegmentSlots = 6U;
  static constexpr std::size_t kSegmentMaxBytes = 256U * 1024U;

  wl_handle_t wl_handle_ = WL_INVALID_HANDLE;
  bool mounted_ = false;
  std::FILE* file_ = nullptr;
  bool session_known_ = false;
  std::uint32_t session_id_ = 0U;
  std::uint32_t current_slot_ = 0U;
  std::uint32_t segment_number_ = 0U;
  std::size_t bytes_in_segment_ = 0U;
  char session_header_[512]{};
  char session_path_[32]{};
};

} // namespace growbox::app::climate_io::storage
