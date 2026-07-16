#include "StatusWireCodec.h"

#include "EnvironmentSchema.h"
#include "JsonLineWriter.h"
#include "ScenarioWireCodec.h"

#include <cJSON.h>

namespace growbox {
namespace demo {
namespace wire {

cJSON* buildLightStatusDocument(const DummyEnvironmentSimulator& simulator,
                                const DemoRuntimeState& runtime) noexcept {
  cJSON* document = cJSON_CreateObject();
  if (document == nullptr) {
    return nullptr;
  }
  cJSON_AddStringToObject(document, "type", "status");
  cJSON_AddNumberToObject(document, "schema_version", control::schema::kSchemaVersion);
  cJSON_AddStringToObject(document, "schema_hash", control::schema::kSchemaHash);
  cJSON_AddStringToObject(document, "mode",
                          runtime.mode == DemoMode::ClosedLoop ? "closed_loop" : "replay");
  cJSON_AddBoolToObject(document, "paused", runtime.paused);
  cJSON_AddNumberToObject(document, "step", runtime.step);
  cJSON_AddNumberToObject(document, "seed", simulator.seed());
  cJSON_AddNumberToObject(document, "simulated_time_s",
                          simulator.input().monotonic_time_ms / 1000U);
  return document;
}

void emitLightStatus(const DummyEnvironmentSimulator& simulator,
                     const DemoRuntimeState& runtime) noexcept {
  emitJsonDocument(buildLightStatusDocument(simulator, runtime));
}

void emitScenarioSnapshot(const DummyEnvironmentSimulator& simulator) noexcept {
  emitJsonDocument(buildScenarioDocument(simulator.input(), simulator.seed()));
}

} // namespace wire
} // namespace demo
} // namespace growbox
