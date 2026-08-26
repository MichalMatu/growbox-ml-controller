#pragma once
#include "ClimateTypes.h"
namespace growbox::climate {
class ClimateFeatureEncoder { public: static ClimateFeatureVector encode(const ClimateControllerInput& input, ClimateEncoderReport* report=nullptr) noexcept; };
}  // namespace growbox::climate
