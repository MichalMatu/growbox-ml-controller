# Fresh-context continuation plan

Updated: 2026-09-11
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Local Agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`
Fresh-chat entrypoint: `docs/FRESH_CHAT_BOOTSTRAP.md`

## Minimal operator resume command

After selecting this repository in a new chat, the operator may simply write:

`sprawdz w jakim miejscu jestesmy, napisz krotkie podsumowanie i kontynuujmy dalsza prace nad kodem`

That is sufficient authorization to restore context from repository evidence, provide a short status summary, and continue the next sensible development task. Do not ask the operator to repeat project history merely to resume work. Follow `docs/FRESH_CHAT_BOOTSTRAP.md`.

## Read first in a new chat

1. `AGENTS.md`
2. `docs/FRESH_CHAT_BOOTSTRAP.md`
3. `docs/CURRENT_STATUS.md`
4. `docs/ARCHITECTURE_HANDOFF.md`
5. this file
6. `docs/PROJECT_ROADMAP.md`

Read `docs/GUIDANCE.md`, `docs/STAGE28E_PHASE_H_HANDOFF.md`, and `docs/STAGE28D_AH_ARBITER_HANDOFF.md` only when historical qualification, diagnostics, or arbiter evidence is needed. They are no longer the active development sequence.

Then fetch fresh `mvp/environment-controller` HEAD and fresh `agent-control:.agent/status/daemon.json`. Never continue from remembered chat state alone.

## Current transition

**Stage27C FROZEN -> Stage28E A-G COMPLETE -> OUTPUT EXECUTION ARCHITECTURE A1-A12 COMPLETE -> A13 + PHYSICAL H COMPLETE -> NORMAL PRODUCT DEVELOPMENT**

The execution-architecture qualification workstream is complete.

Qualified production executable identity:

`02208d23f403bca3540dbbd652eb55703a044833`

Terminal physical evidence:

`20260910-output-supervisor-physical-h-v3` PASS

The current work branch may be a docs-only descendant of the qualified production SHA. Fetch the fresh branch HEAD before work; do not mistake later documentation commits for a new qualified executable identity.

## What is complete

- `OutputSupervisor` is the only normal production owner allowed to execute configured physical outputs.
- climate/schedule/manual paths produce intent rather than directly transmitting configured outputs.
- hard safety remains non-bypassable and independent of normal automation ownership.
- A12 full software qualification passed.
- A13 replay/preflight qualification passed.
- Physical H passed on the real Growbox with a natural humidity-driven `ClimateDecision` fan transition.
- independent Shelly evidence showed `22.0 W -> 24.8 W` (`+2.8 W`).
- the absolute-humidity gradient contracted by `0.381 g/m3`, exceeding the frozen `0.30 g/m3` threshold.
- final supervisor-owned shutdown reached `Disabled`, fan OFF, humidifier OFF, transport clean.
- historical H v8 is frozen and must not be run.

No further A12/A13/H work is required merely to continue ordinary product development.

## Current product-development goal

Return to improving the actual growbox rather than qualification for its own sake.

Start with a read-only audit of the current code and identify the best next changes across:

- temperature and humidity control quality;
- absolute-humidity ventilation decisions;
- controller deadband, hysteresis, dwell and interaction between temperature/humidity goals;
- growbox configuration and operator UX;
- panel/UI usability;
- logging, history, plots and replayability;
- ML-shadow feature quality, labels and offline evaluation;
- additional sensors/actuators only where they provide real product value.

Do not assume all of these deserve implementation. Rank the best 3-5 candidates by practical value, implementation cost, risk, ESP32-S3 RAM/CPU/flash impact, and verification cost. Prefer small/medium changes with high user value and clean ownership.

## First new-chat deliverable

Before coding, report:

`What we have -> biggest product gaps -> 3-5 best next changes -> recommended first change and why.`

Ground this in current source, not only documentation.

## Work-mode policy

### Sandbox first

Use the available sandbox/container aggressively for work that does not require the physical Mac or devices. Prefer it for code analysis, parsing telemetry, simulations, synthetic data, controller experiments, replay, statistics, comparison scripts, and other compute-heavy analysis.

Do not consume Local Agent/Mac execution for computation that can be completed safely in the sandbox.

The sandbox should not be assumed to have Internet access. Use GitHub tools for repository content and the sandbox for processing/computation.

### Direct GitHub

Use direct GitHub edits for bounded source/config/docs changes when the exact diff and relevant CI or focused verification are sufficient. A commit proves publication, not runtime correctness.

### Local Agent

Use Local Agent only when Mac-local execution is materially required, including PlatformIO/local toolchains, host builds/tests that depend on the local environment, pre-commit/pre-push, serial/USB/flash, local-network Shelly access, or physical hardware evidence.

Local Agent is a deterministic executor; ChatGPT remains the planner. Never invoke or delegate to local Codex.

Every Local Agent task must contain exactly:

```json
{
  "agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5",
  "work_branch": "mvp/environment-controller",
  "resources": []
}
```

Check `.agent/status/daemon.json` before modifying the same branch. Do not duplicate a healthy active task or poll long tasks at 30-second cadence.

## Hardware/network constants

Canonical Shelly IP:

`192.168.0.16`

Canonical Shelly status endpoint:

`http://192.168.0.16/rpc/Switch.GetStatus?id=0`

Do not guess, substitute, or network-scan for another Shelly address unless the operator explicitly changes it.

Qualified Growbox serial port:

`/dev/cu.usbserial-1130`

Never touch:

`/dev/cu.usbserial-10`

Do not use `/dev/cu.usbserial-1120` without separate authorization.

## Safety and ML invariants

- deterministic rule controller remains authoritative;
- ML remains shadow/research-only and must not directly own physical outputs;
- thermal trip remains `>=28 C`;
- thermal recovery remains `<=26 C` continuously for 10 minutes;
- one-way RF completion is transport evidence, not physical acknowledgement;
- raw RF remains restricted to explicit `MaintenanceLocked` handling;
- `OutputSupervisor` remains the only normal production owner of configured physical outputs.

## When qualification must be revisited

Do not rerun A12/A13/H after UI/docs-only work or unrelated product changes.

Requalification becomes necessary when a production-source change materially changes the qualified execution/safety/output path or when a new hardware qualification target is intentionally introduced. Scope the replacement verification to the actual change rather than blindly rerunning historical workflows.

Historical Stage28E and H documents remain evidence; do not delete them and do not execute historical H v8.
