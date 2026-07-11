#pragma once

#include "EnvironmentTypes.h"

namespace growbox {
namespace control {

class FeatureEncoder {
public:
  static EncoderStatus encode(const ControllerInput& input, FeatureVector& output,
                              EncoderReport& report) noexcept;
};

} // namespace control
} // namespace growbox
