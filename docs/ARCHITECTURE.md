# Architecture

Work plan and v2 I/O roadmap: [plan.md](plan.md). Hardware mapping: [IO_MAP.md](IO_MAP.md).

## Design goals

The repository separates a portable, deterministic controller from every deployment concern. The
same `environment_control` library is used by the ESP-IDF demonstration and is intended to move
unchanged into GrowClip Nodeflow. The library does not depend on ESP-IDF, Arduino, serial I/O, JSON,
GPIO, networking, FreeRTOS, a sensor driver, an actuator driver, or either simulator.

```text
Standalone ESP-IDF demo                         GrowClip later
----------------------                         --------------
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
Demo simulator adapter                           Nodeflow actuator bridge
```

## ESP-IDF project boundary

The root is a native ESP-IDF project targeting ESP32-S3. `src/` is registered as the application
component, `lib/environment_control` is a separate portable component, and
`components/emlearn_runtime` provides only the dense-network API required by the generated model.
The current CI firmware baseline is ESP-IDF 5.5.1.

The application component owns UART setup, monotonic scheduling, cJSON parsing/serialization,
heap diagnostics, and the local demo lifecycle. It executes one controller cycle per wall-clock
second, representing ten simulated seconds. No code path configures or writes GPIO.

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

The ESP-IDF application runs a local closed loop against `DummyEnvironmentSimulator`. It uses the
built-in `json` component only to parse bounded serial commands and serialize NDJSON records. The
UART adapter is outside the controller library, and the simulator is not linked into the portable
component.

### Host pipeline

The Python pipeline generates complete time-series scenarios from a growbox thermodynamics
simulator (lumped-parameter, coupled T/RH/soil/fan/outside — see [plan.md](plan.md)), labels them
with a deterministic finite-action rollout teacher, trains a small regression MLP, exports it
through emlearn, compares Python and compiled-C predictions on golden vectors, and writes
deterministic generated headers. Splits are by scenario seed, so steps from one simulated run
cannot cross data partitions.

Portable C++ tests use ordinary CMake and CTest. They compile the same controller sources and the
same generated model as the firmware build.

## Safety boundary

The model only proposes continuous values in `[0, 1]`. The safety supervisor can mask, clamp, or
quantize proposals and reports a reason bitmask. Physical adapters remain responsible for mapping a
safe normalized command to PWM, duty cycles, relay states, or timed pump pulses.

The demo is an integration test, not a validated agronomic controller. The bundled environment
simulator targets training-grade thermodynamic fidelity (not runtime on real hardware — sensors
provide state there). Hardware interlocks remain mandatory in a real deployment.
