#include "EnvironmentController.h"

namespace growbox {
namespace control {
namespace {

SafetyReason modelFailureReason(ModelStatus status) noexcept {
  switch (status) {
  case ModelStatus::SchemaMismatch:
  case ModelStatus::ShapeMismatch:
    return SafetyReason::SchemaMismatch;
  case ModelStatus::NonFiniteOutput:
    return SafetyReason::NonFiniteModelOutput;
  case ModelStatus::Ok:
    return SafetyReason::None;
  case ModelStatus::NonFiniteInput:
  case ModelStatus::InferenceFailure:
    return SafetyReason::ModelFailure;
  }
  return SafetyReason::ModelFailure;
}

} // namespace

ControllerStatus EnvironmentController::process(const ControllerInput& input,
                                                ControllerOutput& output) noexcept {
  output = ControllerOutput{};
  FeatureVector features{};
  output.diagnostics.encoder_status =
      FeatureEncoder::encode(input, features, output.diagnostics.encoder);
  if (output.diagnostics.encoder_status != EncoderStatus::Ok) {
    output.diagnostics.model_status = ModelStatus::NonFiniteInput;
    safety_.apply(input, output.raw, SafetyReason::NonFiniteInput, output.safe,
                  output.diagnostics.safety);
    return ControllerStatus::EncoderError;
  }

  output.diagnostics.model_status = model_.infer(features, output.raw);
  if (output.diagnostics.model_status != ModelStatus::Ok) {
    safety_.apply(input, output.raw, modelFailureReason(output.diagnostics.model_status),
                  output.safe, output.diagnostics.safety);
    return ControllerStatus::ModelError;
  }

  safety_.apply(input, output.raw, SafetyReason::None, output.safe, output.diagnostics.safety);
  return ControllerStatus::Ok;
}

void EnvironmentController::resetSafetyState() noexcept {
  safety_.reset();
}

const ModelRuntime& EnvironmentController::modelRuntime() const noexcept {
  return model_;
}

} // namespace control
} // namespace growbox
