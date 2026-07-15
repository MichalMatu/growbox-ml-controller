#include "DecisionWireCodec.h"

#include "EnvironmentTypes.h"
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
using control::schema::kOutputCount;
using control::schema::kOutputNames;
using control::schema::OutputIndex;

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
  constexpr std::array<SafetyReason, 16> reasons{{
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
      SafetyReason::Co2VentingFan,
  }};
  for (const SafetyReason reason : reasons) {
    if ((mask & control::reasonBit(reason)) != 0U) {
      return SafetySupervisor::reasonCode(reason);
    }
  }
  return SafetySupervisor::reasonCode(SafetyReason::None);
}

bool irrigationAvailable(const control::ControllerInput& input, std::size_t zone_index) noexcept {
  return zone_index < control::kMaxZones && input.zones[zone_index].available &&
         input.zones[zone_index].irrigation.available;
}

float maskedRawOutput(const control::ControllerInput& input, const control::RawModelDecision& raw,
                      OutputIndex output) noexcept {
  switch (output) {
  case OutputIndex::Heater:
    return input.actuators.heater.available ? raw.heater : 0.0f;
  case OutputIndex::Fan:
    return input.actuators.fan.available ? raw.fan : 0.0f;
  case OutputIndex::Humidifier:
    return input.actuators.humidifier.available ? raw.humidifier : 0.0f;
  case OutputIndex::Dehumidifier:
    return input.actuators.dehumidifier.available ? raw.dehumidifier : 0.0f;
  case OutputIndex::Cooler:
    return input.actuators.cooler.available ? raw.cooler : 0.0f;
  case OutputIndex::Co2Doser:
    return input.actuators.co2_doser.available ? raw.co2_doser : 0.0f;
  case OutputIndex::IrrigationZone1:
    return irrigationAvailable(input, 0U) ? raw.irrigation_zone_1 : 0.0f;
  case OutputIndex::IrrigationZone2:
    return irrigationAvailable(input, 1U) ? raw.irrigation_zone_2 : 0.0f;
  case OutputIndex::IrrigationZone3:
    return irrigationAvailable(input, 2U) ? raw.irrigation_zone_3 : 0.0f;
  case OutputIndex::IrrigationZone4:
    return irrigationAvailable(input, 3U) ? raw.irrigation_zone_4 : 0.0f;
  }
  return 0.0f;
}

void addOutputObject(cJSON* object, const char* name, float value) noexcept {
  if (object != nullptr) {
    cJSON_AddNumberToObject(object, name, value);
  }
}

} // namespace

void emitDecision(const DecisionEmitRequest& request) noexcept {
  if (request.input == nullptr || request.output == nullptr) {
    return;
  }
  const auto& input = *request.input;
  const auto& output = *request.output;

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

  cJSON* raw = cJSON_AddObjectToObject(document, "raw_output");
  cJSON* safe = cJSON_AddObjectToObject(document, "safe_output");
  for (std::size_t output_index = 0U; output_index < kOutputCount; ++output_index) {
    const auto output_slot = static_cast<OutputIndex>(output_index);
    const char* name = kOutputNames[output_index];
    addOutputObject(raw, name, maskedRawOutput(input, output.raw, output_slot));
    addOutputObject(safe, name, control::safeOutputValue(output.safe, output_slot));
  }

  cJSON* irrigation_pulse_s = cJSON_AddArrayToObject(safe, "irrigation_pulse_s");
  for (std::size_t zone_index = 0U; zone_index < control::kMaxZones; ++zone_index) {
    cJSON_AddItemToArray(irrigation_pulse_s,
                         cJSON_CreateNumber(output.safe.irrigation_pulse_s[zone_index]));
  }

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
  for (std::size_t output_index = 0U; output_index < kOutputCount; ++output_index) {
    cJSON_AddNumberToObject(output_reasons, kOutputNames[output_index],
                            output.diagnostics.safety.output_reason_masks[output_index]);
  }
  cJSON_AddNumberToObject(diagnostics, "free_heap", heap_caps_get_free_size(MALLOC_CAP_8BIT));
  cJSON_AddNumberToObject(diagnostics, "free_psram", heap_caps_get_free_size(MALLOC_CAP_SPIRAM));

  emitJsonDocument(document);
}

} // namespace wire
} // namespace demo
} // namespace growbox
