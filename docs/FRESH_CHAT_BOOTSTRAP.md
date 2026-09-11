# Fresh chat bootstrap

Updated: 2026-09-11
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Local Agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`

## Operator command

After pointing a new chat at this repository, the operator should be able to write only:

`sprawdz w jakim miejscu jestesmy, napisz krotkie podsumowanie i kontynuujmy dalsza prace nad kodem`

Polish punctuation/diacritic variants with the same meaning should be treated equivalently.

## Required assistant behavior

On that command, restore context from repository evidence instead of asking the operator to restate project history.

Read, in this order:

1. `AGENTS.md`
2. `docs/CURRENT_STATUS.md`
3. `docs/ARCHITECTURE_HANDOFF.md`
4. `docs/CONTINUATION_PLAN.md`
5. `docs/PROJECT_ROADMAP.md`

Then:

1. Fetch fresh `mvp/environment-controller` HEAD.
2. Read fresh `agent-control:.agent/status/daemon.json` before any write or Local Agent task.
3. If a Local Agent task is active, inspect its exact repository/binding/task identity and do not race the same branch.
4. Read terminal `.agent/results/<task-id>.json` when a prior task result materially affects the next action.
5. Inspect current source for the next relevant product area; do not rely only on handoff prose.
6. Reply in Polish with a short status summary, normally covering: completed work, current branch/HEAD, current product-development focus, and the next recommended action.
7. Continue the next sensible development task immediately unless the operator explicitly asked only for discussion. Do not require a second prompt just to start work.

## Current project phase

The qualification workstream is complete:

`Stage27C FROZEN -> Stage28E A-G COMPLETE -> Output Execution A1-A12 COMPLETE -> A13 COMPLETE -> Physical H PASS -> NORMAL PRODUCT DEVELOPMENT`

Do not resume historical Stage28E/A12/A13/H work by default. Historical documents remain evidence, not the active workflow.

Current product development should prioritize practical growbox value, for example controller quality, configuration/UX, UI, logging/history/plots, ML-shadow data/evaluation, or additional devices where justified by a real use case.

## Work mode

### Sandbox first

Use the sandbox/container aggressively for analysis and computation that does not require the physical Mac or devices: code analysis, telemetry parsing, replay, simulations, controller experiments, synthetic data, statistics and comparison tooling. Do not consume Local Agent/Mac execution merely as generic compute when sandbox can do the work.

### Direct GitHub

Use direct GitHub edits for bounded source/config/docs changes when exact diff plus focused checks/CI provide sufficient evidence.

### Local Agent

Use Local Agent for Mac-specific execution: local toolchains/builds/tests, pre-commit/pre-push, local-network Shelly access, serial/USB/flash and physical hardware. ChatGPT remains the planner; Local Agent is a deterministic executor. Never launch local Codex.

Every Local Agent task must use exactly:

```json
{
  "agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5",
  "work_branch": "mvp/environment-controller",
  "resources": []
}
```

## Fixed hardware/network facts

- Canonical Shelly IP: `192.168.0.16`
- Shelly status RPC: `http://192.168.0.16/rpc/Switch.GetStatus?id=0`
- Growbox serial: `/dev/cu.usbserial-1130`
- Never touch `/dev/cu.usbserial-10`
- Do not use `/dev/cu.usbserial-1120` without separate authorization

## Standing invariants

- deterministic rule controller remains authoritative;
- ML remains shadow/research-only;
- `OutputSupervisor` remains the only normal production owner of configured physical outputs;
- thermal safety remains authoritative;
- one-way RF completion is transport evidence, not physical acknowledgement;
- raw RF remains restricted to explicit `MaintenanceLocked` handling.
