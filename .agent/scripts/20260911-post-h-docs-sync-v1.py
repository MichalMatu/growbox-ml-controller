from pathlib import Path

QUALIFIED_SHA = "02208d23f403bca3540dbbd652eb55703a044833"
PHYSICAL_H_TASK = "20260910-output-supervisor-physical-h-v3"
SHELLY_IP = "192.168.0.16"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


# AGENTS.md: make fresh-chat bootstrap point at current post-H sources of truth.
path = Path("AGENTS.md")
text = path.read_text()
text = replace_once(
    text,
    "1. Read this `AGENTS.md`, `docs/GUIDANCE.md`, `docs/STAGE28D_AH_ARBITER_HANDOFF.md`, `docs/PROJECT_ROADMAP.md`, `docs/CURRENT_STATUS.md`, and `docs/CONTINUATION_PLAN.md` before proposing or executing changes. `docs/GUIDANCE.md` is the mandatory Stage28E A-H execution sequence while diagnostics/architecture hardening is active. Read `docs/STAGE27_NATIVE_IDF_HANDOFF.md` only when older native-platform decisions are needed.",
    "1. Read this `AGENTS.md`, `docs/CURRENT_STATUS.md`, `docs/ARCHITECTURE_HANDOFF.md`, `docs/CONTINUATION_PLAN.md`, and `docs/PROJECT_ROADMAP.md` before proposing or executing changes. Stage28E, A12, A13, and Physical H are complete. Read `docs/GUIDANCE.md`, `docs/STAGE28E_PHASE_H_HANDOFF.md`, and `docs/STAGE28D_AH_ARBITER_HANDOFF.md` only when historical diagnostics, qualification, or arbiter context is needed. Read `docs/STAGE27_NATIVE_IDF_HANDOFF.md` only when older native-platform decisions are needed.",
    "AGENTS bootstrap read order",
)
text = replace_once(
    text,
    "13. Do not reopen completed Stage25/26 work. Stage27 native-platform direction is frozen in `docs/STAGE27_NATIVE_IDF_HANDOFF.md`; the current control-path continuation is in `docs/STAGE28D_AH_ARBITER_HANDOFF.md`.",
    "13. Do not reopen completed Stage25/26 work. Stage27 native-platform direction is frozen in `docs/STAGE27_NATIVE_IDF_HANDOFF.md`; current post-qualification product continuation is in `docs/CONTINUATION_PLAN.md` and `docs/CURRENT_STATUS.md`.",
    "AGENTS current continuation",
)
text = replace_once(
    text,
    "14. While Stage28E is active, do not resume normal AH/arbiter functional development before Phases A-G in `docs/GUIDANCE.md` have passed their documented exit criteria and commits have been recorded.",
    "14. Do not rerun Stage28E/A12/A13/Physical H by default. Those stages are complete for the qualified executable identity. Requalification is required only when a later production-source change invalidates the relevant qualified execution path or when a new hardware qualification target is intentionally introduced.",
    "AGENTS completed qualification rule",
)
path.write_text(text)


# Fresh-context continuation becomes the authoritative post-H product-development handoff.
Path("docs/CONTINUATION_PLAN.md").write_text(f"""# Fresh-context continuation plan

Updated: 2026-09-11
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Local Agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`

## Read first in a new chat

1. `AGENTS.md`
2. `docs/CURRENT_STATUS.md`
3. `docs/ARCHITECTURE_HANDOFF.md`
4. this file
5. `docs/PROJECT_ROADMAP.md`

Read `docs/GUIDANCE.md`, `docs/STAGE28E_PHASE_H_HANDOFF.md`, and `docs/STAGE28D_AH_ARBITER_HANDOFF.md` only when historical qualification, diagnostics, or arbiter evidence is needed. They are no longer the active development sequence.

Then fetch fresh `mvp/environment-controller` HEAD and fresh `agent-control:.agent/status/daemon.json`. Never continue from remembered chat state alone.

## Current transition

**Stage27C FROZEN -> Stage28E A-G COMPLETE -> OUTPUT EXECUTION ARCHITECTURE A1-A12 COMPLETE -> A13 + PHYSICAL H COMPLETE -> NORMAL PRODUCT DEVELOPMENT**

The execution-architecture qualification workstream is complete.

Qualified production executable identity:

`{QUALIFIED_SHA}`

Terminal physical evidence:

`{PHYSICAL_H_TASK}` PASS

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
{{
  "agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5",
  "work_branch": "mvp/environment-controller",
  "resources": []
}}
```

Check `.agent/status/daemon.json` before modifying the same branch. Do not duplicate a healthy active task or poll long tasks at 30-second cadence.

## Hardware/network constants

Canonical Shelly IP:

`{SHELLY_IP}`

Canonical Shelly status endpoint:

`http://{SHELLY_IP}/rpc/Switch.GetStatus?id=0`

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
""")


# Project roadmap: replace stale Stage28D/Gate7 priority with the current product roadmap.
Path("docs/PROJECT_ROADMAP.md").write_text(f"""# Growbox ML project roadmap and chat handoff

Updated: 2026-09-11
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Local Agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`
Current continuation: `docs/CONTINUATION_PLAN.md`
Current execution handoff: `docs/ARCHITECTURE_HANDOFF.md`

## Source-of-truth order

For a fresh chat, read:

1. `AGENTS.md`
2. `docs/CURRENT_STATUS.md`
3. `docs/ARCHITECTURE_HANDOFF.md`
4. `docs/CONTINUATION_PLAN.md`
5. this roadmap

Older Stage27/Stage28 handoffs and `docs/GUIDANCE.md` are historical evidence unless a task specifically needs that context.

## Project direction

The project is a native ESP-IDF growbox environmental controller using real sensors, local RF433 actuators, deterministic safety, telemetry/logging, and a shadow ML path.

Current direction after Physical H PASS: improve product behavior and usability with small/medium, evidence-backed changes rather than extending the completed qualification workstream.

## Completed platform milestones

- Stage27C real-input native ESP-IDF baseline: FROZEN.
- Stage28A RF433 codec/classification: DONE.
- Stage28B ESP-IDF RMT TX/RX: DONE.
- Stage28C physical RF identity: DONE/FROZEN.
- absolute-humidity ventilation policy: DONE.
- Stage28E diagnostics/architecture hardening A-G: DONE.
- Output execution architecture A1-A12: DONE.
- A13 OutputSupervisor qualification tooling/preflight: DONE.
- Physical H: PASS.

Qualified production executable identity:

`{QUALIFIED_SHA}`

Physical H evidence:

`{PHYSICAL_H_TASK}` PASS

The physical H run proved the production chain from natural climate intent through OutputSupervisor/RF transport to independent Shelly power evidence and environmental response, then restored the supervisor-owned safe final state.

## Frozen physical identities

| role/load | ON | OFF | profile |
| --- | ---: | ---: | --- |
| fan / endpoint 1 | 906118656 | 1040336384 | protocol 2, 32 bit, 575 us, repeat 10 |
| lamp / endpoint 2 | 235030016 | 16926208 | protocol 2, 32 bit, 560 us, repeat 10 |
| humidifier / endpoint 3 | 637683200 | 771900928 | protocol 2, 32 bit, 560 us, repeat 10 |

Canonical Shelly host: `{SHELLY_IP}`.

## Architecture invariant

`OutputSupervisor` is the only normal production owner allowed to execute configured physical outputs.

Standing rules:

- climate/schedule/manual produce intents;
- safety produces non-bypassable constraints/forced actions;
- binary policy owns hysteresis/dwell rather than transport;
- RF433 transport is policy-free;
- one-way RF completion is not physical acknowledgement;
- raw RF is maintenance-only through explicit `MaintenanceLocked` handling;
- deterministic rule control remains authoritative;
- ML remains shadow/research-only.

## Current product roadmap

The next chat should audit current source and rank the following opportunities rather than blindly implementing all of them.

### 1. Controller quality

Review temperature/humidity interaction, absolute-humidity ventilation usefulness, targets, deadband/hysteresis, dwell, binary thresholds, and whether the controller is unnecessarily conservative or aggressive in real growbox conditions.

Prefer offline replay/simulation before hardware experimentation.

### 2. Configuration and operator UX

Reduce friction in configuring sensors, targets, actuators, schedules and growbox parameters. Preserve clear validation and bounded embedded resource cost.

### 3. Logging/history/plots

Improve the ability to answer why the controller made a decision and how the environment responded. Prefer compact telemetry and offline analysis over expensive firmware-side visualization/processing.

### 4. ML shadow/research

Improve feature logging, labels, deterministic-vs-ML comparison, replay datasets and evaluation metrics. ML must remain observe-only until separately justified and qualified.

### 5. Additional devices

Add sensors/actuators only where a concrete use case justifies code, RAM, UI and verification cost. Avoid feature accumulation for its own sake.

## Selection rule for the next implementation

Choose the first change by:

1. practical growbox value;
2. low/controlled safety risk;
3. clean architectural ownership;
4. modest ESP32-S3 RAM/CPU/flash cost;
5. ability to verify mostly in software/sandbox;
6. small coherent diff over broad rewrites.

The expected first deliverable is a source-backed shortlist of 3-5 changes with value/cost/risk/resource/test estimates and one recommended first implementation.

## Work-mode roadmap

- use sandbox/container first for analysis, replay, simulation, statistics and compute-heavy experiments;
- use direct GitHub for bounded edits when exact diff + CI/focused checks are sufficient;
- use Local Agent for Mac-specific builds/toolchains, local network, serial/USB/flash and physical devices;
- do not use Local Agent merely as general compute when sandbox can do the work;
- never invoke local Codex from Local Agent;
- every Local Agent task uses the exact repository binding, explicit `work_branch: mvp/environment-controller`, and `resources: []`.

## Hardware boundaries

Correct Growbox port: `/dev/cu.usbserial-1130`.

Never touch `/dev/cu.usbserial-10`.

Do not use `/dev/cu.usbserial-1120` without separate authorization.

Shelly: `{SHELLY_IP}`; do not scan for substitutes unless the operator explicitly changes the address.

## Qualification policy going forward

A12/A13/Physical H are complete for the qualified executable identity. Do not rerun them by default after docs/UI/unrelated work.

If a later production-source change materially modifies the qualified execution/safety/output path, determine the minimum required requalification from the actual diff and preserve the historical H evidence. Historical H v8 remains frozen and must not be run.
""")


# CURRENT_STATUS: keep completed qualification evidence and give the next chat a real product-development next step.
path = Path("docs/CURRENT_STATUS.md")
text = path.read_text()
old = """## Immediate next work

Phase H is complete. No further Phase H execution is required unless production source changes or a new hardware qualification target is intentionally introduced.

Preserve the terminal evidence above and the historical failed-safe attempts; do not rerun historical H v8.
"""
new = """## Immediate next work

Phase H is complete. Resume normal product development rather than extending qualification for its own sake.

The next chat should audit the current source and rank the best 3-5 improvements across controller temperature/humidity quality, configuration/UI, logging/history/plots, ML-shadow data/evaluation, and genuinely useful additional devices. Prefer small/medium high-value changes and use offline replay/simulation before new hardware experiments.

Use `docs/CONTINUATION_PLAN.md` as the current fresh-context handoff and `docs/PROJECT_ROADMAP.md` as the current product roadmap. Preserve the terminal qualification evidence above and the historical failed-safe attempts; do not rerun historical H v8.
"""
text = replace_once(text, old, new, "CURRENT_STATUS immediate work")
path.write_text(text)


# ARCHITECTURE_HANDOFF: add a clear post-H continuation section without rewriting historical qualification detail.
path = Path("docs/ARCHITECTURE_HANDOFF.md")
text = path.read_text()
anchor = "## Required architecture invariant\n"
post_h = f"""## Post-H product-development handoff

The execution-architecture workstream is complete. Normal product development may resume without further A12/A13/H work unless a later production-source change materially invalidates the qualified execution/safety/output path.

Current fresh-context handoff: `docs/CONTINUATION_PLAN.md`.

Current product roadmap: `docs/PROJECT_ROADMAP.md`.

For the next development cycle, audit current source and rank high-value, low-risk improvements in controller temperature/humidity behavior, configuration/UI, logging/history/plots, ML-shadow evaluation, and useful additional devices. Prefer sandbox/offline replay and simulation before physical experiments.

Canonical Shelly host is `{SHELLY_IP}` (`/rpc/Switch.GetStatus?id=0`). Do not guess or scan for a substitute address unless the operator explicitly changes it.

Work-mode boundary:

- sandbox/container first for analysis, simulation, replay, statistics and compute-heavy work;
- direct GitHub for bounded changes when exact diff plus focused verification is sufficient;
- Local Agent for Mac-specific toolchains/builds, local-network access, serial/USB/flash and physical hardware;
- Local Agent remains a deterministic executor; do not invoke local Codex.

"""
if "## Post-H product-development handoff\n" not in text:
    text = replace_once(text, anchor, post_h + anchor, "ARCHITECTURE_HANDOFF post-H insertion")
else:
    raise SystemExit("ARCHITECTURE_HANDOFF post-H section already exists")
path.write_text(text)

print("POST_H_DOCS_SYNC_READY")
