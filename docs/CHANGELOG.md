# Changelog

All notable changes to this project are documented here.

## Unreleased

### Architecture and runtime quality cleanup — 2026-09-11

- Split the real-input runtime into thin bootstrap, composition, coordinator, cycle-state, output-transport and output-telemetry boundaries.
- Split the Stage28 service console into a thin router/transport plus output, storage and system command domains.
- Centralize board/runtime configuration in CMake profiles and generate typed `RuntimeBuildConfig.h` for production C++.
- Isolate legacy controller sources from production climate-v6 builds and add executable app-mode/config/runtime ownership guards.
- Preserve `OutputSupervisor` as the only normal configured physical-output execution owner.
- Fix `fake-locked` transport semantics so unavailable transport reports `NotAttempted/Unavailable` instead of manufacturing successful executed state.
- Add focused `RuntimeOutputTransport` regression coverage and fail closed on invalid runtime lifecycle/automation/maintenance reports.
- Group coordinator dependencies by input/output/support domains and move output telemetry formatting out of hot orchestration.
- Move binary-output policy constants out of composition wiring and fence production runtime authority to deterministic Rule mode; ML remains shadow/research-only.
- Reduce duplicated `GROWBOX_*` compile-definition surface and remove the retired Gate6 thermal test-sequence helper.
- Compact post-refactor verification passed all architecture/config guards, the focused transport regression, `51/51` host C++ tests and a CrowPanel real-input ESP-IDF build on code-bearing SHA `1a599a58eb57841206ab92c7a5cacf50f7463f78`.
- Clarify that historical full Physical H evidence belongs only to its historical executable identity and is not automatically inherited by later refactor SHAs.

### Earlier climate-v6 / native ESP-IDF work

- Add Rule / ML_SHADOW / ML_ACTIVE runtime modes with Rule as the default authority and deterministic safety remaining final.
- Add the 44-feature climate-v6 C++ runtime, Python/C++ golden parity, trace schema/NDJSON recording, deterministic replay and counterfactual ML evaluation.
- Add `ClimateControlLoop` fail-closed I/O handling, actuator OFF recovery/fault latch, and multi-step virtual HIL coverage.
- Compile climate-v6 sources in the real ESP-IDF ESP32-S3 firmware build and align local/CI ESP-IDF to v5.5.4.
- Add a hardware-neutral application I/O adapter seam for sensor/configuration providers and semantic actuator-role drivers.
- Complete climate-v6 research through Stage 16 and preserve authoritative safety after applied actions.
- Keep the bounded 44 -> 32 -> 32 -> 6 MLP; reject residual policy and simple deterministic CO2/exhaust coupling after representative DEV regressions/trade-offs.
- Add explicit Sequence-Teacher DAgger support while preserving the legacy rollout default; stop after one bounded DEV iteration because switching gates fail on two DEV seeds.
- Freeze ML decisions and seed hygiene in `docs/ML_DECISION_REPORT.md`; move production use toward Rule-authoritative shadow diagnostics and deterministic trace/replay.
- Migrate the standalone ESP32-S3 firmware from Arduino/PlatformIO to native ESP-IDF 5.5.4.
- Preserve the bounded NDJSON serial protocol, deterministic simulator, controller behavior and generated-model identity.
- Add native ESP-IDF components, CMake/CTest host tests and ESP-IDF CI builds.
- Vendor the small MIT-licensed emlearn dense-network runtime surface required by the generated model.

## 0.1.0 - 2026-07-11

- Bootstrap the schema-driven, portable environment-controller library.
- Add deterministic simulation, teacher, training and emlearn export pipeline.
- Add the ESP32-S3 closed-loop demonstration firmware and bounded serial protocol.
- Add an optional explicitly selected N32R16V OPI profile while keeping N8/no-PSRAM as default.
- Add host tests, firmware builds, CI, scenarios and portability documentation.
- Harden serial replay correlation and malformed-log analysis.
