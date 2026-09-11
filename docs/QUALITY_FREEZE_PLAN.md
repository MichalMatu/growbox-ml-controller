# Final architecture and quality freeze plan

Status: active
Scope branch: `refactor/quality-freeze-final`
Base product branch: `mvp/environment-controller`
Base SHA: `100a7c9d618586b8b7c0add27084763261bee238`

## Goal

Complete the remaining architecture cleanup once, preserve all qualified safety/output invariants, and finish with one exact-SHA software quality gate plus any hardware requalification that is materially required by the final production-source diff.

The end state must have:

- one production climate controller path;
- one authoritative runtime/build configuration source;
- `OutputSupervisor` as the only normal configured physical-output owner;
- a thin real-input runtime composition root;
- a thin service-console transport/router with domain handlers;
- legacy controller code isolated from the production V6 target;
- architecture guards that make the boundaries executable constraints rather than documentation only;
- deterministic bounded build/test tooling;
- final exact-SHA evidence before the refactor is declared frozen.

## Frozen invariants

The cleanup must not change these product contracts unless a separate explicit product decision is made:

- deterministic rule control remains authoritative;
- ML remains shadow/research-only and cannot become active control implicitly;
- lamp thermal trip remains `>= 28 C`;
- lamp recovery remains `<= 26 C` continuously for 10 minutes;
- safety remains active while automation is disabled;
- one-way RF transmission is not physical acknowledgement;
- raw RF remains available only through explicit `MaintenanceLocked` capability;
- configured physical output execution remains owned by `OutputSupervisor`;
- no runtime refactor may fabricate executed/physical output truth.

## QF-0 — deterministic verification foundation

Problem:

- `scripts/run_clang_tidy_host.sh` performs an unnecessary full host build only to obtain `compile_commands.json`;
- host builds use unbounded `--parallel`, which made the previous quality gate exceed the Local Agent memory limit.

Changes:

- configure the clang-tidy host build tree without compiling it;
- introduce a bounded `HOST_BUILD_JOBS` default for actual host builds;
- validate the job-count input;
- use the same bounded value from the quality gate;
- retain an environment override for larger developer machines.

Acceptance:

- focused host tests pass;
- clang-tidy runs from the configured compile database without the redundant build;
- the quality gate no longer depends on all host cores being available.

## QF-1 — runtime/build configuration SSOT

Problem:

Board/runtime values and feature defaults are duplicated between `src/CMakeLists.txt`, fallback preprocessor definitions in `ClimateV6RealInputRuntime.cpp`, and board scripts such as `scripts/stage27c_crowpanel.sh`.

Target design:

- CMake owns resolved build configuration;
- one generated/typed runtime build configuration header exposes resolved values to C++;
- board scripts select profiles and intentional overrides instead of restating generic defaults;
- production C++ does not contain a second fallback-default table;
- configuration validation rejects incompatible feature/pin combinations where both features can be enabled together.

Acceptance:

- one authoritative default per setting;
- no production fallback macros duplicating CMake defaults;
- host/unit coverage for generated/resolved configuration where practical;
- CrowPanel real-input and fake-output build profiles still resolve to the intended pins/features.

## QF-2 — split `ClimateV6RealInputRuntime`

Problem:

`ClimateV6RealInputRuntime.cpp` is currently both composition root and runtime behavior owner. It contains resource construction, lifecycle logic, control-cycle orchestration, persistence synchronization, schedule/lamp-safety handling and telemetry.

Target design:

- a composition object owns construction/lifetimes of runtime dependencies;
- a small runtime coordinator owns one-cycle orchestration;
- lifecycle/fault handling has an explicit boundary;
- `runClimateV6RealInputRuntime()` becomes approximately initialize -> validate -> run;
- raw mutable readiness booleans are replaced by an explicit runtime execution-status abstraction where this improves lifetime/state clarity.

Non-goal:

Do not create a renamed monolithic `RuntimeManager`. New classes must each have one cohesive responsibility.

Acceptance:

- behavior-preserving tests remain green;
- output ownership guard remains green;
- runtime file becomes a composition entry point rather than a behavior container;
- safety, lifecycle and output truth semantics are unchanged.

## QF-3 — split `Stage28ServiceConsole`

Problem:

`Stage28ServiceConsole` mixes terminal IO/routing with output control, storage/logging, sensor/system diagnostics, RTC and RF diagnostics.

Target design:

Keep `Stage28ServiceConsole` responsible for line IO, parsing and dispatch only. Extract coarse domain handlers:

- output commands: manual, automation, maintenance;
- storage commands: SD status/list/read/self-test;
- system commands: status, sensors, RTC and RF diagnostics.

The existing `Stage28ServiceConsoleCommand` parser remains the parser SSOT.

Acceptance:

- no direct normal RF/output ownership is introduced;
- service-console tests cover dispatch and each handler domain;
- adding one future command does not require adding another unrelated dependency to the console transport/router.

## QF-4 — isolate legacy controller architecture

Problem:

The legacy environment controller and V6 climate controller are still compiled from the same component, and the source tree still makes both architectures appear equally production-relevant.

Target design:

- production V6 builds do not compile/link legacy controller/safety implementations by default;
- legacy code remains available only through an explicit demo/reference/test target where still needed;
- production app-mode selection is explicit and fail-closed;
- existing comparison/test use-cases are preserved deliberately rather than accidentally.

Acceptance:

- a build/architecture guard detects accidental legacy linkage into the production V6 target;
- V6 real-input and fake builds remain green;
- legacy tests/demos that are intentionally retained have an explicit build path.

## QF-5 — architecture guards and dependency review

Extend executable architecture checks only where they protect real boundaries discovered during QF-1..QF-4. At minimum verify:

- configured output writes cannot bypass `OutputSupervisor`;
- raw RF remains restricted to maintenance/diagnostic boundaries;
- production V6 does not link retired/legacy controller ownership;
- runtime configuration defaults have one source;
- service-console refactor does not reintroduce direct configured-output transport ownership.

Avoid style-only guards and LOC-only thresholds.

## QF-6 — post-refactor code audit

Perform a fresh audit of the final candidate, not merely the moved files. Review:

- class responsibility and dependency direction;
- mutable-state ownership and SSOT;
- lifetime/reference safety;
- duplicated policy/configuration;
- failure/fail-closed paths;
- dead compatibility paths;
- public APIs;
- stack/DRAM/PSRAM consequences;
- test coverage of the newly introduced boundaries.

Do not split cohesive components solely because they are large. In particular, do not split `ClimateRuntimeController` unless the final dependency audit finds a concrete responsibility violation.

## QF-7 — exact-SHA software gate

Iteration uses focused verification. The final candidate receives one broad software gate on one exact SHA:

- output/RF ownership and new architecture guards;
- Python tests excluding hardware;
- complete host C++ tests;
- focused Stage28D regressions;
- host clang-tidy;
- required schema/config checks;
- generic IDF build;
- CrowPanel real-input fake-output build;
- any additional production build matrix introduced by the legacy/config split;
- clean-tree and exact-SHA identity checks.

A failed final gate is not waived. Fix the defect, rerun affected focused verification, then rerun the final broad gate.

## QF-8 — hardware requalification decision

After the final production diff is frozen, compare it with the last physically qualified executable path.

- Documentation/test/tool-only changes do not trigger hardware work.
- Production-source changes that materially touch runtime composition, output execution, safety or hardware configuration require the current bounded physical qualification contract on the final SHA.
- Never claim historical physical qualification for a later executable SHA.

Qualified Growbox serial remains `/dev/cu.usbserial-1130` when physical qualification is required. `/dev/cu.usbserial-10` must not be touched.

## Execution policy

- Work happens on `refactor/quality-freeze-final`, based on the exact recorded MVP SHA.
- Direct GitHub edits are preferred for bounded, reviewable source/config/doc changes.
- Local Agent is used for Mac-local builds, ESP-IDF, clang-tidy and physical hardware evidence.
- Local Agent tasks use the repository binding `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`, `resources: []`, explicit work branch and bounded limits.
- No concurrent write task may race a direct GitHub write.
- Use focused verification during implementation and one final full software stage.
- Only after final evidence is green should `mvp/environment-controller` be fast-forwarded to the frozen candidate.

## Definition of done

This refactor is complete only when all planned architecture changes are implemented or explicitly demonstrated unnecessary by final code evidence, the exact final SHA passes the full software gate, required physical qualification (if triggered) passes on that same executable identity, and the product branch is advanced to that verified SHA.
