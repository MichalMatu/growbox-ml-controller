# Stage28B RF433 final evidence

Date: 2026-09-04
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`

## Scope

Stage28B qualified the native ESP-IDF RF433 transport on the CrowPanel HAT as a local radio loop only. It did **not** qualify or confirm the state of a 230 V socket/load.

Required evidence chain:

`requested FrameKey -> TX queued -> TX started -> TX completed -> RX capture -> decoded identical FrameKey -> classified SelfTx`

## Source milestones

Stage28A codec/temporal-policy source commit:

`ac29122cbcf9d155fd08baa0df1014d71f04c135` — native RF433 protocol codec and temporal classification.

Initial Stage28B native RMT loopback source commit:

`56813b27f6dc1f93d4899974ffd47a1528d8b6b8` — native ESP-IDF RMT TX/RX loopback backend.

Final qualified Stage28B source commit:

`a87169748ee2bd42bc4d35cfe3b2964b90f40eb8` — `Fix RF433 RMT receive timing limits`.

The final fix changed the RX path to the physically accepted configuration:

- RF433 TX GPIO: `8`;
- RF433 RX GPIO: `14`;
- TX/codec RMT resolution: `100 kHz`;
- RX RMT resolution: `1 MHz`;
- RX minimum accepted signal / glitch filter: `1,250 ns`;
- RX maximum signal / idle threshold: `12,000,000 ns`;
- RX durations are converted back to codec ticks before decode.

## Diagnostic history

The original receive configuration (`100 kHz`, min `20,000 ns`, max `300,000,000 ns`) failed at `rmt_receive()` with:

`ESP_ERR_INVALID_ARG (0x102)`.

A bounded range probe showed that changing only min/max within the original 100 kHz setup did not fix the argument rejection.

A 1 MHz probe with the still-invalid large filter range also failed at RX arm.

The accepted hardware configuration was then proven with:

- RX `1 MHz`;
- minimum signal `1,250 ns`;
- maximum signal `12 ms`.

That configuration passed the complete local RF loop and was then committed permanently.

## Final hardware recheck

Terminal task:

`20260904-growbox-stage28b-final-hardware-recheck-v1`

Firmware/source SHA under test:

`a87169748ee2bd42bc4d35cfe3b2964b90f40eb8`

Final RF evidence:

- requested code: `42330` / `0xA55A`;
- requested bits: `16`;
- requested protocol: `1`;
- requested repeat: `3`;
- TX queued: `1`;
- TX started: `1`;
- TX completed: `1`;
- RX captured: `1`;
- decode status: success;
- decoded code: `42330` / `0xA55A`;
- decoded bits: `16`;
- decoded protocol: `1`;
- estimated pulse: `350 us`;
- observed repeats: `2`;
- classification: `SelfTx`;
- RX arm errors: `0`;
- RX timeouts: `0`;
- RX decode failures: `0`;
- RX ambiguous: `0`;
- RX self-TX counter: `1`;
- RX interference: `0`;
- outputs remained `fake-locked`.

Terminal marker:

`STAGE28B_FINAL_HARDWARE_RECHECK_OK sha=a87169748ee2bd42bc4d35cfe3b2964b90f40eb8`

The strict 180-second Stage27 regression capture reported `violations: []` and preserved the existing SCD41, RTC, BLE and SD behavior.

## Evidence boundary

Stage28B proves local radio transport:

1. the backend accepted and completed a TX request;
2. the real RF receiver captured the over-air transmission;
3. the decoded `FrameKey` matched the request and was classified as `SelfTx`.

It does **not** prove that a mains socket changed state. A one-way 433 MHz socket can still miss a frame even when local RX hears it. Physical load state must remain a separate evidence level.

## Stage28B closure

Stage28A: DONE.

Stage28B: DONE and physically rechecked on commit `a87169748ee2bd42bc4d35cfe3b2964b90f40eb8`.

No Stage28B work should be repeated unless a later change touches the RF codec/RMT path or invalidates the Stage27 regression baseline.

Next gate: Stage28C — capture and freeze one original remote/socket pair ON/OFF before any semantic role mapping or real-load automation.
