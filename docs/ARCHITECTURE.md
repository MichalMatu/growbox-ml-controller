# Architecture

Current status: [CURRENT_STATUS.md](CURRENT_STATUS.md).
Hardware plan: [MVP_HARDWARE_SENSOR_SET.md](MVP_HARDWARE_SENSOR_SET.md).
Scientific decisions: [ML_DECISION_REPORT.md](ML_DECISION_REPORT.md).

## Design rule

The climate controller is independent from sensor libraries and physical actuator endpoints.
Hardware produces semantic measurements and consumes semantic role commands. The controller does
not know whether a value came from I2C, BLE, MQTT, a simulator or a recorded trace.

## Current climate-v6 path

```text
sensor/config/time providers
           |
           v
  ClimateInputSnapshot
           |
           v
  ClimateInputAdapter
           |
           v
   ClimateControlLoop
           |
           v
ClimateRuntimeController
   |               |
   | Rule          | optional ML
   |               | (shadow by default)
   +-------+-------+
           |
      arbitration
           |
  deterministic safety
           |
           v
   semantic safe command
           |
           v
 ClimateActuatorAdapter
           |
           v
   semantic role driver
           |
           v
GPIO / relay / PWM / remote device later
```

`ClimateControlLoop` is the I/O-facing safety boundary. If input acquisition fails, it passes an
invalid/default input into the runtime so deterministic safety resolves to OFF. If an actuator
command is rejected, it attempts all-OFF, resets unconfirmed runtime actuator state, and latches
an actuator fault if OFF also fails.

The loop owns confirmed previous-applied actions. The runtime owns trend estimation and the
effective-actuator estimator. Sensor/configuration adapters must not duplicate those states.

## Policy modes

- `Rule` — authoritative default and current production recommendation.
- `MlShadow` — ML is evaluated and recorded but Rule remains authoritative.
- `MlActive` — explicit research-only opt-in; not qualified for real actuation.

Arbitration and deterministic safety remain authoritative regardless of policy mode.

## Climate-v6 contract

`schemas/environment-controller.v6.json` and generated `ClimateContract.h` define schema v6,
contract `climate-mvp-v1`, 44 features and 6 ML-controlled semantic outputs. Inputs contain only
runtime-observable state: measurements with validity/freshness, targets, schedule level, trends,
previous applied actions, estimated effective actions and role capabilities.

The older root `schemas/environment-controller.json` and legacy `EnvironmentController` demo are
retained during migration because the serial demo/browser history still depends on them. They
are not the architecture for new climate-v6 runtime work.

## Application I/O boundary

`src/climate/ClimateIoAdapters.*` provides the narrow application seam:

- `ClimateSnapshotProvider` produces measurements, target/configuration state, schedule level,
  capabilities and sensor timeout;
- `ClimateInputAdapter` maps that snapshot to `ClimateInputSource`;
- `ClimateRoleDriver` accepts one normalized semantic role command at a time;
- `ClimateActuatorAdapter` maps all six climate outputs and reports failure if any role fails.

Concrete SCD41/BLE/RTC/GPIO dependencies stay outside `lib/environment_control`.

## Real-input runtime composition and RF433 boundary

The ESP32-S3 real-input application is deliberately split so the top-level runtime remains orchestration rather than a god object:

- `ClimateV6RealInputRuntime.cpp` wires lifecycle and the one-second application tick;
- `runtime/Stage27RuntimeAdapters.*` owns Stage27 physical-source adapters and the locked fake role driver;
- `runtime/Stage27TelemetryReporter.*` owns diagnostic snapshot construction/logging/storage enqueue;
- `runtime/Stage28RfDiagnostics.*` owns passive RF capture and bounded self-loopback diagnostics;
- `rf433/Rf433ProtocolCodec.*` owns portable protocol encode/decode;
- `rf433/Rf433RmtLoopback.*` owns ESP-IDF RMT transport;
- `rf433/Rf433HardwareConfig.h` owns frozen neutral remote/socket identities;
- `rf433/Rf433RmtTuning.h` owns the hardware-qualified receive envelope that host tests lock.

The current qualified RX envelope is 100 kHz resolution, 10 us minimum signal and 20 ms idle/max signal. Hardware identity remains below semantic role mapping. A local `SelfTx` classification is transport evidence, not physical socket-state acknowledgement.

## Verification layers

- Python scientific/simulator tests;
- Python/C++ golden runtime parity;
- portable C++ climate-v6 tests;
- `ClimateControlLoop` failure tests;
- multi-step virtual HIL tests;
- application I/O adapter mapping tests;
- real ESP-IDF ESP32-S3 compile gate;
- GitHub Actions CI on ESP-IDF v5.5.4.

Simulator or virtual-HIL PASS establishes software behavior, not real hardware readiness.

## Preserved legacy demo

`src/main.cpp` still drives `DummyEnvironmentSimulator` through the older
`EnvironmentController` and bounded UART/NDJSON protocol. This remains a reference/demo path
until climate-v6 has concrete providers. Do not silently mix the legacy and climate-v6 contracts.
