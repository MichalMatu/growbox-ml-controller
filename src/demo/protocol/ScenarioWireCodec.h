#pragma once

#include "EnvironmentTypes.h"

#include <cstdint>

struct cJSON;

namespace growbox {
namespace demo {
namespace wire {

void addScenarioSnapshot(cJSON* document, const control::ControllerInput& input) noexcept;

void addDecisionContext(cJSON* document, const control::ControllerInput& input) noexcept;

bool parseLoadScenario(const cJSON* root, control::ControllerInput& scenario,
                       std::uint32_t& seed) noexcept;

bool parseStepOverrides(const cJSON* root, control::SensorState& sensors,
                        control::SensorValidity& validity,
                        control::GlobalActuatorCapabilities& actuators, bool& has_sensors,
                        bool& has_validity, bool& has_actuators) noexcept;

bool parseTargetPatch(const cJSON* root, control::ControlTargets& targets) noexcept;

bool parseSeedValue(const cJSON* root, std::uint32_t& seed) noexcept;

cJSON* buildScenarioDocument(const control::ControllerInput& input, std::uint32_t seed) noexcept;

} // namespace wire
} // namespace demo
} // namespace growbox
