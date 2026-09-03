# Fresh-context continuation plan

Updated: 2026-09-03
Work branch: `mvp/environment-controller`
Control branch: `agent-control`

## Primary bootstrap

The authoritative handoff for the next ChatGPT conversation is now:

`/continuation.md`

Read that file first. It contains:

- the frozen Stage27C baseline and exact tested firmware identity;
- the `stage27c-validated-2026-09-03` milestone boundary;
- the Stage28 RF433 physical-actuator roadmap;
- the pinned `MichalMatu/esp32s3_LiteGraph` RF433 donor revision and relevant files;
- the TX -> air -> RX self-loop qualification plan;
- the Local Agent and Local Chat Bridge operating rules;
- exact first actions for a fresh conversation.

This file remains only as a compatibility pointer because older handoffs and chats refer to `docs/CONTINUATION_PLAN.md`.

## Frozen Stage27C status

Stage27C CrowPanel real-input validation is complete. Do not resume or extend it under the old goal.

Frozen annotated tag:

`stage27c-validated-2026-09-03`

Frozen coherent Stage27C closure commit:

`b418520090d0feadc005701092c1b7ed3384afbf`

Exact physically qualified firmware:

`a5726b89e94b9ac628249b780d6548a692c3fd2c`

Detailed evidence remains in:

- `docs/STAGE27C_FINAL_EVIDENCE.md`;
- `docs/CURRENT_STATUS.md`;
- `docs/STAGE27C_CROWPANEL_BRINGUP.md`.

Historical pre-soak/soak handoffs are records only and must not be interpreted as instructions to restart Stage27C.

## New active direction

The next explicit product direction is Stage28: native ESP-IDF RF433 actuator bring-up using the transmitter and receiver already connected to the CrowPanel HAT and the user's 433 MHz sockets.

Start from `/continuation.md`; do not invent a new Stage28 plan from memory.
