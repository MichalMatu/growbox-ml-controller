#include "ModelRuntime.h"

#include "generated/EnvironmentModel.h"

#include <array>
#include <cmath>

namespace growbox {
namespace control {
namespace {

bool stringsEqual(const char* first, const char* second) noexcept {
  if (first == nullptr || second == nullptr) {
    return false;
  }
  while (*first != '\0' && *second != '\0') {
    if (*first != *second) {
      return false;
    }
    ++first;
    ++second;
  }
  return *first == *second;
}

} // namespace

ModelStatus ModelRuntime::infer(const FeatureVector& features,
                                RawModelDecision& decision) const noexcept {
  decision = RawModelDecision{};
  if (!stringsEqual(generated_model::kSchemaHash, schema::kSchemaHash)) {
    return ModelStatus::SchemaMismatch;
  }
  if (generated_model::kInputCount != schema::kFeatureCount ||
      generated_model::kOutputCount != schema::kOutputCount) {
    return ModelStatus::ShapeMismatch;
  }
  for (const float value : features.values) {
    if (!std::isfinite(value)) {
      return ModelStatus::NonFiniteInput;
    }
  }

  std::array<float, schema::kOutputCount> output{};
  if (!generated_model::infer(features.values.data(), output.data())) {
    return ModelStatus::InferenceFailure;
  }
  for (const float value : output) {
    if (!std::isfinite(value)) {
      return ModelStatus::NonFiniteOutput;
    }
  }

  for (std::size_t index = 0; index < schema::kOutputCount; ++index) {
    rawOutputValue(decision, static_cast<schema::OutputIndex>(index)) = output[index];
  }
  return ModelStatus::Ok;
}

bool ModelRuntime::isSchemaCompatible(const char* model_schema_hash, std::size_t model_input_count,
                                      std::size_t model_output_count) noexcept {
  return stringsEqual(model_schema_hash, schema::kSchemaHash) &&
         model_input_count == schema::kFeatureCount && model_output_count == schema::kOutputCount;
}

bool ModelRuntime::isCompatible() noexcept {
  return isSchemaCompatible(generated_model::kSchemaHash, generated_model::kInputCount,
                            generated_model::kOutputCount);
}

const char* ModelRuntime::schemaHash() noexcept {
  return schema::kSchemaHash;
}

const char* ModelRuntime::modelSchemaHash() noexcept {
  return generated_model::kSchemaHash;
}

const char* ModelRuntime::modelVersion() noexcept {
  return generated_model::kModelVersion;
}

std::size_t ModelRuntime::inputCount() noexcept {
  return generated_model::kInputCount;
}

std::size_t ModelRuntime::outputCount() noexcept {
  return generated_model::kOutputCount;
}

} // namespace control
} // namespace growbox
