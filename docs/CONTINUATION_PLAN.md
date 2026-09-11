# Fresh-context continuation plan

Updated: 2026-09-11
Repository: `MichalMatu/growbox-ml-controller`
Primary development branch after cleanup: `main`
Control branch: `agent-control`
Local Agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`
Fresh-chat entrypoint: `docs/FRESH_CHAT_BOOTSTRAP.md`

## Resume rule

A new chat should restore context from repository evidence instead of asking the operator to repeat project history.

Read:

1. `AGENTS.md`
2. `docs/FRESH_CHAT_BOOTSTRAP.md`
3. `docs/CURRENT_STATUS.md`
4. `docs/ARCHITECTURE.md`
5. `docs/PROJECT_ROADMAP.md`
6. this file

Historical Stage27/Stage28 handoffs and qualification documents are evidence, not the active work sequence.

Fetch fresh `main` HEAD and fresh `agent-control:.agent/status/daemon.json` before writes or Local Agent work.

## Current transition

`Stage27/28 platform qualification -> OutputSupervisor architecture -> quality refactor -> NORMAL PRODUCT DEVELOPMENT`

Latest code-bearing compact software verification:

`1a599a58eb57841206ab92c7a5cacf50f7463f78`

It passed architecture/config guards, the focused runtime transport truth regression, `51/51` host tests and one CrowPanel real-input ESP-IDF build.

Historical full Physical H remains frozen evidence for executable `02208d23f403bca3540dbbd652eb55703a044833`. Later refactor SHAs do not inherit that exact physical qualification.

## What is complete

- production runtime split into bootstrap, composition, coordinator and focused support boundaries;
- service console split into domain handlers/router;
- runtime/build configuration SSOT and typed generated config;
- production V6/legacy build isolation;
- `OutputSupervisor` normal configured-output ownership;
- unavailable transport no longer fabricates successful executed truth;
- production Rule authority explicitly fenced; ML remains shadow/research-only;
- architecture guards updated to enforce the final boundaries;
- retired Gate6 thermal test helper removed from production code;
- compact post-refactor software verification PASS.

## Next development goal

Improve the product rather than continue architecture work for its own sake. Use `docs/PROJECT_ROADMAP.md` to rank the next change. Prefer small/medium changes with high practical growbox value and software-verifiable behavior.

Likely areas:

- temperature/humidity control quality and tuning;
- configuration/operator UX;
- logging/history/explainability/replay;
- ML-shadow data and evaluation;
- additional devices only when a concrete use case justifies them.

## Work-mode policy

Use sandbox/container for analysis, replay, simulation and statistics. Use direct GitHub for bounded repository edits. Use Local Agent only for Mac-local toolchains/builds, local network, serial/USB/flash and physical devices.

Every Local Agent task must contain exactly:

```json
{
  "agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5",
  "work_branch": "main",
  "resources": []
}
```

Never invoke local Codex from Local Agent. Check active tasks before editing the same branch.

## Fixed hardware/network boundaries

- Shelly: `192.168.0.16`
- Growbox serial: `/dev/cu.usbserial-1130`
- Never touch: `/dev/cu.usbserial-10`
- Do not use `/dev/cu.usbserial-1120` without separate authorization

## Safety/ownership invariants

- deterministic Rule remains authoritative in production;
- ML remains shadow/research-only;
- thermal trip `>=28 C`;
- thermal recovery `<=26 C` continuously for 10 minutes;
- one-way RF completion is not physical acknowledgement;
- raw RF remains restricted to `MaintenanceLocked`;
- `OutputSupervisor` remains the only normal owner of configured physical outputs.

## Qualification policy

Do not rerun historical qualification workflows by default. Scope verification to the actual change. A fresh physical qualification is required only when the project intentionally needs a new hardware-qualified executable identity or a change materially affects physical output/safety behavior.
