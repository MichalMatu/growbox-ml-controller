#include "DiagnosticsWireCodec.h"

#include "EnvironmentSchema.h"
#include "HeapDiagnostics.h"
#include "JsonLineWriter.h"

#include <cJSON.h>

#ifndef GROWBOX_BOARD_PROFILE
#define GROWBOX_BOARD_PROFILE "esp32s3-devkitc1-n16r8"
#endif

namespace growbox {
namespace demo {
namespace wire {
namespace {

void addHeapObject(cJSON* parent, const char* key, const HeapSnapshot& heap) noexcept {
  cJSON* object = cJSON_CreateObject();
  if (object == nullptr) {
    return;
  }
  cJSON_AddBoolToObject(object, "psram_enabled", heap.psram_enabled);
  cJSON_AddNumberToObject(object, "free_internal", heap.free_internal);
  cJSON_AddNumberToObject(object, "free_psram", heap.free_psram);
  cJSON_AddNumberToObject(object, "min_free_internal", heap.min_free_internal);
  cJSON_AddNumberToObject(object, "min_free_psram", heap.min_free_psram);
  cJSON_AddNumberToObject(object, "largest_free_internal", heap.largest_free_internal);
  cJSON_AddNumberToObject(object, "largest_free_psram", heap.largest_free_psram);
  cJSON_AddNumberToObject(object, "total_psram", heap.total_psram);
  cJSON_AddItemToObject(parent, key, object);
}

}  // namespace

cJSON* buildDiagnosticsDocument(const DummyEnvironmentSimulator& simulator,
                                const DemoRuntimeState& runtime) noexcept {
  cJSON* document = cJSON_CreateObject();
  if (document == nullptr) {
    return nullptr;
  }

  const HeapSnapshot heap = captureHeapSnapshot();
  const TaskSnapshot task = captureTaskSnapshot();

  cJSON_AddStringToObject(document, "type", "diagnostics");
  cJSON_AddNumberToObject(document, "schema_version", control::schema::kSchemaVersion);
  cJSON_AddStringToObject(document, "schema_hash", control::schema::kSchemaHash);
  cJSON_AddStringToObject(document, "board_profile", GROWBOX_BOARD_PROFILE);
  addHeapObject(document, "heap", heap);

  cJSON* task_object = cJSON_CreateObject();
  if (task_object != nullptr) {
    cJSON_AddNumberToObject(task_object, "main_stack_free_bytes", task.main_stack_free_bytes);
    cJSON_AddItemToObject(document, "task", task_object);
  }

  cJSON* runtime_object = cJSON_CreateObject();
  if (runtime_object != nullptr) {
    cJSON_AddStringToObject(runtime_object, "mode",
                            runtime.mode == DemoMode::ClosedLoop ? "closed_loop" : "replay");
    cJSON_AddBoolToObject(runtime_object, "paused", runtime.paused);
    cJSON_AddNumberToObject(runtime_object, "step", runtime.step);
    cJSON_AddNumberToObject(runtime_object, "seed", simulator.seed());
    cJSON_AddItemToObject(document, "runtime", runtime_object);
  }

  return document;
}

void emitDiagnostics(const DummyEnvironmentSimulator& simulator,
                     const DemoRuntimeState& runtime) noexcept {
  emitJsonDocument(buildDiagnosticsDocument(simulator, runtime));
}

}  // namespace wire
}  // namespace demo
}  // namespace growbox