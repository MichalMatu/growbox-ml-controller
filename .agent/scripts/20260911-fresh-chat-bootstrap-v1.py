from pathlib import Path

TRIGGER = "sprawdz w jakim miejscu jestesmy, napisz krotkie podsumowanie i kontynuujmy dalsza prace nad kodem"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


# AGENTS.md: make the minimal operator phrase a documented resume contract.
path = Path("AGENTS.md")
text = path.read_text()
anchor = "- Treat `192.168.0.16` as authoritative unless the operator explicitly changes it. Do not guess, substitute, or network-scan for a different Shelly address when this device is intended.\n\n### New chat bootstrap\n"
insert = f"""- Treat `192.168.0.16` as authoritative unless the operator explicitly changes it. Do not guess, substitute, or network-scan for a different Shelly address when this device is intended.

### Minimal fresh-chat resume command

The operator should not need to restate project history in a new chat. After pointing the chat at this repository, the following short instruction is sufficient:

`{TRIGGER}`

Treat that sentence, and obvious punctuation/Polish-diacritic variants of it, as an explicit request to restore current project context from repository evidence and continue development.

On that request:

1. Do not ask the operator to repeat previous work or paste an old handoff.
2. Read `AGENTS.md`, `docs/FRESH_CHAT_BOOTSTRAP.md`, `docs/CURRENT_STATUS.md`, `docs/ARCHITECTURE_HANDOFF.md`, `docs/CONTINUATION_PLAN.md`, and `docs/PROJECT_ROADMAP.md`.
3. Fetch the fresh `mvp/environment-controller` HEAD and inspect `agent-control:.agent/status/daemon.json` before editing or queueing work. If exact prior Local Agent evidence matters, read the relevant terminal result file.
4. Inspect the current source for the area that is actually next; repository code outranks stale remembered context.
5. Give the operator a short Polish summary: what is complete, where the branch currently is, what the most important remaining product work is, and what you will do next.
6. Then continue the next sensible code-development task without requiring another context-restoration prompt. Ask a clarification only when a real product decision cannot be inferred safely; do not ask merely to recover context.
7. Use sandbox/container first for analysis, replay, simulation, statistics, parsing, synthetic data and other compute that does not require the Mac or hardware. Use direct GitHub for bounded edits when sufficient. Use Local Agent only for Mac-local toolchains/builds/tests, local-network access, serial/USB/flash or physical devices.
8. Stage28E, A12, A13 and Physical H are complete. Do not reopen or rerun them by default; revisit qualification only when a later production-source change materially invalidates the qualified execution/safety/output path or when a new hardware qualification target is intentionally introduced.
9. Preserve standing safety and ownership invariants, including `OutputSupervisor` as the only normal production configured-output owner and ML as shadow/research-only.

### New chat bootstrap
"""
text = replace_once(text, anchor, insert, "AGENTS fresh-chat resume insertion")
path.write_text(text)


# Add a compact, dedicated resume entrypoint for fresh chats.
Path("docs/FRESH_CHAT_BOOTSTRAP.md").write_text(f"""# Fresh chat bootstrap

Updated: 2026-09-11
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Local Agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`

## Operator command

After pointing a new chat at this repository, the operator should be able to write only:

`{TRIGGER}`

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
{{
  "agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5",
  "work_branch": "mvp/environment-controller",
  "resources": []
}}
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
""")


# CONTINUATION_PLAN.md: make the dedicated bootstrap visible immediately.
path = Path("docs/CONTINUATION_PLAN.md")
text = path.read_text()
anchor = "Local Agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`\n\n## Read first in a new chat\n"
insert = f"""Local Agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`
Fresh-chat entrypoint: `docs/FRESH_CHAT_BOOTSTRAP.md`

## Minimal operator resume command

After selecting this repository in a new chat, the operator may simply write:

`{TRIGGER}`

That is sufficient authorization to restore context from repository evidence, provide a short status summary, and continue the next sensible development task. Do not ask the operator to repeat project history merely to resume work. Follow `docs/FRESH_CHAT_BOOTSTRAP.md`.

## Read first in a new chat
"""
text = replace_once(text, anchor, insert, "CONTINUATION_PLAN resume entrypoint")
text = replace_once(
    text,
    "1. `AGENTS.md`\n2. `docs/CURRENT_STATUS.md`\n3. `docs/ARCHITECTURE_HANDOFF.md`\n4. this file\n5. `docs/PROJECT_ROADMAP.md`",
    "1. `AGENTS.md`\n2. `docs/FRESH_CHAT_BOOTSTRAP.md`\n3. `docs/CURRENT_STATUS.md`\n4. `docs/ARCHITECTURE_HANDOFF.md`\n5. this file\n6. `docs/PROJECT_ROADMAP.md`",
    "CONTINUATION_PLAN read order",
)
path.write_text(text)


# CURRENT_STATUS.md: expose the fresh-chat entrypoint near the top-level status.
path = Path("docs/CURRENT_STATUS.md")
text = path.read_text()
anchor = "Latest handoff: `docs/ARCHITECTURE_HANDOFF.md`\n"
insert = "Latest handoff: `docs/ARCHITECTURE_HANDOFF.md`\nFresh-chat entrypoint: `docs/FRESH_CHAT_BOOTSTRAP.md`\n"
text = replace_once(text, anchor, insert, "CURRENT_STATUS fresh-chat entrypoint")
path.write_text(text)

print("FRESH_CHAT_BOOTSTRAP_PATCH_READY")
