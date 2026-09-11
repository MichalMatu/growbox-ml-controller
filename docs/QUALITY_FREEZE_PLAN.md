# Final architecture and quality freeze plan

Status: **closed**
Started from product SHA: `100a7c9d618586b8b7c0add27084763261bee238`
Latest code-bearing compact software verification: `1a599a58eb57841206ab92c7a5cacf50f7463f78`

## Outcome

The planned architecture cleanup is complete. The final production structure has:

- one production climate-v6 path;
- one authoritative runtime/build configuration source;
- `OutputSupervisor` as the only normal configured physical-output owner;
- a thin real-input bootstrap plus separate composition/coordinator boundaries;
- a thin service-console transport/router with domain handlers;
- legacy controller code isolated from production V6 builds;
- executable architecture/config ownership guards;
- bounded deterministic host/build tooling;
- explicit transport truth semantics that do not fabricate execution when physical transport is unavailable.

## Frozen invariants preserved

- deterministic Rule control remains authoritative in production;
- ML remains shadow/research-only;
- lamp thermal trip remains `>= 28 C`;
- lamp recovery remains `<= 26 C` continuously for 10 minutes;
- safety remains active while normal automation is disabled;
- one-way RF transmission is not physical acknowledgement;
- raw RF remains restricted to explicit `MaintenanceLocked` handling;
- configured physical output execution remains owned by `OutputSupervisor`;
- unavailable transport must not fabricate executed/physical output truth.

## Stage result summary

### QF-0 — verification foundation: DONE

Host build parallelism was bounded and clang-tidy setup no longer requires a redundant full build just to create compile commands.

### QF-1 — runtime/build configuration SSOT: DONE

Canonical CMake/profile configuration now generates typed `RuntimeBuildConfig.h`. Production C++ fallback-default duplication was removed and guards enforce the boundary.

### QF-2 — real-input runtime split: DONE

`ClimateV6RealInputRuntime` is a thin bootstrap. Construction/lifetimes live in `RealInputRuntimeComposition`; one-cycle orchestration lives in `RealInputRuntimeCoordinator`.

### QF-3 — service-console split: DONE

Console line IO/routing is separated from output, storage and system command handlers.

### QF-4 — legacy isolation: DONE

Production V6 builds no longer compile the legacy controller path by default. App-mode selection is explicit.

### QF-5 — architecture guards: DONE

Guards cover output/RF ownership, runtime/config boundaries, service-console boundaries and app-mode isolation.

### QF-6 — post-refactor audit/debt burn: DONE

The re-audit found and fixed additional debt:

- `fake-locked` transport no longer reports false `Completed` execution;
- `RuntimeOutputTransport` is a separate focused boundary with regression coverage;
- coordinator dependencies are grouped by domain instead of a flat dependency bag;
- invalid lifecycle/automation/maintenance reports fail closed instead of being ignored;
- binary output policy constants moved out of composition wiring;
- output telemetry formatting moved out of coordinator orchestration;
- production Rule authority received an explicit compile-time fence;
- duplicated compile-definition runtime surface was reduced;
- retired Gate6 thermal test-sequence code was removed.

### QF-7 — software verification: DONE

The original broad QF-7 software gate passed on `fa56b345b5e555a68fc5a880779dee6f931acf66`.

After the additional debt burn, compact software verification passed on exact code-bearing SHA `1a599a58eb57841206ab92c7a5cacf50f7463f78`:

- all architecture/config guards PASS;
- focused runtime transport regression PASS;
- host C++ `51/51` PASS;
- one CrowPanel real-input ESP-IDF build PASS;
- firmware binary `0xbc950` bytes;
- `hardware_started=0`.

### QF-8 — hardware requalification: NOT RE-EARNED FOR FINAL REFACTOR SHA

Historical full Physical H remains valid only for its historical executable `02208d23f403bca3540dbbd652eb55703a044833`.

Refactor hardware attempts confirmed the expected board/port/runtime path and safe shutdown behavior, but the final frozen Physical H contract did not produce a terminal PASS on the refactor executable. The long-run contract waited for a 180-second clean fan-OFF baseline followed by a natural OFF->ON transition and did not obtain that transition during the final attempt.

Therefore:

- do not transfer the historical Physical H claim to `fa56...`, `1a599...` or later descendants;
- do not block ordinary software/product development on repeating the old long test;
- run a bounded fresh physical qualification only when a future release explicitly needs a new hardware-qualified executable identity.

## Definition-of-done interpretation

The architecture/software quality-freeze goal is complete. A fresh physical-executable qualification remains a separate release gate when required; it is not claimed as completed for the final refactor SHA.

This distinction intentionally preserves evidence integrity instead of calling an incomplete hardware run a PASS.

## Post-freeze workflow

Normal development proceeds from `main` after branch cleanup. Prefer focused verification and small coherent changes. Do not reopen the broad quality-freeze workstream unless new evidence shows a concrete architecture ownership/responsibility defect.

Current status: `docs/CURRENT_STATUS.md`.
Current roadmap: `docs/PROJECT_ROADMAP.md`.
