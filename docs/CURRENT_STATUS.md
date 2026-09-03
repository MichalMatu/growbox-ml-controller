# Current controller status

Date: 2026-09-03
Development branch: `mvp/environment-controller`
Fresh-chat bootstrap: `docs/CONTINUATION_PLAN.md`
Final Stage27C evidence: `docs/STAGE27C_FINAL_EVIDENCE.md`
Validated milestone tag: `stage27c-validated-2026-09-03`

This is the short source of truth for the current climate-controller product path.

## Current state

The architecture through Stage26, native Stage27A/Stage27B implementation, and Stage27C CrowPanel real-input validation are complete for the requested scope.

The exact firmware physically qualified and used for the final continuous soak is:

`a5726b89e94b9ac628249b780d6548a692c3fd2c` — `Disable Stage27C CMD0 precondition by default`

Do not confuse later test/documentation commits or the milestone tag target with the firmware-under-test SHA.

## Proven Stage27C hardware path

Board and runtime:

- Elecrow CrowPanel ESP32-S3 N8R8;
- 100% native ESP-IDF v5.5.4;
- no Arduino component and no PlatformIO/Arduino migration;
- shared native I2C on GPIO21/GPIO38;
- SCD41 at `0x62`;
- DS3231 at `0x68`;
- one native NimBLE scanner for TP357 and Xiaomi/PVVX/BTHome using exact MAC identities;
- microSD primary storage with flash fallback/recovery support;
- e-paper/front-panel deferred;
- physical outputs/relays fake/locked.

Authoritative sensor mapping:

- TP357 exact-MAC device = primary inside temperature/RH;
- SCD41 = controller CO2 plus local/window temperature/RH diagnostics;
- Xiaomi/PVVX/BTHome exact-MAC device = nearby ambient temperature/RH through neutral `outside_*` fields;
- DS3231 = wall clock with availability kept separate from trusted validity.

No cross-sensor temperature/RH offsets are applied because the sensors are intentionally located in different physical positions.

## Storage qualification

The final storage path is qualified on real hardware:

- strict SD-primary operation passed;
- flash fallback with SD physically absent passed;
- live flash-to-SD recovery after hot insertion without reset passed;
- native CMD0 A/B passed;
- `GROWBOX_SD_CMD0_PRECONDITION=0` is the qualified default;
- storage mount/write/drop/skip counters remained clean in final qualification and soak evidence.

## Final Stage27C soak

Point 5 completed with seven accepted strict 5400-second chunks on one preserved MCU uptime sequence:

- accepted active capture: `37,800 s` = `10.5 h`;
- exact firmware SHA remained `a5726b89e94b9ac628249b780d6548a692c3fd2c`;
- final accepted uptime: `59,019,769 ms`;
- final SD record counter: `6717`;
- resets: `0`;
- serial disconnects: `0`;
- parser errors: `0`;
- SD mount/write/drop/skip failures: `0`;
- SCD41 read/invalid errors: `0`;
- BLE scanning/freshness diagnostics remained clean;
- RTC remained trusted;
- outputs remained fake/locked;
- internal heap, largest block, PSRAM and stack minima remained stable.

The isolated failed chunk-05 capture attempt is documented in `docs/STAGE27C_FINAL_EVIDENCE.md` and was not accepted into the final sequence.

## Fault/freshness qualification

Point 6 audited existing host coverage and added only the missing end-to-end stale-valid-measurement assertion.

Terminal validation:

- full portable host suite: `17/17` PASS;
- targeted Stage27C subset: `3/3` PASS.

Covered behavior includes exact BLE identity filtering, rejected/malformed packet diagnostics without refreshing valid freshness, stale measurement timeout behavior, BTHome encrypted/unsupported rejection semantics, and DS3231 OSF/trust handling.

## Controller policy boundary at closure

The hardware-neutral climate core remains authoritative.

- Rule is the authoritative applied policy.
- ML remains `MlShadow` only for real hardware use.
- `MlActive` is not qualified for real growbox actuation.
- deterministic arbitration and safety remain authoritative over every policy proposal.
- physical actuator endpoints were not qualified by Stage27C.
- e-paper/front-panel behavior was not qualified by Stage27C.

## Frozen milestone

Stage27C is frozen as tested and reviewed by the annotated Git tag:

`stage27c-validated-2026-09-03`

The tag freezes the repository closure state. The physically soaked firmware identity remains the separate SHA shown above.

Do not resume, extend or reinterpret Stage27C merely because the branch advances later. Reopen it only if a relevant firmware/runtime change invalidates the evidence or a new explicit goal deliberately expands the scope.

## Next work

No Stage27C work remains.

The next development goal must be opened explicitly as a new stage. The logical choices are:

1. qualify real physical actuator outputs beneath the existing `ClimateRoleDriver` / `MappedClimateRoleDriver` seam, one semantic role at a time, with Rule authoritative and fail-safe OFF behavior proven first;
2. add the deferred CrowPanel e-paper/front-panel UI without coupling it to controller correctness;
3. collect real operational traces with ML still shadow-only, then evaluate/retrain/re-qualify ML before any future `MlActive` hardware experiment.

For a fresh chat, start from `docs/CONTINUATION_PLAN.md` and `docs/STAGE27C_FINAL_EVIDENCE.md`. Do not restart Stage27A/B/C.
