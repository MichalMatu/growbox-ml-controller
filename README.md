# Growbox ML Controller

Production-oriented TinyML environment-controller demo for ESP32-S3, designed for future GrowClip
Nodeflow integration.

The project trains a small neural-network controller on deterministic, physically inspired
growbox simulations, exports it to portable C with emlearn, and runs that exact generated model on
an ESP32-S3-DevKitC-1. A separate deterministic safety supervisor remains in control of hard
limits. The demonstration firmware only drives its local simulator: **it never configures or writes
GPIO**.

> This is an engineering demo, not a calibrated physical model or a validated controller for
> unattended heaters, pumps, or other real equipment.

## Architecture

```text
Python scenarios -> rollout teacher -> Keras MLP -> emlearn C model
                                                    |
Nodeflow provider (future) ---+                     v
Dummy simulator (today) ------+-> FeatureEncoder -> ModelRuntime -> SafetySupervisor
                                                                    |
                                      Nodeflow ActionRegistry <-----+
                                           (future adapter)
```

The reusable `lib/environment_control` library has no dependency on Arduino, `Serial`,
ArduinoJson, GPIO, Wi-Fi, FreeRTOS, sensor drivers, actuator drivers, or the demo simulator. It uses
fixed-size structures and performs no dynamic allocation during inference. See
[Architecture](docs/ARCHITECTURE.md).

## Hardware and software

- ESP32-S3-DevKitC-1; PlatformIO's
  [`esp32-s3-devkitc-1` board definition](https://docs.platformio.org/en/latest/boards/espressif32/esp32-s3-devkitc-1.html)
  targets the N8 module (8 MB quad flash, no PSRAM).
- A data-capable USB cable connected to the board's USB-to-UART port.
- VS Code with the recommended PlatformIO extension, or PlatformIO Core on `PATH`.
- Python 3.11 and the pinned packages in `requirements-lock.txt`.

Check the module marking before using a different memory profile. On octal flash/PSRAM variants,
GPIO35 through GPIO37 can be reserved internally. The demo avoids all GPIO, including the RGB LED,
so board-revision LED routing does not affect the smoke test. Refer to Espressif's
[ESP32-S3-DevKitC-1 v1.1 guide](https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide_v1.1.html).

An optional `esp32s3-devkitc1-n32r16v` environment is provided for the module explicitly marked
`ESP32-S3-WROOM-2-N32R16V`. It uses 32 MB octal flash, 16 MB octal PSRAM, a 32 MB partition table,
and USB Serial/JTAG CDC. It is never selected by default; do not use it for an N8/N8R8 board.

## Quick start

Run these commands from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-lock.txt
python -m tools.ml.pipeline --quick
pio test -e native
pio run -e esp32s3-devkitc1-n8
pio run -e esp32s3-devkitc1-n8 -t upload
pio device monitor -b 115200
```

For a verified N32R16V module, replace the environment in the build/upload commands:

```bash
pio run -e esp32s3-devkitc1-n32r16v
pio run -e esp32s3-devkitc1-n32r16v -t upload
pio device monitor -b 115200
```

If `pio` is not on `PATH` but the VS Code PlatformIO extension is installed, use its Core binary on
macOS/Linux:

```bash
~/.platformio/penv/bin/pio run -e esp32s3-devkitc1-n8
```

## VS Code workflow

1. Open this repository as the VS Code folder and install the recommended extensions.
2. Create and select `.venv` as the Python interpreter.
3. Run `PlatformIO: Build` or use the PlatformIO toolbar for the
   `esp32s3-devkitc1-n8` environment.
4. Select the USB-to-UART port before Upload/Monitor if multiple serial devices are present.

PlatformIO downloads the pinned Espressif platform and ArduinoJson version declared in
`platformio.ini`. A system-wide Arduino installation is not needed.

## Python setup on macOS

The quick-start virtual environment keeps TensorFlow, emlearn, NumPy, and test dependencies out of
the system Python. The pinned TensorFlow 2.21 package provides a macOS arm64 wheel but no Intel
macOS wheel; use a native Apple Silicon Python process rather than Rosetta. Command Line Tools are
required for the exported-model host compiler check:

```bash
xcode-select --install
file "$(command -v python3)"
```

Recreate `.venv` after changing Python architecture or minor version; do not mix packages from
another environment.

## Training and export

The quick profile trains a real, compact two-hidden-layer MLP and exercises the complete export
path on a small deterministic dataset:

```bash
python -m tools.ml.pipeline --quick
```

Use the larger scenario/epoch budget for an offline training run:

```bash
python -m tools.ml.pipeline --full
```

Both modes generate whole time-series scenarios, split by scenario seed, label them with a
deterministic finite-action rollout teacher, train and test Keras, export via emlearn, and compare
Python with compiled-C predictions. The generated firmware model, manifest, and small golden
vectors are committed; large datasets and working model files are ignored. See
[Model pipeline](docs/MODEL_PIPELINE.md).

## Build, upload, and monitor

```bash
pio test -e native
pio run -e esp32s3-devkitc1-n8
pio run -e esp32s3-devkitc1-n8 -t upload
pio device monitor -b 115200
```

Add `--upload-port /dev/cu.usbserial-10` or the appropriate local device when automatic selection
is ambiguous. Upload uses `esptool`; monitoring is 115200 baud.

On boot, firmware emits one startup NDJSON object containing the schema/model identity, followed by
one decision object per step. One wall-clock second represents a ten-second simulation step. Every
record occupies exactly one line, making it safe to stream into the host tools.

## Serial protocol and scenarios

Commands are one JSON object per line. Supported operations are `status`, `reset`, `seed`, `pause`,
`resume`, `step`, `target`, `load_scenario`, and `mode` (`closed_loop` or `replay`). Firmware uses a
bounded line buffer and returns an error record for oversized, malformed, or unsupported input.

Replay a committed scenario and save the bidirectional session:

```bash
python -m tools.serial.replay \
  --port /dev/cu.usbserial-10 \
  --scenario examples/scenarios/nominal.jsonl \
  --output logs/nominal-session.ndjson
```

Capture autonomous output until Ctrl+C:

```bash
python -m tools.serial.capture \
  --port /dev/cu.usbserial-10 \
  --baud 115200 \
  --output logs/closed-loop.ndjson
```

Analyse a capture and optionally export decision rows to CSV:

```bash
python -m tools.analysis.report logs/closed-loop.ndjson --csv logs/closed-loop.csv
```

The report validates records and summarizes target error, safety modifications, inference errors,
output oscillation, and inference latency.

## Contract and availability

`schemas/environment-controller-v1.json` is the single source of truth for field names, order,
units, ranges, defaults, and model inputs/outputs. Generation embeds its canonical short hash in
the C++ schema metadata, model, manifest, firmware, and startup logs. Firmware rejects a model built
for a different hash.

After changing the contract, regenerate its C++ view before retraining:

```bash
python tools/schema/generate_environment_schema.py
python -m tools.ml.pipeline --quick
```

Each sensor has an independent validity mask. A missing actuator is represented in configuration by
`available: false` and zero maximum capability. The encoder exposes this to the model, while the
safety supervisor independently forces that actuator's final output to zero. See
[Data contract](docs/DATA_CONTRACT.md).

## Tests and CI

```bash
python -m pytest
python -m tools.ml.pipeline --quick
pio test -e native
pio run -e esp32s3-devkitc1-n8
```

CI runs these checks without a physical board. It requires byte-identical regenerated model and
manifest headers, exact golden metadata/order, and numerically equivalent golden predictions across
CPU math kernels. Native tests cover feature order/ranges, invalid inputs, actuator masking, safety
alarms and timing, model/schema identity, golden inference, and output bounds.

## Demo limitations

- The simulator uses simplified thermal, humidity, CO2, and soil-water relationships.
- Synthetic training cannot establish real-world performance or safety.
- The v1 teacher is a short-horizon deterministic search, not model-predictive control or RL.
- The exported float model favors a transparent demonstration over aggressive quantization.
- No physical sensors or actuators are connected, calibrated, or driven.
- Upload and serial smoke testing require a locally attached board; CI only builds firmware.

## GrowClip Nodeflow path

A future integration with `MichalMatu/esp32s3_LiteGraph` will replace the dummy simulator with a
provider adapter and pass safe decisions to `ActionRegistry`. The encoder, runtime, supervisor,
schema identity checks, and fixed-size public types should move unchanged. No integration with that
repository is implemented here. See [Porting to LiteGraph](docs/PORTING_TO_LITEGRAPH.md).

## Convenience targets

`make setup`, `make train-quick`, `make train-full`, `make test`, `make build`, `make upload`,
`make monitor`, and `make clean` wrap the documented commands. Override `PIO` when necessary, for
example `make build PIO="$HOME/.platformio/penv/bin/pio"`.

## License

Released under the [MIT License](LICENSE).
