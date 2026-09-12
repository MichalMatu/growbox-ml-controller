# Changelog

All notable changes to this project are documented here.

## Unreleased

### Final release-readiness hardening — 2026-09-12

- Updated the Stage27C soak parser to preserve historical `soak_v=2` support while accepting current `soak_v=3` telemetry and its renamed storage fields.
- For v3 fake-output soak acceptance, validate the explicit physical-output fence (`output_v=2`, `transport_active=0`) instead of treating legacy loop `io_status=2/3` as a physical-output failure.
- Kept missing/stale lamp temperature fail-closed without synthesizing a thermal trip; a genuine over-temperature trip still survives temporary temperature loss and requires the full recovery hold.
- Added regression coverage for both parser versions and both lamp-safety state-history cases.
- Confirmed the intended long-lived remote branches are only `main`, `agent-control` and `gh-pages`; the latter two are required control/publishing branches, not cleanup candidates.
- Final code-bearing hardening identity: `e03763d019af405087a5fa9c6713a7165d2e623f`. Local verification passed 500 Python tests (12 hardware/visual skips), all 50 host C++ tests, five architecture/config ownership guards, host clang-tidy and three ESP-IDF builds.
- Canonical GitHub verification passed CI #865 and Sandbox Pack #63 on the same code-bearing SHA.
- Bounded current-board qualification `20260912-final-main-hardware-qualification-v1` passed on `/dev/cu.usbserial-1130`: strict 120 s `soak_v=3` reported zero violations, no reset/disconnect/SHA mismatch, and the first valid SCD41 sample cleared startup fail-closed state without a false `RecoveryHold`.
- Closeout leaves product development ready to move to the roadmap's first priority: evidence-backed controller behavior quality using real telemetry/replay baselines before tuning production behavior.

### Structural cleanup closeout — 2026-09-12

- Removed retired `BleOutsideSource`, `Stage27SdDataLogger` and obsolete `Stage27Telemetry.cpp` implementation.
- Removed unused `ClimateObservabilityMetrics` and its standalone host-test target.
- Moved `LampSafety` and `OutputBindings` under `src/climate/output/` while preserving namespaces and behavior.
- Reduced `RealInputRuntimeCoordinator.h` coupling to two direct includes by moving concrete dependencies into the implementation file.
- Final code-bearing identity: `0a7097a30280ec0f7bb408799c07093761d63e88`.
- Final software verification on that code line passed all runtime/config/service-console/app-mode/output-ownership guards, `50/50` host C++ tests, host clang-tidy, the CrowPanel real-input ESP-IDF build, GitHub CI #863 and Sandbox Pack #61.
- Final read-only structure re-audit reported zero include cycles, zero climate `.cpp` files without build/reference wiring and no remaining structural cleanup with a clear benefit-to-churn justification.
- The current code-bearing identity is ready to flash but is **not yet hardware-qualified**. Historical Physical H qualification remains attached only to `02208d23f403bca3540dbbd652eb55703a044833` until a new bounded physical run passes.

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
