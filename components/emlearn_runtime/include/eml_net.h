#pragma once

// Narrow, header-only emlearn neural-network runtime used by the generated
// growbox model. The API and evaluation order match emlearn commit
// 3a4053a60e53d79d42b9d359eba72cd5c07e4e6b.

#include <math.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum _EmlError {
  EmlOk = 0,
  EmlSizeMismatch,
  EmlUnsupported,
  EmlUninitialized,
  EmlPostconditionFailed,
  EmlUnknownError,
  EmlErrors,
} EmlError;

typedef enum _EmlNetActivationFunction {
  EmlNetActivationIdentity = 0,
  EmlNetActivationRelu,
  EmlNetActivationLogistic,
  EmlNetActivationSoftmax,
  EmlNetActivationTanh,
  EmlNetActivationFunctions,
} EmlNetActivationFunction;

typedef struct _EmlNetLayer {
  int32_t n_outputs;
  int32_t n_inputs;
  const float* weights;
  const float* biases;
  EmlNetActivationFunction activation;
} EmlNetLayer;

typedef struct _EmlNet {
  int32_t n_layers;
  const EmlNetLayer* layers;
  float* activations1;
  float* activations2;
  int32_t activations_length;
} EmlNet;

static inline float eml_net_relu(float value) {
  return value <= 0.0f ? 0.0f : value;
}

static inline float eml_net_expit(float value) {
  return 1.0f / (1.0f + expf(-value));
}

static inline EmlError eml_net_softmax(float* input, size_t input_length) {
  if (input == NULL || input_length == 0U) {
    return EmlUninitialized;
  }

  float input_max = -INFINITY;
  for (size_t index = 0; index < input_length; ++index) {
    if (input[index] > input_max) {
      input_max = input[index];
    }
  }

  float sum = 0.0f;
  for (size_t index = 0; index < input_length; ++index) {
    sum += expf(input[index] - input_max);
  }
  if (!(sum > 0.0f) || !isfinite(sum)) {
    return EmlPostconditionFailed;
  }

  const float offset = input_max + logf(sum);
  for (size_t index = 0; index < input_length; ++index) {
    input[index] = expf(input[index] - offset);
  }
  return EmlOk;
}

static inline bool eml_net_valid(const EmlNet* model) {
  return model != NULL && model->layers != NULL && model->activations1 != NULL &&
         model->activations2 != NULL;
}

static inline int32_t eml_net_outputs(const EmlNet* model) {
  return model->layers[model->n_layers - 1].n_outputs;
}

static inline int32_t eml_net_find_largest_layer(const EmlNet* model) {
  int32_t largest = -1;
  for (int32_t layer = 0; layer < model->n_layers; ++layer) {
    if (model->layers[layer].n_inputs > largest) {
      largest = model->layers[layer].n_inputs;
    }
    if (model->layers[layer].n_outputs > largest) {
      largest = model->layers[layer].n_outputs;
    }
  }
  return largest;
}

static inline EmlError eml_net_forward(const float* input, int32_t input_length,
                                       const float* weights, const float* biases,
                                       EmlNetActivationFunction activation, float* output,
                                       int32_t output_length) {
  if (input == NULL || weights == NULL || biases == NULL || output == NULL) {
    return EmlUninitialized;
  }
  if (input_length <= 0 || output_length <= 0) {
    return EmlSizeMismatch;
  }

  for (int32_t output_index = 0; output_index < output_length; ++output_index) {
    float sum = 0.0f;
    for (int32_t input_index = 0; input_index < input_length; ++input_index) {
      const int32_t weight_index = output_index + (input_index * output_length);
      sum += weights[weight_index] * input[input_index];
    }
    output[output_index] = sum + biases[output_index];
  }

  switch (activation) {
    case EmlNetActivationIdentity:
      break;
    case EmlNetActivationRelu:
      for (int32_t index = 0; index < output_length; ++index) {
        output[index] = eml_net_relu(output[index]);
      }
      break;
    case EmlNetActivationLogistic:
      for (int32_t index = 0; index < output_length; ++index) {
        output[index] = eml_net_expit(output[index]);
      }
      break;
    case EmlNetActivationTanh:
      for (int32_t index = 0; index < output_length; ++index) {
        output[index] = tanhf(output[index]);
      }
      break;
    case EmlNetActivationSoftmax:
      return eml_net_softmax(output, (size_t)output_length);
    default:
      return EmlUnsupported;
  }
  return EmlOk;
}

static inline EmlError eml_net_layer_forward(const EmlNetLayer* layer, const float* input,
                                             int32_t input_length, float* output,
                                             int32_t output_length) {
  if (layer == NULL) {
    return EmlUninitialized;
  }
  if (input_length < layer->n_inputs || output_length < layer->n_outputs) {
    return EmlSizeMismatch;
  }
  return eml_net_forward(input, layer->n_inputs, layer->weights, layer->biases,
                         layer->activation, output, layer->n_outputs);
}

static inline EmlError eml_net_infer(EmlNet* model, const float* features,
                                     int32_t features_length) {
  if (!eml_net_valid(model) || features == NULL) {
    return EmlUninitialized;
  }
  if (model->n_layers < 2) {
    return EmlUnsupported;
  }
  if (features_length != model->layers[0].n_inputs ||
      model->activations_length < eml_net_find_largest_layer(model)) {
    return EmlSizeMismatch;
  }

  const int32_t buffer_length = model->activations_length;
  float* buffer1 = model->activations1;
  float* buffer2 = model->activations2;

  EmlError error = eml_net_layer_forward(&model->layers[0], features, features_length, buffer1,
                                         buffer_length);
  if (error != EmlOk) {
    return error;
  }

  for (int32_t layer_index = 1; layer_index < model->n_layers - 1; ++layer_index) {
    error = eml_net_layer_forward(&model->layers[layer_index], buffer1, buffer_length, buffer2,
                                  buffer_length);
    if (error != EmlOk) {
      return error;
    }
    for (int32_t index = 0; index < buffer_length; ++index) {
      buffer1[index] = buffer2[index];
    }
  }

  return eml_net_layer_forward(&model->layers[model->n_layers - 1], buffer1, buffer_length,
                               buffer2, buffer_length);
}

static inline int32_t eml_net_predict(EmlNet* model, const float* features,
                                      int32_t features_length) {
  const EmlError error = eml_net_infer(model, features, features_length);
  if (error != EmlOk) {
    return -(int32_t)error;
  }

  const int32_t output_count = eml_net_outputs(model);
  if (output_count == 1) {
    return model->activations2[0] > 0.5f ? 1 : 0;
  }
  if (output_count <= 0) {
    return -(int32_t)EmlUnknownError;
  }

  float maximum = -INFINITY;
  int32_t maximum_index = -1;
  for (int32_t index = 0; index < output_count; ++index) {
    if (model->activations2[index] > maximum) {
      maximum = model->activations2[index];
      maximum_index = index;
    }
  }
  return maximum_index;
}

static inline EmlError eml_net_regress(EmlNet* model, const float* features,
                                       int32_t features_length, float* output,
                                       int32_t output_length) {
  if (output == NULL || !eml_net_valid(model)) {
    return EmlUninitialized;
  }
  const int32_t model_output_count = eml_net_outputs(model);
  if (output_length != model_output_count) {
    return EmlSizeMismatch;
  }

  const EmlError error = eml_net_infer(model, features, features_length);
  if (error != EmlOk) {
    return error;
  }
  for (int32_t index = 0; index < model_output_count; ++index) {
    output[index] = model->activations2[index];
  }
  return EmlOk;
}

static inline float eml_net_regress1(EmlNet* model, const float* features,
                                     int32_t features_length) {
  float output[1] = {0.0f};
  return eml_net_regress(model, features, features_length, output, 1) == EmlOk ? output[0]
                                                                                : NAN;
}

#ifdef __cplusplus
}  // extern "C"
#endif
