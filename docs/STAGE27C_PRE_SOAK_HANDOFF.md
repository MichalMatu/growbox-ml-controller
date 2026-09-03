# Stage27C pre-soak handoff

Date: 2026-09-03
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Local Agent repository id: `growbox-ml-controller`
Agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`

This is the current Stage27C continuation document after completion of the final pre-soak hardware/storage qualification. It supersedes the older operational state in `docs/STAGE27C_CONTINUATION_HANDOFF.md`; keep that older file only for historical evidence from the earlier long-soak session.

## Current stop point

Stage27C is **ready for the separately approved overnight/final long soak** on the final firmware revision.

The overnight/final long soak has **not** been started. Do not start it automatically. It requires explicit user approval in a separate step.

No further pre-soak hardware gate is pending.

## Final firmware-under-test identity

`a5726b89e94b9ac628249b780d6548a692c3fd2c` — `Disable Stage27C CMD0 precondition by default`

This is the exact firmware revision flashed and validated by the final strict SD-primary gate.

Documentation-only commits created after this SHA may advance `mvp/environment-controller`. Do not confuse a later documentation HEAD with the firmware revision physically validated on the CrowPanel.

## Final hardware state

- board: Elecrow CrowPanel ESP32-S3 2.9-inch, N8R8;
- verified CH340 serial path during qualification: `/dev/cu.usbserial-1130`;
- MCU: ESP32-S3 QFN56 rev0.2;
- PSRAM: 8 MB;
- microSD: inserted at the end of qualification and intended to remain inserted for normal SD-primary operation;
- I2C: SDA GPIO21, SCL GPIO38;
- SCD41: `0x62`;
- DS3231: `0x68`;
- SD SPI: MOSI GPIO40, MISO GPIO13, SCLK GPIO39, CS GPIO10, power GPIO42;
- outputs: fake/locked;
- controller authority: Rule;
- ML: shadow-only;
- e-paper/front-panel: out of scope.

Rediscover the serial port before future local execution; do not assume the macOS device suffix is permanent.

## Completed pre-soak storage gates

### SD-primary baseline

Task: `20260903-growbox-stage27c-sd-primary-smoke-v2`

Passed strict physical SD-primary validation on firmware `0cbd181f46661423d1983ad1805f11d6fecc5128` with zero SD mount/write errors, zero queue drops/skips, healthy SCD41/RTC/BLE, fake-locked outputs, and no serial disconnects.

### Flash fallback with SD absent

Task: `20260903-growbox-stage27c-flash-fallback-v3`

Passed with the microSD physically removed. Expected cold-start sequence was observed:

- first diagnostic row: `storage_backend=none` before the storage worker consumes the first enqueued snapshot;
- all later rows: `storage_backend=flash`;
- `storage_flash_mounted=1` after startup transition;
- `storage_sd_mounted=0` throughout;
- `storage_fallbacks=1`;
- flash mount errors: 0;
- storage write errors: 0;
- queue drops: 0;
- skipped records: 0;
- persisted record count advanced.

The initial `none` row is expected runtime ordering, not a firmware failure.

### Live flash-to-SD recovery

Task: `20260903-growbox-stage27c-flash-to-sd-recovery-v1`

The microSD was hot-inserted while the device continued running on flash fallback. No reset or `esptool` probe was used before the recovery capture.

Passed with:

- stable SD from the first captured row after insertion;
- `storage_sd_recoveries=1`;
- retained `storage_fallbacks=1`;
- `storage_sd_mounted=1`;
- `storage_flash_mounted=0` after recovery;
- records written `24 -> 43`;
- storage write errors: 0;
- queue drops: 0;
- skipped records: 0;
- resets: 0;
- serial disconnects: 0.

The recovery happened before the serial capture began, which is acceptable because the retained recovery counter proves the live flash-to-SD transition occurred without reset.

### CMD0 compatibility A/B

Task: `20260903-growbox-stage27c-cmd0-native-ab-v1`

The firmware was built/flashed with:

`GROWBOX_SD_CMD0_PRECONDITION=0`

The native no-shim path passed strict SD-required hardware validation:

- `passed=true`;
- 18 records;
- one allowed startup `sd_unmounted` diagnostic row;
- zero resets;
- zero serial disconnects;
- no strict violations.

Therefore `scripts/stage27c_crowpanel.sh` now defaults `GROWBOX_SD_CMD0_PRECONDITION=0`. The compatibility precondition remains available only as an explicit override if future hardware evidence requires it.

### Final default-config SD-primary gate

Task: `20260903-growbox-stage27c-final-sd-primary-v1`
Firmware SHA: `a5726b89e94b9ac628249b780d6548a692c3fd2c`

The helper was run with its new default CMD0 setting and the exact final firmware SHA. Build, flash, and 300-second strict `--require-sd` validation all passed.

Terminal marker:

`STAGE27C_FINAL_SD_PRIMARY_OK`

Final key metrics:

- records: 30;
- last SD records written: 34;
- minimum internal heap: 231780 B;
- minimum free stack: 10884 B;
- SD mount errors: 0;
- SD write errors: 0;
- SD queue drops: 0;
- SD records skipped: 0;
- resets: 0;
- serial disconnects: 0;
- violations: none.

## Final CI evidence

For firmware SHA `a5726b89e94b9ac628249b780d6548a692c3fd2c`:

- GitHub Actions `CI`, run `33714883003`: `success`;
- GitHub Actions `Stage27C Storage Gate`, run `33714883009`: `success`.

Both workflows were triggered by the final default CMD0 configuration commit.

## Historical long-soak evidence

The older Stage27C session contains two valid ~90-minute soak chunks on firmware `cf957a7649ec02835f724951d34f0b408f5f6de2` and one intentionally interrupted task. That evidence is documented in `docs/STAGE27C_CONTINUATION_HANDOFF.md`.

Do not merge that historical uptime into a claim of continuous long-soak coverage for final firmware `a5726b89e94b9ac628249b780d6548a692c3fd2c`.

## Exact next action

Do nothing automatically.

If and only if the user explicitly approves the overnight/final long soak:

1. fetch fresh work-branch HEAD and daemon/result evidence;
2. distinguish the docs HEAD from the flashed firmware identity `a5726b89e94b9ac628249b780d6548a692c3fd2c`;
3. verify the board is still running the expected final firmware before claiming continuity;
4. run the approved bounded long-soak plan without changing control behavior;
5. keep microSD primary, outputs fake/locked, Rule authoritative, ML shadow-only, and e-paper out of scope;
6. use new immutable Local Agent task ids with exactly the bound agent id above;
7. inspect terminal results before any acceptance claim.

If the board has reset or been reflashed before the long soak, start a fresh soak baseline and document the session break instead of pretending continuity.

## Stop condition

The active goal that led to this handoff is complete at:

**ready for overnight soak**

Do not cross that boundary without explicit user approval.
