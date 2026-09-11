# Current controller status

Updated: 2026-09-11
Repository: `MichalMatu/growbox-ml-controller`
Primary development branch after cleanup: `main`
Control branch: `agent-control`
Fresh-chat entrypoint: `docs/FRESH_CHAT_BOOTSTRAP.md`
Product roadmap: `docs/PROJECT_ROADMAP.md`

## Current phase

The architecture/quality refactor is complete and normal product development is the active phase.

The latest code-bearing software-verified refactor identity is:

`1a599a58eb57841206ab92c7a5cacf50f7463f78`

Compact verification on that exact SHA passed:

- runtime/config/service-console/app-mode/output-ownership guards;
- focused `RuntimeOutputTransport` regression test;
- host C++ suite: `51/51` PASS;
- one full CrowPanel ESP-IDF real-input build;
- generated firmware binary size: `0xbc950` bytes;
- `hardware_started=0`.

Documentation-only descendants do not replace this code-bearing verification identity.

## Architecture state

The real-input firmware is no longer a monolithic runtime. The production path is split into:

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

The later quality-refactor code changed production runtime composition and therefore does **not** inherit that exact executable hardware qualification. Refactor requalification attempts confirmed the correct firmware/port/runtime path but did not produce a new terminal frozen Physical H PASS marker. Do not claim otherwise.

This does not block ordinary software/product development. Re-run bounded physical qualification only when a future release explicitly requires a fresh hardware-qualified executable identity.

Qualified Growbox serial device for any future physical qualification: `/dev/cu.usbserial-1130`.

Never touch `/dev/cu.usbserial-10`.

## Repository workflow

After repository cleanup, normal source work happens from `main`. `agent-control` remains the Local Agent control branch and `gh-pages` remains the publishing branch.

Local Agent tasks must use:

```json
{
  "agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5",
  "work_branch": "main",
  "resources": []
}
```

Use direct GitHub for bounded source/config/docs changes. Use Local Agent only when Mac-local builds/toolchains, local network, serial/USB/flash or physical devices are materially required.

## Immediate next work

Resume product development from `docs/PROJECT_ROADMAP.md`. The preferred next changes are small/medium, high-value improvements to controller behavior, configuration/UX, observability/replay, and ML-shadow evaluation. Avoid another broad architecture rewrite unless concrete evidence exposes a new responsibility or ownership problem.
