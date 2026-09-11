#pragma once

#include "climate/output/OutputExecution.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace growbox::app::output {

struct PhysicalObservation {
  PhysicalOutputState state = PhysicalOutputState::Unknown;
  bool has_independent_feedback = false;
  std::uint64_t observed_ms = 0U;
  std::uint64_t sequence = 0U;
};

struct OutputStateEntry {
  OutputEndpointId endpoint = kInvalidOutputEndpoint;
  bool configured = false;

  bool has_desired = false;
  OutputCommand desired{};

  bool has_resolved = false;
  OutputCommand resolved{};

  bool has_attempt = false;
  OutputCommand last_attempt{};
  std::uint64_t last_attempt_ms = 0U;
  TxResult last_transport{};

  bool has_successful_command = false;
  OutputCommand last_successful_command{};
  std::uint64_t last_successful_ms = 0U;

  PhysicalObservation physical{};
};

class OutputStateStore final {
public:
  bool configure(const std::array<OutputEndpointId, kOutputEndpointCapacity>& endpoints,
                 std::size_t count) noexcept;
  void resetRuntimeTruth() noexcept;

  bool valid() const noexcept {
    return valid_;
  }
  std::size_t configuredCount() const noexcept {
    return configured_count_;
  }

  const OutputStateEntry* find(OutputEndpointId endpoint) const noexcept;

  bool recordDesired(const OutputCommand& command) noexcept;
  bool recordResolved(const OutputCommand& command) noexcept;
  bool recordAttempt(const OutputCommand& command, std::uint64_t attempted_ms,
                     TxResult result) noexcept;
  bool restoreLastSuccessfulCommand(OutputEndpointId endpoint, BinaryOutputState state) noexcept;
  bool recordPhysicalObservation(OutputEndpointId endpoint, PhysicalOutputState state,
                                 std::uint64_t observed_ms, std::uint64_t sequence = 0U) noexcept;
  bool clearPhysicalObservation(OutputEndpointId endpoint) noexcept;

private:
  static bool commandStateValid(const OutputCommand& command) noexcept;
  OutputStateEntry* findMutable(OutputEndpointId endpoint) noexcept;
  void clearAll() noexcept;

  std::array<OutputStateEntry, kOutputEndpointCapacity> entries_{};
  std::size_t configured_count_{0U};
  bool valid_{false};
};

} // namespace growbox::app::output
