# Architecture handoff

Updated: 2026-09-11
Repository: `MichalMatu/growbox-ml-controller`
Primary development branch after cleanup: `main`

## State

The OutputSupervisor migration and the later architecture/quality refactor are complete. This file is now a compact handoff, not an active implementation plan.

Latest code-bearing compact software verification:

`1a599a58eb57841206ab92c7a5cacf50f7463f78`

Verification on that exact SHA passed architecture/config guards, the focused runtime transport regression, all `51/51` host C++ tests and one CrowPanel real-input ESP-IDF build.

Historical full Physical H qualification remains attached only to executable:

`02208d23f403bca3540dbbd652eb55703a044833`

Historical terminal evidence: `20260910-output-supervisor-physical-h-v3`.

Do not claim that later refactor SHAs inherit the historical executable qualification.

## Final production architecture

- `ClimateV6RealInputRuntime` is a thin bootstrap;
- `RealInputRuntimeComposition` owns construction/lifetimes;
- `RealInputRuntimeCoordinator` owns one-cycle orchestration;
- coordinator dependencies are grouped into input/output/support domains;
- `RuntimeOutputTransport` owns the transport availability/truth boundary;
- `RuntimeOutputTelemetryLog` owns output telemetry formatting;
- service-console transport/router dispatches to output/storage/system handlers;
- CMake/runtime profiles are the configuration SSOT and generate typed `RuntimeBuildConfig.h`;
- production V6 and legacy source graphs are isolated;
- production real-input composition is fenced to deterministic Rule authority;
- `OutputSupervisor` remains the only normal configured physical-output execution owner.

When physical transport is unavailable, command attempts return `NotAttempted/Unavailable`. They must not create successful execution state or physical acknowledgement.

## Frozen invariants

- deterministic Rule authority in production;
- ML shadow/research-only;
- lamp trip `>=28 C`;
- recovery `<=26 C` continuously for 10 minutes;
- safety remains active when normal automation is disabled;
- one-way RF is not physical acknowledgement;
- raw RF only via explicit `MaintenanceLocked` handling;
- no hidden configured-output writer outside `OutputSupervisor`.

## What remains historical

Stage27/Stage28 handoff documents, A12/A13 records and Phase H records are retained as evidence. They should not be rewritten to look like current workflow and should not be executed blindly as current test plans.

## Active continuation

Use:

- `docs/CURRENT_STATUS.md` for the current state;
- `docs/ARCHITECTURE.md` for current boundaries;
- `docs/PROJECT_ROADMAP.md` for the next product work;
- `docs/CONTINUATION_PLAN.md` for fresh-context workflow.

Normal development proceeds from `main`. `agent-control` remains control state and `gh-pages` remains publishing infrastructure.
