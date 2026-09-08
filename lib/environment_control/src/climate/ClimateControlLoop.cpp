#include "ClimateControlLoop.h"

#include <cmath>

namespace growbox::climate {
namespace {

float boundedPreviousLevel(float value) noexcept {
  if (!std::isfinite(value)) {
    return 0.0F;
  }
  if (value < 0.0F) {
    return 0.0F;
  }
  return value > 1.0F ? 1.0F : value;
}

} // namespace

ClimateControlLoop::ClimateControlLoop(ClimateRuntimeController& runtime,
                                       ClimateInputSource& input_source,
                                       ClimateActuatorSink& actuator_sink) noexcept
    : runtime_(runtime), input_source_(input_source), actuator_sink_(actuator_sink) {}

PreviousClimateActions
ClimateControlLoop::previousFromRequest(const ClimatePolicyRequest& request) noexcept {
  return PreviousClimateActions{request.heater,     request.cooler,       request.exhaust_fan,
                                request.humidifier, request.dehumidifier, request.co2_doser};
}

void ClimateControlLoop::setPreviousExecutionFeedback(
    const ClimateExecutionProjection& feedback) noexcept {
  external_previous_execution_ = feedback;
  has_external_previous_execution_ = true;
}

void ClimateControlLoop::clearPreviousExecutionFeedback() noexcept {
  external_previous_execution_ = {};
  has_external_previous_execution_ = false;
}

PreviousClimateActions ClimateControlLoop::previousForInput() const noexcept {
  PreviousClimateActions previous = previous_applied_;
  if (!has_external_previous_execution_) {
    return previous;
  }

  const auto& feedback = external_previous_execution_;
  if (feedback.known(ClimateExecutionKnownHeater)) {
    previous.heater = boundedPreviousLevel(feedback.executed.heater);
  }
  if (feedback.known(ClimateExecutionKnownCooler)) {
    previous.cooler = boundedPreviousLevel(feedback.executed.cooler);
  }
  if (feedback.known(ClimateExecutionKnownExhaustFan)) {
    previous.exhaust_fan = boundedPreviousLevel(feedback.executed.exhaust_fan);
  }
  if (feedback.known(ClimateExecutionKnownHumidifier)) {
    previous.humidifier = boundedPreviousLevel(feedback.executed.humidifier);
  }
  if (feedback.known(ClimateExecutionKnownDehumidifier)) {
    previous.dehumidifier = boundedPreviousLevel(feedback.executed.dehumidifier);
  }
  if (feedback.known(ClimateExecutionKnownCo2Doser)) {
    previous.co2_doser = boundedPreviousLevel(feedback.executed.co2_doser);
  }
  return previous;
}

bool ClimateControlLoop::isOff(const ClimatePolicyRequest& request) noexcept {
  return request.heater == 0.0F && request.cooler == 0.0F && request.exhaust_fan == 0.0F &&
         request.humidifier == 0.0F && request.dehumidifier == 0.0F && request.co2_doser == 0.0F;
}

ClimateLoopResult ClimateControlLoop::tick(std::uint64_t monotonic_ms,
                                           ClimateRuntimeDecision& decision) noexcept {
  ClimateLoopResult result{};

  if (actuator_fault_latched_) {
    decision = {};
    result.io_status = ClimateLoopIoStatus::ActuatorFaultLatched;
    result.fail_safe_attempted = true;
    result.fail_safe_applied = actuator_sink_.applyFailSafeOff(monotonic_ms);
    result.command_applied = result.fail_safe_applied;
    return result;
  }

  ClimateControllerInput input{};
  result.input_sampled = input_source_.sample(monotonic_ms, input);
  if (!result.input_sampled) {
    input = {};
  }
  input.previous = previousForInput();

  result.runtime_status = runtime_.step(input, monotonic_ms, decision);
  ClimatePolicyRequest confirmed_applied{};
  result.command_applied =
      actuator_sink_.applyAndReport(decision.applied, monotonic_ms, confirmed_applied);
  if (result.command_applied) {
    ClimateExecutionProjection execution{};
    execution.executed = confirmed_applied;
    execution.known_mask = ClimateExecutionKnownAll;
    runtime_.reconcileExecution(execution, input.capabilities, decision);
    previous_applied_ = previousFromRequest(decision.applied);
    result.io_status =
        result.input_sampled ? ClimateLoopIoStatus::Ok : ClimateLoopIoStatus::InputUnavailable;
    return result;
  }

  result.io_status = ClimateLoopIoStatus::ActuatorApplyFailed;
  result.fail_safe_attempted = true;
  result.fail_safe_applied = actuator_sink_.applyFailSafeOff(monotonic_ms);

  // The runtime advanced its effective-action estimator before the sink
  // acknowledgement. Reset it after any rejected command so an unconfirmed
  // actuator state never becomes future ML context.
  runtime_.reset();
  previous_applied_ = {};
  clearPreviousExecutionFeedback();
  if (!result.fail_safe_applied) {
    actuator_fault_latched_ = true;
  }
  return result;
}

void ClimateControlLoop::reset() noexcept {
  runtime_.reset();
  previous_applied_ = {};
  clearPreviousExecutionFeedback();
  actuator_fault_latched_ = false;
}

} // namespace growbox::climate
