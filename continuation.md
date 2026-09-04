# Growbox continuation handoff

Date: 2026-09-04
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Control branch: `agent-control`

This is the primary bootstrap for a fresh conversation. Read it first, then verify the fresh work-branch HEAD and `agent-control:.agent/status/daemon.json` before doing work.

## Frozen baseline

Stage27C real-input qualification is complete and remains frozen.

- validated tag: `stage27c-validated-2026-09-03`
- Stage27C closure commit: `b418520090d0feadc005701092c1b7ed3384afbf`
- physically soaked Stage27C firmware: `a5726b89e94b9ac628249b780d6548a692c3fd2c`
- Rule authoritative
- ML shadow-only
- physical outputs remain fake/locked unless a later explicit gate says otherwise

Do not restart Stage27A/B/C without new evidence that later code invalidated them.

## Stage28 status

**Stage28A DONE -> Stage28B DONE -> Stage28C DONE -> pre-Stage28D golden gate COMPLETE -> Stage28D NOT STARTED**

### Stage28A

Native RF433 codec and temporal classification are complete. Milestone: `ac29122cbcf9d155fd08baa0df1014d71f04c135`.

### Stage28B

Native ESP-IDF RMT TX/RX local loopback is complete. Historical Stage28B qualified milestone: `a87169748ee2bd42bc4d35cfe3b2964b90f40eb8`.

### Stage28C

One remote/socket pair is frozen under the neutral hardware label `remote_socket_1`:

- ON: decimal `906118656`, hex `0x36024600`
- OFF: decimal `1040336384`, hex `0x3E024600`
- bit length: `32`
- protocol: `2`
- pulse: `575 us`
- validated transmit repeat: `10`

`repeat=10` is a physically proven reliable TX setting. It is not claimed to be the exact measured repeat count of the original handheld remote.

The final known-pair hardware recheck was performed on source `2cb4b8dffb0835460a9e9ba920d9bd888c99d992` and required exact ON/OFF decode, TX lifecycle completion, RX capture, no RX timeout, `SelfTx` classification and `outputs=fake-locked`. The board was restored to passive RX-only afterwards.

The identity/config freeze commit is `b3e90c92dd39c50c23ed618aba47e9fe8ddf26ec`.

Detailed closure: `docs/STAGE28C_FINAL_EVIDENCE.md`.

## Current RF implementation after golden hardening

Post-Stage28C software hardening has advanced the source beyond the physical recheck SHA without changing the frozen RF identity:

- `a215cae35bbdee155a40fce0c7481a87191a3716` — split real-input runtime responsibilities into Stage27 runtime adapters, telemetry reporter and Stage28 RF diagnostics; `ClimateV6RealInputRuntime.cpp` reduced to orchestration.
- `60da0a4d2a99f3045596b6a8a8bf362a0c6e1aca` — deduplicated the RMT receive path and moved the hardware-qualified receive envelope into a host-testable contract.

Current Stage28C receive contract:

- RMT TX/codec resolution: `100 kHz`
- RMT RX resolution: `100 kHz`
- RX minimum signal / glitch threshold: `10 us` (`10,000 ns`)
- RX maximum signal / idle threshold: `20 ms` (`20,000,000 ns`)
- TX GPIO8, RX GPIO14
- raw RX capacity remains 256 symbols
- a 32-bit protocol-2 frame occupies 33 symbols; seven complete repeats fit, ten complete repeats exceed one raw capture buffer

The 20 ms idle threshold was physically qualified because 300 ms did not terminate one-shot capture reliably in the same receiver environment. Do not revert to the old Stage28B `1 MHz / 1.25 us / 12 ms` settings.

## Evidence boundaries

Keep these distinct:

1. TX request accepted/completed.
2. Local RF receiver captured and decoded the expected frame (`SelfTx`).
3. Real remote socket/load state changed.

Stages 28B/28C prove levels 1 and 2 for the qualified path and record a reliable TX setting. They do not turn local self-RX into physical socket-state acknowledgement.

## Golden gate complete

The clean golden firmware/source checkpoint is `316b58e76de609069ddbf2667fe86f6218fb2143`. It passed the complete software gate and the same exact SHA passed a 5400-second strict real-hardware soak with 526 records, zero resets/disconnects/parse errors/violations, healthy sensor freshness, stable memory, continuous SD progress, outputs fake-locked and no RF433 transmit observed. Full evidence is in `docs/PRESTAGE28D_GOLDEN_CHECKPOINT.md`.

Stage28D is intentionally NOT STARTED. No later semantic integration is implied by this checkpoint.

## Local Agent binding

Every task must contain exactly:

`"agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5"`

Use `resources: []` for software-only work and `resources: ["board:growbox-s3"]` for USB/flash/serial/hardware work. Work only on this repository and `mvp/environment-controller` unless the operator explicitly changes scope.
