#pragma once

#include "demo/DummyEnvironmentSimulator.h"
#include "demo/SerialJsonProtocol.h"

struct cJSON;

namespace growbox {
namespace demo {
namespace wire {

cJSON* buildLightStatusDocument(const DummyEnvironmentSimulator& simulator,
                                const DemoRuntimeState& runtime) noexcept;

void emitLightStatus(const DummyEnvironmentSimulator& simulator,
                     const DemoRuntimeState& runtime) noexcept;

void emitScenarioSnapshot(const DummyEnvironmentSimulator& simulator) noexcept;

}  // namespace wire
}  // namespace demo
}  // namespace growbox