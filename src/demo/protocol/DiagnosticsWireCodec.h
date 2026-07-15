#pragma once

#include "demo/DummyEnvironmentSimulator.h"
#include "demo/SerialJsonProtocol.h"

struct cJSON;

namespace growbox {
namespace demo {
namespace wire {

cJSON* buildDiagnosticsDocument(const DummyEnvironmentSimulator& simulator,
                                const DemoRuntimeState& runtime) noexcept;

void emitDiagnostics(const DummyEnvironmentSimulator& simulator,
                     const DemoRuntimeState& runtime) noexcept;

}  // namespace wire
}  // namespace demo
}  // namespace growbox