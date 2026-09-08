from pathlib import Path


def replace_once(path, old, new):
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{path}: expected one replacement, found {count}')
    p.write_text(text.replace(old, new, 1))

Path('src/climate/output/OutputPersistenceStore.h').write_text(r'''#pragma once

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

  bool valid() const noexcept { return valid_; }
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
''')

Path('src/climate/output/OutputPersistenceStore.cpp').write_text(r'''#include "climate/output/OutputPersistenceStore.h"

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
''')

Path('src/climate/output/OutputNvsBackend.h').write_text(r'''#pragma once

#include "climate/output/OutputPersistenceStore.h"

namespace growbox::app::output {

inline constexpr char kOutputNvsNamespace[] = "growbox_out";
inline constexpr char kOutputNvsSnapshotKey[] = "snapshot";

class OutputNvsBackend final : public OutputPersistenceBackend {
public:
  OutputPersistenceBackendStatus read(OutputPersistenceBlob& blob,
                                      std::size_t& stored_size) noexcept override;
  OutputPersistenceBackendStatus write(const OutputPersistenceBlob& blob) noexcept override;
};

} // namespace growbox::app::output
''')

Path('src/climate/output/OutputNvsBackend.cpp').write_text(r'''#include "climate/output/OutputNvsBackend.h"

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

OutputPersistenceBackendStatus
OutputNvsBackend::write(const OutputPersistenceBlob& blob) noexcept {
  nvs_handle_t handle{};
  const esp_err_t open_error = nvs_open(kOutputNvsNamespace, NVS_READWRITE, &handle);
  if (open_error != ESP_OK) {
    return mapOpenError(open_error) == OutputPersistenceBackendStatus::NotFound
               ? OutputPersistenceBackendStatus::Unavailable
               : mapOpenError(open_error);
  }

  esp_err_t error = nvs_set_blob(handle, kOutputNvsSnapshotKey, blob.bytes.data(), blob.bytes.size());
  if (error == ESP_OK) {
    error = nvs_commit(handle);
  }
  nvs_close(handle);
  return error == ESP_OK ? OutputPersistenceBackendStatus::Ok
                         : OutputPersistenceBackendStatus::WriteFailed;
}

} // namespace growbox::app::output
''')

Path('test/test_output_persistence_store/test_main.cpp').parent.mkdir(parents=True, exist_ok=True)
Path('test/test_output_persistence_store/test_main.cpp').write_text(r'''#include "climate/output/OutputPersistenceStore.h"

#include <cassert>
#include <cstddef>

namespace {
namespace output = growbox::app::output;

class FakeBackend final : public output::OutputPersistenceBackend {
public:
  output::OutputPersistenceBackendStatus read(output::OutputPersistenceBlob& output_blob,
                                              std::size_t& output_size) noexcept override {
    ++read_count;
    if (read_status != output::OutputPersistenceBackendStatus::Ok) {
      output_blob = {};
      output_size = 0U;
      return read_status;
    }
    output_blob = blob;
    output_size = stored_size;
    return read_status;
  }

  output::OutputPersistenceBackendStatus
  write(const output::OutputPersistenceBlob& input_blob) noexcept override {
    ++write_count;
    if (write_status == output::OutputPersistenceBackendStatus::Ok) {
      blob = input_blob;
      stored_size = blob.bytes.size();
    }
    return write_status;
  }

  output::OutputPersistenceBackendStatus read_status = output::OutputPersistenceBackendStatus::NotFound;
  output::OutputPersistenceBackendStatus write_status = output::OutputPersistenceBackendStatus::Ok;
  output::OutputPersistenceBlob blob{};
  std::size_t stored_size = 0U;
  unsigned read_count = 0U;
  unsigned write_count = 0U;
};

output::OutputPolicyConfig safePolicy() {
  return output::makeSafeDefaultOutputPolicyConfig(1U, 2U, 3U);
}

output::OutputPersistenceSnapshot snapshotWithCommand() {
  output::OutputPersistenceSnapshot snapshot{};
  assert(output::makeSafeOutputPersistenceSnapshot(safePolicy(), snapshot));
  snapshot.commands[0].has_last_successful_command = true;
  snapshot.commands[0].state = output::BinaryOutputState::On;
  return snapshot;
}

void assertSafeFallback(const output::OutputPersistenceLoadResult& result,
                        output::OutputPersistenceStoreStatus expected) {
  assert(result.status == expected);
  assert(result.used_safe_defaults);
  assert(result.snapshot.command_count == output::kOutputEndpointCapacity);
  for (std::size_t index = 0U; index < result.snapshot.command_count; ++index) {
    assert(!result.snapshot.commands[index].has_last_successful_command);
  }
}

void testRoundTripThroughBackendInterface() {
  FakeBackend backend;
  output::OutputPersistenceStore store(backend, safePolicy());
  assert(store.valid());
  const auto snapshot = snapshotWithCommand();
  assert(store.save(snapshot) == output::OutputPersistenceStoreStatus::Ok);
  assert(backend.write_count == 1U);
  backend.read_status = output::OutputPersistenceBackendStatus::Ok;
  const auto loaded = store.load();
  assert(loaded.status == output::OutputPersistenceStoreStatus::Ok);
  assert(!loaded.used_safe_defaults);
  assert(loaded.snapshot.commands[0].has_last_successful_command);
  assert(loaded.snapshot.commands[0].state == output::BinaryOutputState::On);
}

void testNotFoundDefaultsSafely() {
  FakeBackend backend;
  output::OutputPersistenceStore store(backend, safePolicy());
  const auto loaded = store.load();
  assertSafeFallback(loaded, output::OutputPersistenceStoreStatus::DefaultedNotFound);
  assert(loaded.backend_status == output::OutputPersistenceBackendStatus::NotFound);
}

void testBackendReadFailureDefaultsSafely() {
  FakeBackend backend;
  backend.read_status = output::OutputPersistenceBackendStatus::ReadFailed;
  output::OutputPersistenceStore store(backend, safePolicy());
  const auto loaded = store.load();
  assertSafeFallback(loaded, output::OutputPersistenceStoreStatus::DefaultedBackendError);
  assert(loaded.backend_status == output::OutputPersistenceBackendStatus::ReadFailed);
}

void testCorruptAndTruncatedPayloadsDefaultSafely() {
  FakeBackend backend;
  output::OutputPersistenceStore store(backend, safePolicy());
  assert(store.save(snapshotWithCommand()) == output::OutputPersistenceStoreStatus::Ok);
  backend.read_status = output::OutputPersistenceBackendStatus::Ok;

  backend.blob.bytes[20] ^= 0x55U;
  auto loaded = store.load();
  assertSafeFallback(loaded, output::OutputPersistenceStoreStatus::DefaultedDecodeError);
  assert(loaded.codec_status == output::OutputPersistenceStatus::ChecksumMismatch);

  assert(store.save(snapshotWithCommand()) == output::OutputPersistenceStoreStatus::Ok);
  backend.read_status = output::OutputPersistenceBackendStatus::Ok;
  backend.stored_size = output::kOutputPersistenceEncodedSize - 1U;
  loaded = store.load();
  assertSafeFallback(loaded, output::OutputPersistenceStoreStatus::DefaultedDecodeError);
  assert(loaded.codec_status == output::OutputPersistenceStatus::InvalidLength);
}

void testInvalidSnapshotNeverWrites() {
  FakeBackend backend;
  output::OutputPersistenceStore store(backend, safePolicy());
  auto snapshot = snapshotWithCommand();
  snapshot.commands[0].endpoint = output::kInvalidOutputEndpoint;
  assert(store.save(snapshot) == output::OutputPersistenceStoreStatus::InvalidSnapshot);
  assert(backend.write_count == 0U);
}

void testWriteFailureSurfacesWithoutSuccess() {
  FakeBackend backend;
  backend.write_status = output::OutputPersistenceBackendStatus::WriteFailed;
  output::OutputPersistenceStore store(backend, safePolicy());
  assert(store.save(snapshotWithCommand()) == output::OutputPersistenceStoreStatus::BackendWriteFailed);
  assert(backend.write_count == 1U);
}

void testInvalidSafeDefaultsFailClosed() {
  FakeBackend backend;
  output::OutputPolicyConfig invalid{};
  output::OutputPersistenceStore store(backend, invalid);
  assert(!store.valid());
  const auto loaded = store.load();
  assert(loaded.status == output::OutputPersistenceStoreStatus::InvalidSafeDefaults);
  assert(!loaded.used_safe_defaults);
  assert(store.save(snapshotWithCommand()) == output::OutputPersistenceStoreStatus::InvalidSafeDefaults);
}

} // namespace

int main() {
  testRoundTripThroughBackendInterface();
  testNotFoundDefaultsSafely();
  testBackendReadFailureDefaultsSafely();
  testCorruptAndTruncatedPayloadsDefaultSafely();
  testInvalidSnapshotNeverWrites();
  testWriteFailureSurfacesWithoutSuccess();
  testInvalidSafeDefaultsFailClosed();
  return 0;
}
''')

replace_once('src/CMakeLists.txt',
'''    "climate/output/OutputPersistenceSchema.cpp"\n    "climate/output/OutputSupervisorLifecycle.cpp"''',
'''    "climate/output/OutputPersistenceSchema.cpp"\n    "climate/output/OutputPersistenceStore.cpp"\n    "climate/output/OutputNvsBackend.cpp"\n    "climate/output/OutputSupervisorLifecycle.cpp"''')

replace_once('test/host/CMakeLists.txt',
'''target_compile_options(output_persistence_schema_tests PRIVATE -Wall -Wextra -Wpedantic)\n\nadd_executable(\n  output_supervisor_lifecycle_tests''',
'''target_compile_options(output_persistence_schema_tests PRIVATE -Wall -Wextra -Wpedantic)\n\nadd_executable(\n  output_persistence_store_tests\n  "${PROJECT_ROOT}/test/test_output_persistence_store/test_main.cpp"\n  "${PROJECT_ROOT}/src/climate/output/OutputPersistenceStore.cpp"\n  "${PROJECT_ROOT}/src/climate/output/OutputPersistenceSchema.cpp"\n  "${PROJECT_ROOT}/src/climate/output/OutputPolicyConfig.cpp"\n)\ntarget_include_directories(output_persistence_store_tests PRIVATE "${PROJECT_ROOT}/src")\ntarget_compile_features(output_persistence_store_tests PRIVATE cxx_std_17)\ntarget_compile_options(output_persistence_store_tests PRIVATE -Wall -Wextra -Wpedantic)\n\nadd_executable(\n  output_supervisor_lifecycle_tests''')

replace_once('test/host/CMakeLists.txt',
'''add_test(NAME output_persistence_schema_tests COMMAND output_persistence_schema_tests)\nadd_test(NAME output_supervisor_lifecycle_tests COMMAND output_supervisor_lifecycle_tests)''',
'''add_test(NAME output_persistence_schema_tests COMMAND output_persistence_schema_tests)\nadd_test(NAME output_persistence_store_tests COMMAND output_persistence_store_tests)\nadd_test(NAME output_supervisor_lifecycle_tests COMMAND output_supervisor_lifecycle_tests)''')

print('A9_2_EDIT_PASS')
