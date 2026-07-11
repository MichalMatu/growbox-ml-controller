# Architecture

## Design goals

The repository separates a portable, deterministic controller from every deployment concern. The
same `environment_control` library is used by the ESP32-S3 demonstration and is intended to move
unchanged into GrowClip Nodeflow. The library does not include Arduino headers and does not depend
on serial I/O, JSON, GPIO, Wi-Fi, FreeRTOS, a sensor driver, an actuator driver, or either simulator.

```text
Demo today                                      GrowClip later
-----------                                     --------------
DummyEnvironmentSimulator                      Nodeflow sensor providers
             |                                               |
             +--------------- ControllerInput ---------------+
                                      |
                               FeatureEncoder
                                      |
                                ModelRuntime
                                      |
                              SafetySupervisor
                                      |
                           SafeControlDecision
             +------------------------+-----------------------+
             |                                                |
Demo simulator adapter                           Nodeflow ActionRegistry
```

## Layers

### Contract and generated metadata

`schemas/environment-controller-v1.json` owns field names, feature and output order, ranges,
defaults, units, and availability semantics. The generator emits `EnvironmentSchema.h` and model
metadata. A canonical schema hash is embedded in the schema header, model header, model manifest,
and boot log. The model runtime refuses inference when these values differ.

### Portable controller library

- `FeatureEncoder` validates finite values, applies validity masks, clamps inputs to contract
  ranges, and normalizes the fixed-size feature vector.
- `ModelRuntime` validates model metadata and invokes the generated emlearn model through a narrow,
  status-code-based API.
- `SafetySupervisor` deterministically enforces actuator availability and independent safety/timing
  constraints. It does not rely on model behavior for safety.
- `EnvironmentController` composes the three stages and returns the decision plus diagnostics. It
  neither logs nor touches hardware.

Inference uses stack or caller-owned fixed-size objects. It does not allocate dynamically or throw
exceptions.

### Demonstration firmware

The Arduino application runs a local closed loop against `DummyEnvironmentSimulator`. It uses
ArduinoJson only to parse bounded serial commands and serialize NDJSON records. No code path drives
GPIO. The simulator is an adapter and is not linked into the controller library.

### Host pipeline

The Python pipeline generates complete time-series scenarios, labels them with a deterministic
finite-action rollout teacher, trains a small regression MLP, exports it through emlearn, compares
Python and compiled-C predictions on golden vectors, and writes deterministic generated headers.
Splits are by scenario seed, so steps from one simulated run cannot cross data partitions.

## Safety boundary

The model only proposes continuous values in `[0, 1]`. The safety supervisor can mask, clamp, or
quantize proposals and reports a reason bitmask. Physical adapters remain responsible for mapping a
safe normalized command to PWM, duty cycles, relay states, or timed pump pulses.

The demo is an integration test, not a validated agronomic controller or a high-fidelity physical
simulation. Hardware interlocks remain mandatory in a real deployment.
