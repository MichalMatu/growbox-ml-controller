from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dedent(content).lstrip(), encoding="utf-8")


write(
    "docs/CURRENT_STATUS.md",
    r'''
    # Current controller status

    Date: 2026-08-28  
    Development branch: `mvp/environment-controller`

    This is the short source of truth for the current climate-controller product path. Historical
    simulator, browser-contract and repository-convergence documents remain for reproducibility, but
    they must not be read as the current climate runtime architecture.

    ## Authoritative climate path

    Climate-v6 is the active migration target for new controller work:

    - schema v6 / contract `climate-mvp-v1`;
    - 44 runtime-observable input features;
    - 6 semantic ML-controlled outputs: heater, cooler, exhaust fan, humidifier, dehumidifier and CO2 doser;
    - bounded model shape `44 -> 32 -> 32 -> 6` retained for compatibility/research;
    - Rule remains the authoritative runtime policy;
    - `MlShadow` evaluates ML without changing the applied command;
    - `MlActive` is an explicit research opt-in and is not qualified for real growbox actuation;
    - deterministic arbitration and safety remain authoritative over every policy proposal;
    - effective-actuator state advances only from the final applied semantic command.

    The scientific rationale and rejected alternatives are frozen in `docs/ML_DECISION_REPORT.md`.

    ## Runtime implementation completed

    The C++ climate-v6 runtime includes:

    - `ClimateFeatureEncoder`;
    - `ClimateRuntimeController` with Rule / ML_SHADOW / ML_ACTIVE modes;
    - trend and effective-actuator state estimation;
    - Python/C++ golden parity;
    - validated trace schema and streaming NDJSON recording;
    - deterministic trace replay and counterfactual ML evaluation;
    - `ClimateControlLoop` with fail-closed input handling, best-effort OFF on actuator rejection and
      an actuator fault latch;
    - multi-step virtual HIL tests covering state, stale/unavailable inputs, shadow ML, safety
      transitions and rejected actuator commands.

    These sources compile in the real ESP-IDF ESP32-S3 firmware build. The local framework and CI
    baseline are ESP-IDF v5.5.4.

    ## Hardware-neutral I/O seam

    `src/climate/ClimateIoAdapters.*` is the application-side boundary for future hardware work. It
    deliberately contains no SCD41, BLE, RTC, GPIO, relay, PWM or networking dependency.

    `ClimateSnapshotProvider` supplies runtime-observable measurements/configuration. The input
    adapter maps that snapshot to `ClimateInputSource`. `ClimateRoleDriver` accepts normalized
    semantic role commands and the actuator adapter maps all six climate outputs to those roles.

    `ClimateControlLoop` owns confirmed previous actions. `ClimateRuntimeController` owns trends and
    estimated effective actions. Hardware providers must not duplicate those states.

    ## Not integrated yet

    `src/main.cpp` still runs the preserved legacy simulator/serial demonstration through the older
    `EnvironmentController`. Climate-v6 is compiled and host/HIL tested but is not yet the default
    `app_main()` execution path and does not drive physical loads.

    Planned first hardware set remains:

    - inside: SCD41 for air temperature, RH and CO2;
    - outside: external BLE temperature/RH sensor, exact model not frozen;
    - system time: backed-up hardware RTC, exact part not frozen;
    - physical actuator endpoints: not frozen yet.

    See `docs/MVP_HARDWARE_SENSOR_SET.md`.

    ## Next steps

    1. Keep the legacy demo intact while proving the new adapter seam in host and ESP-IDF builds.
    2. Add concrete SCD41 / BLE / RTC providers after parts and libraries are frozen.
    3. Add concrete semantic actuator-role drivers.
    4. Bring up real hardware in Rule mode first.
    5. Run ML only in `MlShadow` while collecting real traces.
    6. Re-qualify ML from real data before considering active ML actuation.
    ''',
)

write(
    "docs/ARCHITECTURE.md",
    r'''
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
    ''',
)

readme = ROOT / "README.md"
text = readme.read_text(encoding="utf-8")
old_status = "> **Integration status:** `integration/convergence-2026-08` is a non-destructive convergence workspace. The original product lines and dated archive snapshots remain available until this branch is fully validated. See [docs/INTEGRATION_CONVERGENCE.md](docs/INTEGRATION_CONVERGENCE.md)."
new_status = "> **Current controller status:** climate-v6 runtime work continues on `mvp/environment-controller`. Rule is authoritative, ML is shadow/research-only, and the hardware-neutral I/O seam is now being integrated. See [docs/CURRENT_STATUS.md](docs/CURRENT_STATUS.md)."
assert old_status in text
text = text.replace(old_status, new_status, 1)
old_fw = "The native ESP-IDF application runs a generated C inference model and places a deterministic `SafetySupervisor` between the model proposal and the final control decision. The demonstration firmware uses a local simulator and bounded UART/NDJSON protocol; it does **not** drive real GPIO loads in the demo configuration."
new_fw = "The preserved ESP-IDF demonstration still uses the legacy `EnvironmentController` plus local simulator/UART protocol. In parallel, the current climate-v6 C++ runtime (`ClimateRuntimeController` + `ClimateControlLoop`) is host/HIL tested and compiled into the real ESP32-S3 firmware build. It does **not** drive real GPIO loads yet."
assert old_fw in text
text = text.replace(old_fw, new_fw, 1)
old_contract = "**Firmware/controller contract:** `schemas/environment-controller.json` is currently **schema v4: 4 pot slots, 128 model features and 15 outputs**. This remains the active firmware/wire contract during repository convergence."
new_contract = "**Contract boundary:** the preserved legacy demo/wire path still uses root schema v4, while all new climate-controller runtime work targets `schemas/environment-controller.v6.json`: **44 runtime-observable features and 6 ML-controlled climate outputs**. The contracts are intentionally not silently mixed."
assert old_contract in text
text = text.replace(old_contract, new_contract, 1)
start = text.index("## Control path\n")
end = text.index("## Firmware stack\n")
control_section = dedent(r'''
## Control path

```mermaid
flowchart TB
    Providers["Measurements / config / time providers"] --> InputAdapter["ClimateInputAdapter"]
    InputAdapter --> Loop["ClimateControlLoop"]
    Loop --> Runtime["ClimateRuntimeController"]
    Runtime --> Rule["Rule policy — authoritative"]
    Runtime --> ML["ML — shadow by default"]
    Rule --> Arb["Arbitration + deterministic safety"]
    ML --> Arb
    Arb --> Sink["ClimateActuatorAdapter"]
    Sink --> Roles["Semantic actuator roles"]
    Roles --> Hardware["GPIO / relays / remote devices later"]
```

The legacy simulator/serial demo remains available while this climate-v6 application path is being
integrated. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

''')
text = text[:start] + control_section + text[end:]
text = text.replace("ESP-IDF 5.5.1", "ESP-IDF 5.5.4")
readme.write_text(text, encoding="utf-8")

changelog = ROOT / "docs" / "CHANGELOG.md"
text = changelog.read_text(encoding="utf-8").replace("ESP-IDF 5.5.1", "ESP-IDF 5.5.4")
marker = "## Unreleased\n\n"
assert marker in text
if "Add Rule / ML_SHADOW / ML_ACTIVE runtime modes" not in text:
    bullets = dedent(r'''
    - Add Rule / ML_SHADOW / ML_ACTIVE runtime modes with Rule as the default authority and deterministic safety remaining final.
    - Add the 44-feature climate-v6 C++ runtime, Python/C++ golden parity, trace schema/NDJSON recording, deterministic replay and counterfactual ML evaluation.
    - Add `ClimateControlLoop` fail-closed I/O handling, actuator OFF recovery/fault latch, and multi-step virtual HIL coverage.
    - Compile climate-v6 sources in the real ESP-IDF ESP32-S3 firmware build and align local/CI ESP-IDF to v5.5.4.
    - Add a hardware-neutral application I/O adapter seam for future sensor/configuration providers and semantic actuator-role drivers; no physical drivers are enabled yet.
    ''')
    text = text.replace(marker, marker + bullets, 1)
changelog.write_text(text, encoding="utf-8")

layout = ROOT / "docs" / "PROJECT_LAYOUT.md"
text = layout.read_text(encoding="utf-8")
text = text.replace("Intentional structure after the v4 pots cleanup. Prefer this map over scattering new files at the root.", "Intentional repository structure. Current climate-v6 status is tracked in `CURRENT_STATUS.md`; legacy v4/v5 assets remain where required for migration/reproducibility.")
text = text.replace("├── lib/environment_control/  # portable C++ controller library", "├── lib/environment_control/  # portable legacy + climate-v6 C++ controller core")
text = text.replace("├── src/                      # ESP-IDF application (demo + serial)", "├── src/                      # ESP-IDF app; legacy demo plus climate-v6 I/O adapters")
layout.write_text(text, encoding="utf-8")

hardware = ROOT / "docs" / "MVP_HARDWARE_SENSOR_SET.md"
text = hardware.read_text(encoding="utf-8")
if "## Integration order" not in text:
    text += dedent(r'''

    ## Integration order

    Do not couple the climate core directly to a sensor library. The application-side
    `src/climate/ClimateIoAdapters.*` seam is integrated first and is tested with fakes.

    Concrete hardware work follows behind that seam:

    1. freeze the SCD41 library/driver and map its T/RH/CO2 readings into a snapshot provider;
    2. freeze the outside BLE sensor and map its T/RH plus freshness into the same snapshot;
    3. freeze the backed-up RTC and derive DAY/NIGHT target/schedule state outside the core;
    4. map physical output endpoints to semantic actuator roles;
    5. bring up hardware in Rule mode, then use ML_SHADOW for real trace collection.

    No soldering choice changes the 44-feature/6-output climate-v6 semantic contract.
    ''')
hardware.write_text(text, encoding="utf-8")

agents = ROOT / "AGENTS.md"
text = agents.read_text(encoding="utf-8")
text = text.replace("Local Agent v4.9.6", "Local Agent v4.10.2")
text = text.replace("release line: `v4.9.x`", "release line: `v4.10.x`")
text = text.replace("current synchronized release: `4.9.6`", "current synchronized release: `4.10.2`")
text = text.replace("### v4.9 execution rules", "### v4.10 execution rules")
agents.write_text(text, encoding="utf-8")

convergence = ROOT / "docs" / "INTEGRATION_CONVERGENCE.md"
text = convergence.read_text(encoding="utf-8")
notice = "> **Historical cleanup note:** this document records the repository convergence/branch cleanup. For the current climate-v6 runtime architecture and active development branch, use [CURRENT_STATUS.md](CURRENT_STATUS.md).\n\n"
if notice not in text:
    heading = "# Repository convergence and cleanup\n\n"
    assert heading in text
    text = text.replace(heading, heading + notice, 1)
contract_heading = "## Contract state\n"
if contract_heading in text:
    prefix = text[: text.index(contract_heading)]
    contract = dedent(r'''
    ## Contract state

    The convergence history includes legacy firmware schema v4 and browser schema v5. New climate
    runtime development targets schema v6 (`climate-mvp-v1`, 44 features, 6 ML-controlled climate
    outputs). The preserved legacy demo is intentionally not silently rewritten to v6. See
    `CURRENT_STATUS.md` for the live migration state.
    ''')
    text = prefix + contract
convergence.write_text(text, encoding="utf-8")

porting = ROOT / "docs" / "PORTING_TO_LITEGRAPH.md"
text = porting.read_text(encoding="utf-8")
porting_notice = "> **Migration note:** this document describes the older `EnvironmentController` integration model. New climate-v6 integration work should start from [CURRENT_STATUS.md](CURRENT_STATUS.md) and [ARCHITECTURE.md](ARCHITECTURE.md), using `ClimateControlLoop` and the semantic I/O adapter boundary.\n\n"
if porting_notice not in text:
    heading = "# GrowClip Nodeflow integration strategy\n\n"
    assert heading in text
    text = text.replace(heading, heading + porting_notice, 1)
porting.write_text(text, encoding="utf-8")
