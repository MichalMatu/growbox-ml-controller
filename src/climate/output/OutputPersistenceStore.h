#pragma once

#include "climate/output/OutputPersistenceSchema.h"

#include <cstddef>
#include <cstdint>

namespace growbox::app::output {

enum class OutputPersistenceBackendStatus : std::uint8_t {
  Ok = 0U,
  NotFound,
  Unavailable,
  ReadFailed,
  WriteFailed,
};

class OutputPersistenceBackend {
public:
  virtual ~OutputPersistenceBackend() = default;
  virtual OutputPersistenceBackendStatus read(OutputPersistenceBlob& blob,
                                              std::size_t& stored_size) noexcept = 0;
  virtual OutputPersistenceBackendStatus write(const OutputPersistenceBlob& blob) noexcept = 0;
};

enum class OutputPersistenceStoreStatus : std::uint8_t {
  Ok = 0U,
  DefaultedNotFound,
  DefaultedBackendError,
  DefaultedDecodeError,
  InvalidSafeDefaults,
  InvalidSnapshot,
  BackendWriteFailed,
};

struct OutputPersistenceLoadResult {
  OutputPersistenceStoreStatus status = OutputPersistenceStoreStatus::InvalidSafeDefaults;
  OutputPersistenceBackendStatus backend_status = OutputPersistenceBackendStatus::Unavailable;
  OutputPersistenceStatus codec_status = OutputPersistenceStatus::InvalidSafeDefaults;
  bool used_safe_defaults = false;
  OutputPersistenceSnapshot snapshot{};
};

class OutputPersistenceStore final {
public:
  OutputPersistenceStore(OutputPersistenceBackend& backend,
                         const OutputPolicyConfig& safe_defaults) noexcept;

  bool valid() const noexcept {
    return valid_;
  }
  OutputPersistenceLoadResult load() noexcept;
  OutputPersistenceStoreStatus save(const OutputPersistenceSnapshot& snapshot) noexcept;

private:
  OutputPersistenceLoadResult safeFallback(OutputPersistenceStoreStatus status,
                                           OutputPersistenceBackendStatus backend_status,
                                           OutputPersistenceStatus codec_status) const noexcept;

  OutputPersistenceBackend& backend_;
  OutputPolicyConfig safe_defaults_{};
  bool valid_{false};
};

} // namespace growbox::app::output
