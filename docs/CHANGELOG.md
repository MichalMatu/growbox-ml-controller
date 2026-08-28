# Changelog

All notable changes to this project are documented here.

## Unreleased

- Complete climate-v6 research through Stage 16: qualify Sequence Teacher, add six effective-actuator state features, and preserve authoritative safety after applied actions.
- Keep the bounded 44 -> 32 -> 32 -> 6 MLP; reject residual policy and simple deterministic CO2/exhaust coupling after representative DEV regressions/trade-offs.
- Add explicit Sequence-Teacher DAgger support while preserving the legacy rollout default; stop after one bounded DEV iteration because switching gates fail on two DEV seeds.
- Freeze ML decisions and seed hygiene in `docs/ML_DECISION_REPORT.md`; move the next milestone to Rule-authoritative runtime shadow diagnostics and deterministic trace/replay.
- Migrate the standalone ESP32-S3 demonstration firmware from Arduino/PlatformIO to native
  ESP-IDF 5.5.1.
- Preserve the bounded NDJSON serial protocol, deterministic simulator, controller behavior, and
  generated-model identity.
- Add native ESP-IDF components, CMake/CTest host tests, and ESP-IDF CI builds.
- Vendor the small MIT-licensed emlearn dense-network runtime surface required by the generated
  model so firmware and host builds remain reproducible without network access.

## 0.1.0 - 2026-07-11

- Bootstrap the schema-driven, portable environment-controller library.
- Add the deterministic simulation, teacher, training, and emlearn export pipeline.
- Add the ESP32-S3 closed-loop demonstration firmware and bounded serial protocol.
- Add an optional, explicitly selected N32R16V OPI profile while keeping N8/no-PSRAM as default.
- Add host tests, firmware builds, CI, scenarios, and portability documentation.
- Harden serial replay correlation and malformed-log analysis.
