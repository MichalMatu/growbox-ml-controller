#include "climate/output/OutputPersistenceStore.h"

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
