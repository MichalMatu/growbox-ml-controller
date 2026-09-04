# Fresh-context continuation plan

Updated: 2026-09-04
Work branch: `mvp/environment-controller`
Control branch: `agent-control`

The authoritative detailed handoff is `/continuation.md`.

Current transition:

**Stage28A DONE -> Stage28B DONE -> Stage28C DONE -> pre-Stage28D golden gate COMPLETE -> Stage28D IN PROGRESS**

Stage27C remains frozen. Stage28C has frozen exactly one neutral RF433 remote/socket identity; detailed evidence is in `docs/STAGE28C_FINAL_EVIDENCE.md`.

The exact Golden firmware/source checkpoint is `316b58e76de609069ddbf2667fe86f6218fb2143`. That exact SHA passed the complete software gate and a strict 5400-second real-hardware soak. Later documentation-only commits may advance branch HEAD without becoming separately hardware-soaked firmware SHAs.

Current RF receive settings remain `100 kHz`, `10 us` minimum signal and `20 ms` idle/max signal. Do not reconstruct the active implementation from historical Stage28B receive values.

The pre-Stage28D hardening/golden work is complete. There is no unfinished overnight Local Agent task.

Stage28D was explicitly started by the operator. Semantic role-to-endpoint mapping is fail-closed, and the second bounded software slice adds stable endpoint ID `1` for the neutral frozen `remote_socket_1` hardware registry. The operator has now explicitly identified that physical pair as the fan socket, but no semantic `ClimateActuatorRole` is assigned yet.

The quick hardware/code register is `docs/RF433_DEVICE_CODES.md`. It now records all three captured identities:

- lamp: ON `235030016`, OFF `16926208`;
- fan / `remote_socket_1`: ON `906118656`, OFF `1040336384`;
- humidifier: ON `637683200`, OFF `771900928`.

All are 32-bit protocol 2 captures with `560 us` captured pulse and requested ESP TX repeat `10`. Preserve the separate Stage28C evidence that the fan pair was physically reliable with `575 us` and repeat `10`; do not rewrite that historical qualification as `560 us` until the new physical recheck proves it.

Current physical sensor placement: TP357 BLE inside growbox, Xiaomi BLE outside growbox, directly connected ESP32 sensors inside growbox.

The next bounded hardware step is manual ESP-to-socket ON/OFF validation for lamp, fan and humidifier, using physical device response as the acceptance criterion. Local TX completion or `SelfTx` alone is insufficient.

Keep the real runtime fake-locked for unattended operation. Do not introduce unattended 230 V control or physical-state acknowledgement semantics during the manual validation step.
