#include "climate/output/OutputPersistenceSchema.h"

#include <cstddef>
#include <cstdint>

namespace growbox::app::output {
namespace {

class Writer final {
public:
  explicit Writer(OutputPersistenceBlob& blob) noexcept : blob_(blob) {
    blob_.bytes.fill(0U);
  }

  bool putU8(std::uint8_t value) noexcept {
    if (offset_ >= blob_.bytes.size()) {
      return false;
    }
    blob_.bytes[offset_++] = value;
    return true;
  }

  bool putU16(std::uint16_t value) noexcept {
    return putU8(static_cast<std::uint8_t>(value & 0xFFU)) &&
           putU8(static_cast<std::uint8_t>((value >> 8U) & 0xFFU));
  }

  bool putU32(std::uint32_t value) noexcept {
    return putU8(static_cast<std::uint8_t>(value & 0xFFU)) &&
           putU8(static_cast<std::uint8_t>((value >> 8U) & 0xFFU)) &&
           putU8(static_cast<std::uint8_t>((value >> 16U) & 0xFFU)) &&
           putU8(static_cast<std::uint8_t>((value >> 24U) & 0xFFU));
  }

  std::size_t offset() const noexcept {
    return offset_;
  }

private:
  OutputPersistenceBlob& blob_;
  std::size_t offset_{0U};
};

class Reader final {
public:
  Reader(const std::uint8_t* data, std::size_t size) noexcept : data_(data), size_(size) {}

  bool getU8(std::uint8_t& value) noexcept {
    if (data_ == nullptr || offset_ >= size_) {
      return false;
    }
    value = data_[offset_++];
    return true;
  }

  bool getU16(std::uint16_t& value) noexcept {
    std::uint8_t low = 0U;
    std::uint8_t high = 0U;
    if (!getU8(low) || !getU8(high)) {
      return false;
    }
    value = static_cast<std::uint16_t>(low) | (static_cast<std::uint16_t>(high) << 8U);
    return true;
  }

  bool getU32(std::uint32_t& value) noexcept {
    std::uint8_t b0 = 0U;
    std::uint8_t b1 = 0U;
    std::uint8_t b2 = 0U;
    std::uint8_t b3 = 0U;
    if (!getU8(b0) || !getU8(b1) || !getU8(b2) || !getU8(b3)) {
      return false;
    }
    value = static_cast<std::uint32_t>(b0) | (static_cast<std::uint32_t>(b1) << 8U) |
            (static_cast<std::uint32_t>(b2) << 16U) | (static_cast<std::uint32_t>(b3) << 24U);
    return true;
  }

  std::size_t offset() const noexcept {
    return offset_;
  }

private:
  const std::uint8_t* data_{nullptr};
  std::size_t size_{0U};
  std::size_t offset_{0U};
};

bool validBinaryState(BinaryOutputState state) noexcept {
  return state == BinaryOutputState::Off || state == BinaryOutputState::On;
}

std::uint32_t crc32(const std::uint8_t* data, std::size_t size) noexcept {
  std::uint32_t crc = 0xFFFFFFFFU;
  for (std::size_t index = 0U; index < size; ++index) {
    crc ^= static_cast<std::uint32_t>(data[index]);
    for (unsigned bit = 0U; bit < 8U; ++bit) {
      const std::uint32_t mask = 0U - (crc & 1U);
      crc = (crc >> 1U) ^ (0xEDB88320U & mask);
    }
  }
  return ~crc;
}

void writeU32At(OutputPersistenceBlob& blob, std::size_t offset, std::uint32_t value) noexcept {
  blob.bytes[offset + 0U] = static_cast<std::uint8_t>(value & 0xFFU);
  blob.bytes[offset + 1U] = static_cast<std::uint8_t>((value >> 8U) & 0xFFU);
  blob.bytes[offset + 2U] = static_cast<std::uint8_t>((value >> 16U) & 0xFFU);
  blob.bytes[offset + 3U] = static_cast<std::uint8_t>((value >> 24U) & 0xFFU);
}

bool policyContainsEndpoint(const OutputPolicyConfig& policy, OutputEndpointId endpoint) noexcept {
  return findOutputPolicyEndpoint(policy, endpoint) != nullptr;
}

OutputPersistenceDecodeResult fallbackResult(OutputPersistenceStatus status,
                                             const OutputPolicyConfig& safe_defaults) noexcept {
  OutputPersistenceDecodeResult result{};
  result.status = status;
  result.used_safe_defaults = makeSafeOutputPersistenceSnapshot(safe_defaults, result.snapshot);
  if (!result.used_safe_defaults) {
    result.status = OutputPersistenceStatus::InvalidSafeDefaults;
    result.snapshot = {};
  }
  return result;
}

} // namespace

OutputPersistenceStatus
validateOutputPersistenceSnapshot(const OutputPersistenceSnapshot& snapshot) noexcept {
  if (validateOutputPolicyConfig(snapshot.policy) != OutputPolicyConfigStatus::Ok) {
    return OutputPersistenceStatus::InvalidPolicy;
  }
  if (snapshot.command_count != snapshot.policy.count ||
      snapshot.command_count != kOutputEndpointCapacity) {
    return OutputPersistenceStatus::InvalidCommandState;
  }

  for (std::size_t index = 0U; index < snapshot.command_count; ++index) {
    const auto& command = snapshot.commands[index];
    if (!isValidOutputEndpoint(command.endpoint) || !validBinaryState(command.state) ||
        !policyContainsEndpoint(snapshot.policy, command.endpoint)) {
      return OutputPersistenceStatus::InvalidCommandState;
    }
    for (std::size_t previous = 0U; previous < index; ++previous) {
      if (snapshot.commands[previous].endpoint == command.endpoint) {
        return OutputPersistenceStatus::InvalidCommandState;
      }
    }
  }

  return OutputPersistenceStatus::Ok;
}

bool makeSafeOutputPersistenceSnapshot(const OutputPolicyConfig& safe_defaults,
                                       OutputPersistenceSnapshot& snapshot) noexcept {
  snapshot = {};
  if (validateOutputPolicyConfig(safe_defaults) != OutputPolicyConfigStatus::Ok) {
    return false;
  }

  snapshot.policy = safe_defaults;
  snapshot.command_count = safe_defaults.count;
  for (std::size_t index = 0U; index < safe_defaults.count; ++index) {
    snapshot.commands[index].endpoint = safe_defaults.endpoints[index].endpoint;
    snapshot.commands[index].has_last_successful_command = false;
    snapshot.commands[index].state = BinaryOutputState::Off;
  }
  return true;
}

OutputPersistenceStatus encodeOutputPersistence(const OutputPersistenceSnapshot& snapshot,
                                                OutputPersistenceBlob& blob) noexcept {
  const OutputPersistenceStatus validation = validateOutputPersistenceSnapshot(snapshot);
  if (validation != OutputPersistenceStatus::Ok) {
    blob.bytes.fill(0U);
    return validation;
  }

  Writer writer(blob);
  if (!writer.putU32(kOutputPersistenceMagic) || !writer.putU16(kOutputPersistenceSchemaVersion) ||
      !writer.putU16(static_cast<std::uint16_t>(kOutputPersistenceEncodedSize)) ||
      !writer.putU32(0U) || !writer.putU16(snapshot.policy.version) ||
      !writer.putU8(snapshot.policy.count) ||
      !writer.putU8(snapshot.policy.max_transition_failures)) {
    blob.bytes.fill(0U);
    return OutputPersistenceStatus::InvalidSnapshot;
  }

  for (std::size_t index = 0U; index < kOutputEndpointCapacity; ++index) {
    const auto& endpoint = snapshot.policy.endpoints[index];
    if (!writer.putU16(endpoint.endpoint) ||
        !writer.putU8(static_cast<std::uint8_t>(endpoint.role))) {
      blob.bytes.fill(0U);
      return OutputPersistenceStatus::InvalidSnapshot;
    }
    for (const auto& action : endpoint.lifecycle) {
      if (!writer.putU8(static_cast<std::uint8_t>(action.action)) || !writer.putU8(action.order) ||
          !writer.putU32(action.delay_ms) || !writer.putU8(action.retransmit ? 1U : 0U) ||
          !writer.putU8(action.max_retries)) {
        blob.bytes.fill(0U);
        return OutputPersistenceStatus::InvalidSnapshot;
      }
    }
  }

  if (!writer.putU8(snapshot.command_count)) {
    blob.bytes.fill(0U);
    return OutputPersistenceStatus::InvalidSnapshot;
  }
  for (std::size_t index = 0U; index < kOutputEndpointCapacity; ++index) {
    const auto& command = snapshot.commands[index];
    if (!writer.putU16(command.endpoint) ||
        !writer.putU8(command.has_last_successful_command ? 1U : 0U) ||
        !writer.putU8(static_cast<std::uint8_t>(command.state))) {
      blob.bytes.fill(0U);
      return OutputPersistenceStatus::InvalidSnapshot;
    }
  }

  if (writer.offset() != kOutputPersistenceEncodedSize) {
    blob.bytes.fill(0U);
    return OutputPersistenceStatus::InvalidSnapshot;
  }

  const std::uint32_t checksum = crc32(blob.bytes.data() + kOutputPersistenceHeaderSize,
                                       blob.bytes.size() - kOutputPersistenceHeaderSize);
  writeU32At(blob, 8U, checksum);
  return OutputPersistenceStatus::Ok;
}

OutputPersistenceDecodeResult
decodeOutputPersistence(const std::uint8_t* data, std::size_t size,
                        const OutputPolicyConfig& safe_defaults) noexcept {
  if (validateOutputPolicyConfig(safe_defaults) != OutputPolicyConfigStatus::Ok) {
    return fallbackResult(OutputPersistenceStatus::InvalidSafeDefaults, safe_defaults);
  }
  if (data == nullptr || size != kOutputPersistenceEncodedSize) {
    return fallbackResult(OutputPersistenceStatus::InvalidLength, safe_defaults);
  }

  Reader reader(data, size);
  std::uint32_t magic = 0U;
  std::uint16_t schema_version = 0U;
  std::uint16_t encoded_size = 0U;
  std::uint32_t stored_crc = 0U;
  if (!reader.getU32(magic) || !reader.getU16(schema_version) || !reader.getU16(encoded_size) ||
      !reader.getU32(stored_crc)) {
    return fallbackResult(OutputPersistenceStatus::InvalidLength, safe_defaults);
  }
  if (magic != kOutputPersistenceMagic) {
    return fallbackResult(OutputPersistenceStatus::InvalidMagic, safe_defaults);
  }
  if (schema_version != kOutputPersistenceSchemaVersion) {
    return fallbackResult(OutputPersistenceStatus::UnsupportedVersion, safe_defaults);
  }
  if (encoded_size != kOutputPersistenceEncodedSize) {
    return fallbackResult(OutputPersistenceStatus::InvalidLength, safe_defaults);
  }

  const std::uint32_t actual_crc =
      crc32(data + kOutputPersistenceHeaderSize, size - kOutputPersistenceHeaderSize);
  if (stored_crc != actual_crc) {
    return fallbackResult(OutputPersistenceStatus::ChecksumMismatch, safe_defaults);
  }

  OutputPersistenceSnapshot decoded{};
  if (!reader.getU16(decoded.policy.version) || !reader.getU8(decoded.policy.count) ||
      !reader.getU8(decoded.policy.max_transition_failures)) {
    return fallbackResult(OutputPersistenceStatus::InvalidLength, safe_defaults);
  }

  for (std::size_t index = 0U; index < kOutputEndpointCapacity; ++index) {
    auto& endpoint = decoded.policy.endpoints[index];
    std::uint8_t role = 0U;
    if (!reader.getU16(endpoint.endpoint) || !reader.getU8(role)) {
      return fallbackResult(OutputPersistenceStatus::InvalidLength, safe_defaults);
    }
    endpoint.role = static_cast<OutputEndpointRole>(role);
    for (auto& action : endpoint.lifecycle) {
      std::uint8_t action_value = 0U;
      std::uint8_t retransmit = 0U;
      if (!reader.getU8(action_value) || !reader.getU8(action.order) ||
          !reader.getU32(action.delay_ms) || !reader.getU8(retransmit) ||
          !reader.getU8(action.max_retries)) {
        return fallbackResult(OutputPersistenceStatus::InvalidLength, safe_defaults);
      }
      action.action = static_cast<OutputPolicyAction>(action_value);
      if (retransmit > 1U) {
        return fallbackResult(OutputPersistenceStatus::InvalidPolicy, safe_defaults);
      }
      action.retransmit = retransmit != 0U;
    }
  }

  if (!reader.getU8(decoded.command_count)) {
    return fallbackResult(OutputPersistenceStatus::InvalidLength, safe_defaults);
  }
  for (std::size_t index = 0U; index < kOutputEndpointCapacity; ++index) {
    auto& command = decoded.commands[index];
    std::uint8_t has_command = 0U;
    std::uint8_t state = 0U;
    if (!reader.getU16(command.endpoint) || !reader.getU8(has_command) || !reader.getU8(state)) {
      return fallbackResult(OutputPersistenceStatus::InvalidLength, safe_defaults);
    }
    if (has_command > 1U) {
      return fallbackResult(OutputPersistenceStatus::InvalidCommandState, safe_defaults);
    }
    command.has_last_successful_command = has_command != 0U;
    command.state = static_cast<BinaryOutputState>(state);
  }

  if (reader.offset() != kOutputPersistenceEncodedSize) {
    return fallbackResult(OutputPersistenceStatus::InvalidLength, safe_defaults);
  }

  const OutputPersistenceStatus validation = validateOutputPersistenceSnapshot(decoded);
  if (validation != OutputPersistenceStatus::Ok) {
    return fallbackResult(validation, safe_defaults);
  }

  OutputPersistenceDecodeResult result{};
  result.status = OutputPersistenceStatus::Ok;
  result.used_safe_defaults = false;
  result.snapshot = decoded;
  return result;
}

} // namespace growbox::app::output
