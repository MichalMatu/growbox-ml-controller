# Fresh chat bootstrap

Updated: 2026-09-12
Repository: `MichalMatu/growbox-ml-controller`
Primary development branch after cleanup: `main`
Control branch: `agent-control`
Local Agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`

## Required restore flow

For a fresh chat, restore context from repository evidence instead of asking the operator to restate project history.

Read:

1. `AGENTS.md`
2. `docs/CURRENT_STATUS.md`
3. `docs/ARCHITECTURE.md`
4. `docs/PROJECT_ROADMAP.md`
5. `docs/CONTINUATION_PLAN.md`

Then fetch fresh `main` HEAD and `agent-control:.agent/status/daemon.json` before any write or Local Agent task.

Historical Stage27/Stage28 handoffs are evidence only unless a task specifically needs them.

## Current phase

Architecture cleanup and release-readiness hardening are complete. The active phase is normal product development, beginning with the roadmap's Controller behavior quality workstream.

Latest code-bearing bounded hardware-qualified identity: `e03763d019af405087a5fa9c6713a7165d2e623f`. It passed local software gates, GitHub CI #865, Sandbox Pack #63 and `20260912-final-main-hardware-qualification-v1`.

Do not confuse the current bounded safe real-input/fake-locked qualification with the historical full Physical H run, which remains attached to exact executable `02208d23f403bca3540dbbd652eb55703a044833`. Documentation-only descendants do not replace either executable identity.

## Work mode

- sandbox/container: analysis, replay, simulation, statistics;
- direct GitHub: bounded repository edits;
- Local Agent: Mac-local builds/toolchains, local network, serial/USB/flash and devices.

Never invoke local Codex from Local Agent.

Every Local Agent task uses:

```json
{
  "agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5",
  "work_branch": "main",
  "resources": []
}
```

Check the active Local Agent task before editing the same branch.

## Standing invariants

- deterministic Rule controller remains authoritative in production;
- ML remains shadow/research-only;
- `OutputSupervisor` is the only normal owner of configured physical outputs;
- unavailable transport must not fabricate execution truth;
- thermal safety remains authoritative;
- one-way RF completion is not physical acknowledgement;
- raw RF remains restricted to explicit `MaintenanceLocked` handling.

## Fixed physical boundaries

- Shelly: `192.168.0.16`
- Growbox serial: `/dev/cu.usbserial-1130`
- Never touch `/dev/cu.usbserial-10`
- Do not use `/dev/cu.usbserial-1120` without separate authorization
