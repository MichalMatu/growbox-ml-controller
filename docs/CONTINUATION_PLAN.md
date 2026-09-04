# Fresh-context continuation plan

Updated: 2026-09-04
Work branch: `mvp/environment-controller`
Control branch: `agent-control`

## Primary bootstrap

The authoritative handoff for the next ChatGPT conversation is:

`/continuation.md`

Read that file first.

It now records:

- the frozen Stage27C baseline;
- completed Stage28A native RF433 codec/temporal work;
- completed Stage28B native ESP-IDF RMT loopback qualification;
- final qualified RF source SHA `a87169748ee2bd42bc4d35cfe3b2964b90f40eb8`;
- final RX timing configuration (`1 MHz`, `1,250 ns`, `12 ms`);
- final hardware recheck evidence;
- the strict boundary between `SelfTx` evidence and real socket/load state;
- the exact Stage28C next gate;
- Local Agent binding and fresh-context startup rules.

Detailed Stage28B closure evidence:

`docs/STAGE28B_FINAL_EVIDENCE.md`

Short current source of truth:

`docs/CURRENT_STATUS.md`

This file remains a compatibility pointer because older chats and handoffs refer to `docs/CONTINUATION_PLAN.md`.

## Frozen Stage27C status

Stage27C CrowPanel real-input validation is complete and must not be restarted under the old goal.

Frozen annotated tag:

`stage27c-validated-2026-09-03`

Frozen coherent closure commit:

`b418520090d0feadc005701092c1b7ed3384afbf`

Exact physically qualified Stage27C firmware:

`a5726b89e94b9ac628249b780d6548a692c3fd2c`

## Stage28 transition

Stage28A: DONE.

Stage28B: DONE and physically rechecked.

Stage28C: NEXT.

Stage28C must capture and freeze one original remote/socket ON/OFF pair before semantic role integration or unattended real-load control.

Start from `/continuation.md`; do not reconstruct or restart Stage28A/28B from old chat memory.
