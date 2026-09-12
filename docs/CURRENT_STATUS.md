# Current controller status

Updated: 2026-09-12
Repository: `MichalMatu/growbox-ml-controller`
Primary development branch: `main`
Control branch: `agent-control`
Publishing branch: `gh-pages`
Fresh-chat entrypoint: `docs/FRESH_CHAT_BOOTSTRAP.md`
Product roadmap: `docs/PROJECT_ROADMAP.md`

## Current phase

The architecture/quality refactor and the follow-up structural cleanup are complete. The code-bearing `main` state is software-verified and ready to be flashed for bounded hardware qualification.

The latest code-bearing software-verified identity is:

`0a7097a30280ec0f7bb408799c07093761d63e88`

Verification completed for that code line:

- runtime/config/service-console/app-mode/output-ownership guards: PASS;
- host C++ suite: `50/50` PASS;
- host clang-tidy: PASS;
- CrowPanel ESP-IDF real-input build: PASS;
- generated firmware binary size: `0xbc950` bytes, with 82% of the configured app partition free;
- GitHub CI run #863: PASS;
- Sandbox Pack run #61: PASS;
- final read-only structure re-audit: PASS;
- physical hardware qualification for this SHA: **pending**.

Documentation-only descendants do not replace this code-bearing firmware identity.

## Structural cleanup closeout

The 2026-09-12 cleanup removed retired or unused climate code, tightened source layout and reduced header coupling without changing production behavior:

- removed retired `BleOutsideSource`, `Stage27SdDataLogger` and obsolete `Stage27Telemetry.cpp` implementation;
- removed unused `ClimateObservabilityMetrics` and its standalone test target;
- moved `LampSafety` and `OutputBindings` under `src/climate/output/`;
- reduced `RealInputRuntimeCoordinator.h` to two direct includes by moving concrete dependencies to the implementation file;
- preserved namespaces, runtime ownership and output/safety behavior.

The final structure re-audit on `0a7097a30280ec0f7bb408799c07093761d63e88` found:

- 82 climate headers and 135 internal include edges;
- zero include cycles;
- zero climate `.cpp` files without build/reference wiring;
- zero `TODO` / `FIXME` / `HACK` / `XXX` markers in the audited climate/core scope;
- no further structural refactor with a clear benefit-to-churn justification.

## Architecture state

The production real-input path is split into clear boundaries:

- `ClimateV6RealInputRuntime` — thin bootstrap/composition entry;
- `RealInputRuntimeComposition` — dependency ownership and lifetime wiring;
- `RealInputRuntimeCoordinator` — one-cycle orchestration;
- `RuntimeOutputTransport` — explicit physical-transport truth boundary;
- `RuntimeOutputTelemetryLog` — output telemetry formatting/logging;
- domain service-console handlers behind a thin router/transport layer.

`OutputSupervisor` remains the only normal production owner allowed to execute configured physical outputs.

The runtime configuration source of truth is CMake/profile based and exported to C++ through the generated typed `RuntimeBuildConfig.h` interface. Production V6 builds do not rely on duplicated fallback defaults.

The production controller is compile-time fenced to deterministic `Rule` authority. ML remains shadow/research-only unless a separate research build explicitly opts into another mode.

When physical transport is unavailable (`fake-locked`), the runtime reports `NotAttempted/Unavailable`; it must never fabricate executed or physical output truth.

## Frozen safety/output invariants

- deterministic rule control remains authoritative;
- ML remains shadow/research-only for production;
- lamp thermal trip remains `>= 28 C`;
- lamp recovery remains `<= 26 C` continuously for 10 minutes;
- safety remains active while normal automation is disabled;
- one-way RF completion is transport evidence, not physical acknowledgement;
- raw RF remains restricted to explicit `MaintenanceLocked` handling;
- configured physical output execution remains owned by `OutputSupervisor`.

## Hardware qualification status

Historical full Physical H remains valid evidence only for its exact executable identity:

`02208d23f403bca3540dbbd652eb55703a044833`

Terminal historical evidence: `20260910-output-supervisor-physical-h-v3`.

The current code-bearing identity `0a7097a30280ec0f7bb408799c07093761d63e88` has passed software/build/CI verification but has **not** yet completed a new bounded physical qualification. It is ready to flash; do not call it hardware-qualified until the physical run finishes successfully.

Qualified Growbox serial device for the next physical qualification: `/dev/cu.usbserial-1130`.

Never touch `/dev/cu.usbserial-10`.

Do not use `/dev/cu.usbserial-1120` without separate authorization.

## Repository workflow

The repository is cleaned to the expected long-lived branches:

- `main` — normal source and documentation work;
- `agent-control` — Local Agent control plane;
- `gh-pages` — publishing branch.

Local Agent tasks must use:

```json
{
  "agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5",
  "work_branch": "main",
  "resources": []
}
```

Use direct GitHub for bounded source/config/docs changes. Use Local Agent when Mac-local builds/toolchains, local network, serial/USB/flash or physical devices are materially required.

## Immediate next work

The next release-readiness step is bounded physical qualification of the current `main` firmware on `/dev/cu.usbserial-1130`. Build/flash the current tree, record the exact code-bearing identity above, and only promote that identity to hardware-qualified after the physical checks pass.

After hardware qualification, resume normal product development from `docs/PROJECT_ROADMAP.md`. Avoid another broad architecture rewrite unless concrete evidence exposes a new responsibility or ownership problem.
