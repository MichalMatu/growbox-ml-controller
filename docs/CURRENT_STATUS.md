# Current controller status

Date: 2026-09-04
Development branch: `mvp/environment-controller`
Primary fresh-chat bootstrap: `/continuation.md`
Stage28B evidence: `docs/STAGE28B_FINAL_EVIDENCE.md`
Stage27C frozen evidence: `docs/STAGE27C_FINAL_EVIDENCE.md`
Validated Stage27C milestone tag: `stage27c-validated-2026-09-03`

This is the short source of truth for the current climate-controller product path.

## Current state

Stage27C real-input qualification is complete and frozen. Stage28A and Stage28B RF433 work are also complete.

Current transition:

**Stage28A DONE -> Stage28B DONE -> Stage28C NEXT**

The final qualified Stage28B RF source commit is:

`a87169748ee2bd42bc4d35cfe3b2964b90f40eb8` — `Fix RF433 RMT receive timing limits`

Documentation-only commits may advance the work-branch HEAD after this SHA. Do not confuse later handoff/documentation commits with the firmware/source SHA physically rechecked for Stage28B.

## Frozen Stage27C baseline

Exact Stage27C firmware used for the final long qualification:

`a5726b89e94b9ac628249b780d6548a692c3fd2c`

Frozen milestone tag:

`stage27c-validated-2026-09-03`

Validated hardware/runtime baseline:

- Elecrow CrowPanel ESP32-S3 N8R8;
- native ESP-IDF v5.5.4;
- SCD41 + DS3231 on shared I2C GPIO21/GPIO38;
- native BLE exact-identity inputs;
- microSD primary storage with flash fallback/recovery;
- Rule authoritative;
- ML shadow-only;
- physical outputs fake/locked.

Stage27C final accepted soak remains 10.5 h active strict SD-primary capture with zero resets, serial disconnects, parser failures or storage/sensor regressions in the accepted sequence. Do not reopen Stage27C unless later changes invalidate its evidence.

## Stage28A — complete

Native RF433 protocol/temporal layer is implemented under `src/climate/rf433/`.

Stage28A source milestone:

`ac29122cbcf9d155fd08baa0df1014d71f04c135`

The implementation is native C++/ESP-IDF and preserves the hardware-neutral semantic output boundary.

## Stage28B — complete

Native ESP-IDF RMT TX/RX loopback is implemented.

Initial RMT source milestone:

`56813b27f6dc1f93d4899974ffd47a1528d8b6b8`

Final qualified source milestone:

`a87169748ee2bd42bc4d35cfe3b2964b90f40eb8`

Final RF hardware configuration:

- TX GPIO8;
- RX GPIO14;
- TX/codec RMT resolution `100 kHz`;
- RX RMT resolution `1 MHz`;
- RX minimum signal/glitch filter `1,250 ns`;
- RX maximum signal/idle threshold `12 ms`;
- RX pulse durations converted back to codec ticks before decode.

The original receive configuration failed at `rmt_receive()` with `ESP_ERR_INVALID_ARG (0x102)`. Bounded hardware diagnostics isolated the valid RX configuration above.

Final terminal hardware task:

`20260904-growbox-stage28b-final-hardware-recheck-v1`

The final recheck passed the complete local-radio chain:

`0xA55A/16/protocol1 requested -> TX queued -> TX started -> TX completed -> RX captured -> exact decode -> SelfTx`

At final acceptance:

- RX arm errors `0`;
- RX timeouts `0`;
- RX decode failures `0`;
- RX ambiguous `0`;
- RX interference `0`;
- outputs `fake-locked`;
- strict 180-second Stage27 regression `violations: []`.

See `docs/STAGE28B_FINAL_EVIDENCE.md` for the detailed closure record.

## Evidence boundary

Stage28B proves the local RF path, not the physical state of a mains socket.

These evidence levels remain separate:

1. TX request accepted/completed;
2. local receiver captured/decoded the expected frame (`SelfTx`);
3. actual socket/load changed state.

Level 3 still requires explicit physical validation.

## Next work — Stage28C

The exact next gate is to learn and freeze one original remote/socket pair.

For one socket only, capture and record:

- ON code;
- OFF code;
- bit length;
- protocol;
- pulse timing;
- repeat behavior;
- stable device/role label.

Do not map the socket into a climate semantic role during Stage28C. Keep RF identity in the hardware/config layer.

After Stage28C:

- Stage28D: semantic integration, `exhaust_fan` first, `humidifier` second; lamp separate;
- Stage28E: fail-safe/recovery and correct confirmation semantics;
- Stage28F: bounded real socket/load validation and one-role soak.

Rule remains authoritative and ML remains shadow-only throughout these gates.

## Fresh-context start

For a new ChatGPT conversation:

1. read `/continuation.md` first;
2. read `docs/STAGE28B_FINAL_EVIDENCE.md`;
3. fetch fresh work-branch HEAD and Local Agent daemon state;
4. verify exact Growbox repository/binding and daemon `idle`;
5. start Stage28C only — do not repeat Stage28A/28B without evidence that later changes invalidated them.
