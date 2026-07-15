#include "SerialJsonProtocol.h"

#include "protocol/DecisionWireCodec.h"
#include "protocol/JsonLineWriter.h"
#include "protocol/ScenarioWireCodec.h"
#include "protocol/StatusWireCodec.h"

#include <cJSON.h>
#include <driver/usb_serial_jtag.h>

#include <cstring>

namespace growbox {
namespace demo {
namespace {

const char* readString(const cJSON* object, const char* key) noexcept {
  const cJSON* value =
      cJSON_IsObject(object) ? cJSON_GetObjectItemCaseSensitive(object, key) : nullptr;
  return cJSON_IsString(value) && value->valuestring != nullptr ? value->valuestring : nullptr;
}

}  // namespace

esp_err_t SerialJsonProtocol::begin() noexcept {
  if (!usb_serial_jtag_is_driver_installed()) {
    usb_serial_jtag_driver_config_t config = USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();
    config.tx_buffer_size = 4096U;
    config.rx_buffer_size = 4096U;
    const esp_err_t error = usb_serial_jtag_driver_install(&config);
    if (error != ESP_OK) {
      return error;
    }
  }

  std::uint8_t discard[128]{};
  while (usb_serial_jtag_read_bytes(discard, sizeof(discard), 0) > 0) {
  }
  return ESP_OK;
}

void SerialJsonProtocol::poll(DummyEnvironmentSimulator& simulator,
                              DemoRuntimeState& runtime) noexcept {
  std::uint8_t buffer[128]{};
  const int received = usb_serial_jtag_read_bytes(buffer, sizeof(buffer), 0);
  if (received <= 0) {
    return;
  }

  for (int index = 0; index < received; ++index) {
    const char character = static_cast<char>(buffer[index]);
    if (character == '\r') {
      continue;
    }
    if (character == '\n') {
      if (discarding_) {
        emitError("line_too_long", "input exceeds the bounded line buffer");
      } else if (length_ > 0U) {
        line_[length_] = '\0';
        processLine(simulator, runtime);
      }
      length_ = 0U;
      discarding_ = false;
      continue;
    }
    if (discarding_) {
      continue;
    }
    if (length_ >= kMaximumLineBytes) {
      discarding_ = true;
      length_ = 0U;
      continue;
    }
    line_[length_++] = character;
  }
}

void SerialJsonProtocol::processLine(DummyEnvironmentSimulator& simulator,
                                     DemoRuntimeState& runtime) noexcept {
  cJSON* root = cJSON_ParseWithLength(line_, length_);
  if (!cJSON_IsObject(root)) {
    cJSON_Delete(root);
    emitError("invalid_json", "input must be a valid JSON object");
    return;
  }

  const char* command = readString(root, "command");
  if (command == nullptr || command[0] == '\0') {
    cJSON_Delete(root);
    emitError("missing_command", "command must be a non-empty string");
    return;
  }

  if (std::strcmp(command, "status") == 0) {
    wire::emitLightStatus(simulator, runtime);
    cJSON_Delete(root);
    return;
  }
  if (std::strcmp(command, "get_scenario") == 0) {
    wire::emitScenarioSnapshot(simulator);
    cJSON_Delete(root);
    return;
  }
  if (std::strcmp(command, "reset") == 0) {
    simulator.reset(simulator.seed());
    runtime.step = 0U;
    runtime.step_requested = false;
    runtime.paused = true;
    runtime.controller_reset_requested = true;
    emitAck(command);
    cJSON_Delete(root);
    return;
  }
  if (std::strcmp(command, "seed") == 0) {
    std::uint32_t seed = 0U;
    if (!wire::parseSeedValue(root, seed)) {
      cJSON_Delete(root);
      emitError("invalid_seed", "value must be an unsigned integer");
      return;
    }
    simulator.setSeed(seed);
    emitAck(command);
    cJSON_Delete(root);
    return;
  }
  if (std::strcmp(command, "pause") == 0) {
    runtime.paused = true;
    emitAck(command);
    cJSON_Delete(root);
    return;
  }
  if (std::strcmp(command, "resume") == 0) {
    runtime.paused = false;
    emitAck(command);
    cJSON_Delete(root);
    return;
  }
  if (std::strcmp(command, "mode") == 0) {
    const char* value = readString(root, "value");
    if (value != nullptr && std::strcmp(value, "closed_loop") == 0) {
      runtime.mode = DemoMode::ClosedLoop;
    } else if (value != nullptr && std::strcmp(value, "replay") == 0) {
      runtime.mode = DemoMode::Replay;
      runtime.paused = true;
    } else {
      cJSON_Delete(root);
      emitError("invalid_mode", "value must be closed_loop or replay");
      return;
    }
    emitAck(command);
    cJSON_Delete(root);
    return;
  }
  if (std::strcmp(command, "target") == 0) {
    control::ControlTargets targets = simulator.input().targets;
    if (!wire::parseTargetPatch(root, targets)) {
      cJSON_Delete(root);
      emitError("invalid_target", "provide at least one finite target field");
      return;
    }
    simulator.setTargets(targets);
    emitAck(command);
    cJSON_Delete(root);
    return;
  }
  if (std::strcmp(command, "step") == 0) {
    control::SensorState sensors = simulator.input().sensors;
    control::SensorValidity validity = simulator.input().validity;
    control::ActuatorCapabilities actuators{};
    bool has_sensors = false;
    bool has_validity = false;
    bool has_actuators = false;
    if (!wire::parseStepOverrides(root, sensors, validity, actuators, has_sensors, has_validity,
                                  has_actuators)) {
      cJSON_Delete(root);
      emitError("invalid_step", "sensors, validity, or actuators are invalid");
      return;
    }
    if (has_sensors || has_validity) {
      if (!has_sensors || !has_validity) {
        cJSON_Delete(root);
        emitError("invalid_step", "sensors and validity must be complete");
        return;
      }
      simulator.setSensors(sensors, validity);
    }
    if (has_actuators) {
      simulator.setActuators(actuators);
      runtime.controller_reset_requested = true;
    }
    runtime.step_requested = true;
    cJSON_Delete(root);
    return;
  }
  if (std::strcmp(command, "load_scenario") == 0) {
    control::ControllerInput scenario{};
    std::uint32_t seed = 0U;
    if (!wire::parseLoadScenario(root, scenario, seed)) {
      cJSON_Delete(root);
      emitError("invalid_scenario", "scenario fields must be complete and finite");
      return;
    }
    simulator.load(scenario, seed);
    runtime.step = 0U;
    runtime.step_requested = false;
    runtime.paused = true;
    runtime.controller_reset_requested = true;
    emitAck(command);
    cJSON_Delete(root);
    return;
  }

  char unsupported[kMaximumLineBytes + 1U]{};
  std::strncpy(unsupported, command, kMaximumLineBytes);
  cJSON_Delete(root);
  emitError("unsupported_command", unsupported);
}

void SerialJsonProtocol::emitError(const char* code, const char* message) const noexcept {
  cJSON* document = cJSON_CreateObject();
  if (document == nullptr) {
    return;
  }
  cJSON_AddStringToObject(document, "type", "error");
  cJSON_AddNumberToObject(document, "schema_version", control::schema::kSchemaVersion);
  cJSON_AddStringToObject(document, "schema_hash", control::schema::kSchemaHash);
  cJSON_AddStringToObject(document, "code", code != nullptr ? code : "unknown_error");
  cJSON_AddStringToObject(document, "message", message != nullptr ? message : "");
  wire::emitJsonDocument(document);
}

void SerialJsonProtocol::emitAck(const char* command) const noexcept {
  cJSON* document = cJSON_CreateObject();
  if (document == nullptr) {
    return;
  }
  cJSON_AddStringToObject(document, "type", "ack");
  cJSON_AddNumberToObject(document, "schema_version", control::schema::kSchemaVersion);
  cJSON_AddStringToObject(document, "schema_hash", control::schema::kSchemaHash);
  cJSON_AddStringToObject(document, "command", command != nullptr ? command : "");
  wire::emitJsonDocument(document);
}

void SerialJsonProtocol::emitStatus(const DummyEnvironmentSimulator& simulator,
                                    const DemoRuntimeState& runtime) const noexcept {
  wire::emitLightStatus(simulator, runtime);
}

void SerialJsonProtocol::writeJson(cJSON* document) const noexcept {
  wire::emitJsonDocument(document);
}

}  // namespace demo
}  // namespace growbox