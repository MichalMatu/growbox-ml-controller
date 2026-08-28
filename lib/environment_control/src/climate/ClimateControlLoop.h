#pragma once

#include "ClimateRuntimeController.h"

#include <cstdint>

namespace growbox::climate {

enum class ClimateLoopIoStatus : std::uint8_t {
  Ok = 0U,
  InputUnavailable,
  ActuatorApplyFailed,
  ActuatorFaultLatched,
};

class ClimateInputSource {
public:
  virtual ~ClimateInputSource() = default;
  virtual bool sample(std::uint64_t monotonic_ms, ClimateControllerInput& input) noexcept = 0;
};

class ClimateActuatorSink {
public:
  virtual ~ClimateActuatorSink() = default;
  virtual bool apply(const ClimatePolicyRequest& request, std::uint64_t monotonic_ms) noexcept = 0;
};

struct ClimateLoopResult {
  ClimateLoopIoStatus io_status = ClimateLoopIoStatus::Ok;
  ClimateRuntimeStatus runtime_status = ClimateRuntimeStatus::Ok;
  bool input_sampled = false;
  bool command_applied = false;
  bool fail_safe_attempted = false;
  bool fail_safe_applied = false;
};

class ClimateControlLoop {
public:
  ClimateControlLoop(ClimateRuntimeController& runtime, ClimateInputSource& input_source,
                     ClimateActuatorSink& actuator_sink) noexcept;

  ClimateLoopResult tick(std::uint64_t monotonic_ms, ClimateRuntimeDecision& decision) noexcept;
  void reset() noexcept;

  bool actuatorFaultLatched() const noexcept {
    return actuator_fault_latched_;
  }
  const PreviousClimateActions& previousApplied() const noexcept {
    return previous_applied_;
  }

private:
  static PreviousClimateActions previousFromRequest(const ClimatePolicyRequest& request) noexcept;
  static bool isOff(const ClimatePolicyRequest& request) noexcept;

  ClimateRuntimeController& runtime_;
  ClimateInputSource& input_source_;
  ClimateActuatorSink& actuator_sink_;
  PreviousClimateActions previous_applied_{};
  bool actuator_fault_latched_ = false;
};

} // namespace growbox::climate
