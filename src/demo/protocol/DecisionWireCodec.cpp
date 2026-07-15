#include "DecisionWireCodec.h"

#include "EnvironmentSchema.h"
#include "JsonLineWriter.h"
#include "ModelRuntime.h"
#include "SafetySupervisor.h"
#include "ScenarioWireCodec.h"

#include <cJSON.h>
#include <esp_heap_caps.h>

#include <array>

namespace growbox {
namespace demo {
namespace wire {
namespace {

using control::ControllerStatus;
using control::ModelStatus;
using control::SafetyReason;
using control::SafetySupervisor;

const char* controllerStatusCode(ControllerStatus status) noexcept {
  switch (status) {
  case ControllerStatus::Ok:
    return "ok";
  case ControllerStatus::EncoderError:
    return "encoder_error";
  case ControllerStatus::ModelError:
    return "model_error";
  }
  return "unknown";
}

const char* modelStatusCode(ModelStatus status) noexcept {
  switch (status) {
  case ModelStatus::Ok:
    return "ok";
  case ModelStatus::SchemaMismatch:
    return "schema_mismatch";
  case ModelStatus::ShapeMismatch:
    return "shape_mismatch";
  case ModelStatus::NonFiniteInput:
    return "non_finite_input";
  case ModelStatus::InferenceFailure:
    return "inference_failure";
  case ModelStatus::NonFiniteOutput:
    return "non_finite_output";
  }
  return "unknown";
}

const char* primarySafetyReason(std::uint32_t mask) noexcept {
  constexpr std::array<SafetyReason, 15> reasons{{
      SafetyReason::NonFiniteInput,
      SafetyReason::ModelFailure,
      SafetyReason::SchemaMismatch,
      SafetyReason::NonFiniteModelOutput,
      SafetyReason::OutputClamped,
      SafetyReason::TemperatureUnavailable,
      SafetyReason::ActuatorUnavailable,
      SafetyReason::OverTemperature,
      SafetyReason::TemperatureAlarmFan,
      SafetyReason::PumpPulseLimited,
      SafetyReason::PumpMinimumInterval,
      SafetyReason::BinaryThreshold,
      SafetyReason::BinaryMinimumOn,
      SafetyReason::BinaryMinimumOff,
      SafetyReason::InvalidCapability,
  }};
  for (const SafetyReason reason : reasons) {
    if ((mask & control::reasonBit(reason)) != 0U) {
      return SafetySupervisor::reasonCode(reason);
    }
  }
  return SafetySupervisor::reasonCode(SafetyReason::None);
}

} // namespace

void emitDecision(const DecisionEmitRequest& request) noexcept {
  if (request.input == nullptr || request.output == nullptr) {
    return;
  }
  const auto& input = *request.input;
  const auto& output = *request.output;
  const auto& actuators = input.actuators;

  cJSON* document = cJSON_CreateObject();
  if (document == nullptr) {
    return;
  }

  cJSON_AddStringToObject(document, "type", "decision");
  cJSON_AddNumberToObject(document, "schema_version", control::schema::kSchemaVersion);
  cJSON_AddStringToObject(document, "schema_hash", control::schema::kSchemaHash);
  cJSON_AddStringToObject(document, "model_version", control::ModelRuntime::modelVersion());
  cJSON_AddNumberToObject(document, "step", request.step);
  cJSON_AddNumberToObject(document, "simulated_time_s", input.monotonic_time_ms / 1000U);

  addDecisionContext(document, input);

  const float raw_heater = actuators.heater.available ? output.raw.heater : 0.0f;
  const float raw_fan = actuators.fan.available ? output.raw.fan : 0.0f;
  const float raw_humidifier = actuators.humidifier.available ? output.raw.humidifier : 0.0f;
  const float raw_irrigation = actuators.irrigation_pump.available ? output.raw.irrigation : 0.0f;

  cJSON* raw = cJSON_AddObjectToObject(document, "raw_output");
  cJSON_AddNumberToObject(raw, "heater", raw_heater);
  cJSON_AddNumberToObject(raw, "fan", raw_fan);
  cJSON_AddNumberToObject(raw, "humidifier", raw_humidifier);
  cJSON_AddNumberToObject(raw, "irrigation", raw_irrigation);

  cJSON* safe = cJSON_AddObjectToObject(document, "safe_output");
  cJSON_AddNumberToObject(safe, "heater", output.safe.heater);
  cJSON_AddNumberToObject(safe, "fan", output.safe.fan);
  cJSON_AddNumberToObject(safe, "humidifier", output.safe.humidifier);
  cJSON_AddNumberToObject(safe, "irrigation", output.safe.irrigation);
  cJSON_AddNumberToObject(safe, "irrigation_pulse_s", output.safe.irrigation_pulse_s);

  cJSON* diagnostics = cJSON_AddObjectToObject(document, "diagnostics");
  cJSON_AddStringToObject(diagnostics, "controller_status",
                          controllerStatusCode(request.controller_status));
  cJSON_AddStringToObject(diagnostics, "inference_status",
                          modelStatusCode(output.diagnostics.model_status));
  cJSON_AddNumberToObject(diagnostics, "inference_us", output.diagnostics.inference_us);
  cJSON_AddBoolToObject(diagnostics, "safety_modified", output.diagnostics.safety.modified);
  cJSON_AddStringToObject(diagnostics, "safety_reason",
                          primarySafetyReason(output.diagnostics.safety.reason_mask));
  cJSON_AddNumberToObject(diagnostics, "safety_reason_mask", output.diagnostics.safety.reason_mask);
  cJSON* output_reasons = cJSON_AddObjectToObject(diagnostics, "output_reason_masks");
  cJSON_AddNumberToObject(output_reasons, "heater",
                          output.diagnostics.safety.output_reason_masks[0]);
  cJSON_AddNumberToObject(output_reasons, "fan", output.diagnostics.safety.output_reason_masks[1]);
  cJSON_AddNumberToObject(output_reasons, "humidifier",
                          output.diagnostics.safety.output_reason_masks[2]);
  cJSON_AddNumberToObject(output_reasons, "irrigation",
                          output.diagnostics.safety.output_reason_masks[3]);
  cJSON_AddNumberToObject(diagnostics, "free_heap", heap_caps_get_free_size(MALLOC_CAP_8BIT));
  cJSON_AddNumberToObject(diagnostics, "free_psram", heap_caps_get_free_size(MALLOC_CAP_SPIRAM));

  emitJsonDocument(document);
}

} // namespace wire
} // namespace demo
} // namespace growbox
