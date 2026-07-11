# Porting to GrowClip Nodeflow

This repository intentionally does not modify or depend on `MichalMatu/esp32s3_LiteGraph`. The
future integration should preserve the controller library and replace only the demo adapters.

## Planned mapping

| Portable interface | Future Nodeflow role |
| --- | --- |
| `SensorState` and `SensorValidity` | Sensor-provider snapshot |
| `EnvironmentConfig`, `CultivationConfig` | Node or graph configuration |
| `ActuatorCapabilities` | Action capability discovery/configuration |
| `ControlTargets` | User/automation setpoints |
| `PreviousControlState` | Last committed ActionRegistry values |
| `EnvironmentController::process` | Scheduled pure controller evaluation |
| `SafeControlDecision` | Input to registered actions |
| `ControllerDiagnostics` | Structured Nodeflow diagnostics/telemetry |

## Integration steps

1. Copy or package `lib/environment_control` without `src/demo`.
2. Generate `ControllerInput` from one coherent Nodeflow sensor snapshot.
3. Supply a monotonic timestamp; never use wall-clock time for dwell or irrigation intervals.
4. Invoke the controller from a bounded scheduler context.
5. Translate each safe normalized output through `ActionRegistry`; keep device-specific units and
   pin handling in action adapters.
6. Commit the actually applied action values as `PreviousControlState` on the next cycle.
7. Route diagnostics through Nodeflow logging without adding logging to the library.
8. Reject configuration/model/schema combinations whose version or hash differs.

## Ownership boundaries

Nodeflow should own lifecycle, persistence, sensors, scheduling, concurrency, action dispatch, and
telemetry. The portable library should continue to own feature encoding, generated inference, and
deterministic safety policy. If graph access can occur concurrently, take a snapshot before calling
the library rather than adding locks or FreeRTOS dependencies inside it.

## Deployment checks

Before real actuators are enabled, add hardware interlocks, calibrate sensors and actuator models,
validate safe limits for the exact growbox, test loss-of-sensor behavior, measure worst-case
inference latency, and replay captured Nodeflow traces on the host.
