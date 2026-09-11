#include "climate/output/persistence/OutputNvsBackend.h"

#include <nvs.h>

namespace growbox::app::output {
namespace {

OutputPersistenceBackendStatus mapOpenError(esp_err_t error) noexcept {
  if (error == ESP_ERR_NVS_NOT_FOUND) {
    return OutputPersistenceBackendStatus::NotFound;
  }
  return error == ESP_OK ? OutputPersistenceBackendStatus::Ok
                         : OutputPersistenceBackendStatus::Unavailable;
}

} // namespace

OutputPersistenceBackendStatus OutputNvsBackend::read(OutputPersistenceBlob& blob,
                                                      std::size_t& stored_size) noexcept {
  blob.bytes.fill(0U);
  stored_size = 0U;

  nvs_handle_t handle{};
  const esp_err_t open_error = nvs_open(kOutputNvsNamespace, NVS_READONLY, &handle);
  if (open_error != ESP_OK) {
    return mapOpenError(open_error);
  }

  std::size_t required_size = 0U;
  esp_err_t error = nvs_get_blob(handle, kOutputNvsSnapshotKey, nullptr, &required_size);
  if (error == ESP_ERR_NVS_NOT_FOUND) {
    nvs_close(handle);
    return OutputPersistenceBackendStatus::NotFound;
  }
  if (error != ESP_OK || required_size > blob.bytes.size()) {
    nvs_close(handle);
    return OutputPersistenceBackendStatus::ReadFailed;
  }

  stored_size = required_size;
  if (required_size > 0U) {
    std::size_t read_size = blob.bytes.size();
    error = nvs_get_blob(handle, kOutputNvsSnapshotKey, blob.bytes.data(), &read_size);
    if (error != ESP_OK || read_size != required_size) {
      blob.bytes.fill(0U);
      stored_size = 0U;
      nvs_close(handle);
      return OutputPersistenceBackendStatus::ReadFailed;
    }
  }

  nvs_close(handle);
  return OutputPersistenceBackendStatus::Ok;
}

OutputPersistenceBackendStatus OutputNvsBackend::write(const OutputPersistenceBlob& blob) noexcept {
  nvs_handle_t handle{};
  const esp_err_t open_error = nvs_open(kOutputNvsNamespace, NVS_READWRITE, &handle);
  if (open_error != ESP_OK) {
    return mapOpenError(open_error) == OutputPersistenceBackendStatus::NotFound
               ? OutputPersistenceBackendStatus::Unavailable
               : mapOpenError(open_error);
  }

  esp_err_t error =
      nvs_set_blob(handle, kOutputNvsSnapshotKey, blob.bytes.data(), blob.bytes.size());
  if (error == ESP_OK) {
    error = nvs_commit(handle);
  }
  nvs_close(handle);
  return error == ESP_OK ? OutputPersistenceBackendStatus::Ok
                         : OutputPersistenceBackendStatus::WriteFailed;
}

} // namespace growbox::app::output
