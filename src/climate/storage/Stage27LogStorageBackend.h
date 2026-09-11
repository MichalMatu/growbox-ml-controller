#pragma once

#include "climate/storage/Stage27StorageTypes.h"

#include <cstddef>
#include <cstdint>

namespace growbox::app::climate_io::storage {

class Stage27LogStorageBackend {
public:
  virtual ~Stage27LogStorageBackend() = default;

  virtual Stage27StorageBackendKind kind() const noexcept = 0;
  virtual bool initialize() noexcept = 0;
  virtual bool mount() noexcept = 0;
  virtual bool beginSession(const char* session_header, std::uint32_t session_id) noexcept = 0;
  virtual bool appendLine(const char* data, std::size_t length) noexcept = 0;
  virtual void close() noexcept = 0;
};

} // namespace growbox::app::climate_io::storage
