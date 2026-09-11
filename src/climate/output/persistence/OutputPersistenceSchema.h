#pragma once

#include "climate/output/OutputPolicyConfig.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace growbox::app::output {

inline constexpr std::uint16_t kOutputPersistenceSchemaVersion = 1U;
inline constexpr std::uint32_t kOutputPersistenceMagic = 0x31504F47U; // "GOP1" little-endian.
inline constexpr std::size_t kOutputPersistenceHeaderSize = 12U;
inline constexpr std::size_t kOutputPersistenceLifecycleActionSize = 8U;
inline constexpr std::size_t kOutputPersistenceEndpointPolicySize =
    3U + (kOutputLifecycleEventCount * kOutputPersistenceLifecycleActionSize);
inline constexpr std::size_t kOutputPersistencePolicySize =
    4U + (kOutputEndpointCapacity * kOutputPersistenceEndpointPolicySize);
inline constexpr std::size_t kOutputPersistenceCommandEntrySize = 4U;
inline constexpr std::size_t kOutputPersistenceCommandStateSize =
    1U + (kOutputEndpointCapacity * kOutputPersistenceCommandEntrySize);
inline constexpr std::size_t kOutputPersistenceEncodedSize = kOutputPersistenceHeaderSize +
                                                             kOutputPersistencePolicySize +
                                                             kOutputPersistenceCommandStateSize;

static_assert(kOutputPersistenceEncodedSize == 134U,
              "Output persistence wire size must remain explicitly bounded");

struct DurableOutputCommandState {
  OutputEndpointId endpoint = kInvalidOutputEndpoint;
  bool has_last_successful_command = false;
  BinaryOutputState state = BinaryOutputState::Off;
};

struct OutputPersistenceSnapshot {
  OutputPolicyConfig policy{};
  std::array<DurableOutputCommandState, kOutputEndpointCapacity> commands{};
  std::uint8_t command_count = 0U;
};

struct OutputPersistenceBlob {
  std::array<std::uint8_t, kOutputPersistenceEncodedSize> bytes{};
};

enum class OutputPersistenceStatus : std::uint8_t {
  Ok = 0U,
  InvalidSafeDefaults,
  InvalidSnapshot,
  InvalidLength,
  InvalidMagic,
  UnsupportedVersion,
  ChecksumMismatch,
  InvalidPolicy,
  InvalidCommandState,
};

struct OutputPersistenceDecodeResult {
  OutputPersistenceStatus status = OutputPersistenceStatus::InvalidLength;
  bool used_safe_defaults = false;
  OutputPersistenceSnapshot snapshot{};
};

OutputPersistenceStatus
validateOutputPersistenceSnapshot(const OutputPersistenceSnapshot& snapshot) noexcept;

bool makeSafeOutputPersistenceSnapshot(const OutputPolicyConfig& safe_defaults,
                                       OutputPersistenceSnapshot& snapshot) noexcept;

OutputPersistenceStatus encodeOutputPersistence(const OutputPersistenceSnapshot& snapshot,
                                                OutputPersistenceBlob& blob) noexcept;

OutputPersistenceDecodeResult
decodeOutputPersistence(const std::uint8_t* data, std::size_t size,
                        const OutputPolicyConfig& safe_defaults) noexcept;

} // namespace growbox::app::output
