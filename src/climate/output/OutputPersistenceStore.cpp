#include "climate/output/OutputPersistenceStore.h"

namespace growbox::app::output {

OutputPersistenceStore::OutputPersistenceStore(OutputPersistenceBackend& backend,
                                               const OutputPolicyConfig& safe_defaults) noexcept
    : backend_(backend), safe_defaults_(safe_defaults),
      valid_(validateOutputPolicyConfig(safe_defaults_) == OutputPolicyConfigStatus::Ok) {}

OutputPersistenceLoadResult OutputPersistenceStore::safeFallback(
    OutputPersistenceStoreStatus status, OutputPersistenceBackendStatus backend_status,
    OutputPersistenceStatus codec_status) const noexcept {
  OutputPersistenceLoadResult result{};
  result.status = status;
  result.backend_status = backend_status;
  result.codec_status = codec_status;
  if (!valid_ || !makeSafeOutputPersistenceSnapshot(safe_defaults_, result.snapshot)) {
    result.status = OutputPersistenceStoreStatus::InvalidSafeDefaults;
    result.backend_status = backend_status;
    result.codec_status = OutputPersistenceStatus::InvalidSafeDefaults;
    result.used_safe_defaults = false;
    result.snapshot = {};
    return result;
  }
  result.used_safe_defaults = true;
  return result;
}

OutputPersistenceLoadResult OutputPersistenceStore::load() noexcept {
  if (!valid_) {
    return safeFallback(OutputPersistenceStoreStatus::InvalidSafeDefaults,
                        OutputPersistenceBackendStatus::Unavailable,
                        OutputPersistenceStatus::InvalidSafeDefaults);
  }

  OutputPersistenceBlob blob{};
  std::size_t stored_size = 0U;
  const auto backend_status = backend_.read(blob, stored_size);
  if (backend_status == OutputPersistenceBackendStatus::NotFound) {
    return safeFallback(OutputPersistenceStoreStatus::DefaultedNotFound, backend_status,
                        OutputPersistenceStatus::InvalidLength);
  }
  if (backend_status != OutputPersistenceBackendStatus::Ok) {
    return safeFallback(OutputPersistenceStoreStatus::DefaultedBackendError, backend_status,
                        OutputPersistenceStatus::InvalidLength);
  }

  const auto decoded = decodeOutputPersistence(blob.bytes.data(), stored_size, safe_defaults_);
  if (decoded.status != OutputPersistenceStatus::Ok) {
    OutputPersistenceLoadResult result{};
    result.status = decoded.status == OutputPersistenceStatus::InvalidSafeDefaults
                        ? OutputPersistenceStoreStatus::InvalidSafeDefaults
                        : OutputPersistenceStoreStatus::DefaultedDecodeError;
    result.backend_status = backend_status;
    result.codec_status = decoded.status;
    result.used_safe_defaults = decoded.used_safe_defaults;
    result.snapshot = decoded.snapshot;
    return result;
  }

  OutputPersistenceLoadResult result{};
  result.status = OutputPersistenceStoreStatus::Ok;
  result.backend_status = backend_status;
  result.codec_status = decoded.status;
  result.used_safe_defaults = false;
  result.snapshot = decoded.snapshot;
  return result;
}

OutputPersistenceStoreStatus
OutputPersistenceStore::save(const OutputPersistenceSnapshot& snapshot) noexcept {
  if (!valid_) {
    return OutputPersistenceStoreStatus::InvalidSafeDefaults;
  }
  OutputPersistenceBlob blob{};
  if (encodeOutputPersistence(snapshot, blob) != OutputPersistenceStatus::Ok) {
    return OutputPersistenceStoreStatus::InvalidSnapshot;
  }
  return backend_.write(blob) == OutputPersistenceBackendStatus::Ok
             ? OutputPersistenceStoreStatus::Ok
             : OutputPersistenceStoreStatus::BackendWriteFailed;
}

} // namespace growbox::app::output
