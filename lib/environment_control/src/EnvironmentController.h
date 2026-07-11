#pragma once

#include "FeatureEncoder.h"
#include "ModelRuntime.h"
#include "SafetySupervisor.h"

namespace growbox {
namespace control {

class EnvironmentController {
public:
  EnvironmentController() noexcept = default;

  ControllerStatus process(const ControllerInput& input, ControllerOutput& output) noexcept;

  void resetSafetyState() noexcept;

  const ModelRuntime& modelRuntime() const noexcept;

private:
  ModelRuntime model_{};
  SafetySupervisor safety_{};
};

} // namespace control
} // namespace growbox
