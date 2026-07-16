#pragma once

#include "EnvironmentController.h"
#include "EnvironmentTypes.h"

#include <cstdint>

namespace growbox {
namespace demo {
namespace wire {

struct DecisionEmitRequest {
  const control::ControllerInput* input = nullptr;
  const control::ControllerOutput* output = nullptr;
  control::ControllerStatus controller_status = control::ControllerStatus::Ok;
  std::uint32_t step = 0U;
};

void emitDecision(const DecisionEmitRequest& request) noexcept;

} // namespace wire
} // namespace demo
} // namespace growbox
