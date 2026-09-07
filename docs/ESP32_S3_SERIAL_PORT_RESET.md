# ESP32-S3 serial-port open reset behavior

Updated: 2026-09-07

## Scope

This note applies to the Growbox CrowPanel ESP32-S3 hardware used by this repository and to runtime validation through:

`/dev/cu.usbserial-1130`

It records a hardware/test-harness behavior that must be considered when interpreting Stage28E and later serial-monitor evidence.

## Verified behavior

Opening the serial monitor / USB-UART port can reset the ESP32-S3 before observation begins.

This is expected on ESP32-family boards that use the USB-UART modem-control lines for automatic reset/bootloader entry. Espressif documents that `DTR` and `RTS` from USB-UART bridges such as FTDI, CP210x, or CH340x are connected through the auto-reset circuit to `GPIO0` and `EN` (`CHIP_PU`), and that some operating systems, drivers, or serial terminal programs may change those modem-control lines when opening the serial port.

Official references:

- https://docs.espressif.com/projects/esptool/en/latest/esp32s3/advanced-topics/boot-mode-selection.html
- https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/get-started/flashing-troubleshooting.html

## Repository hardware evidence

Stage28E Phase G reproduced this behavior on the Growbox board.

Long-soak task:

`20260907-growbox-stage28e-phase-g-long-soak-v1`

Reanalysis task:

`20260907-growbox-stage28e-phase-g-long-soak-reanalysis-v1`

Exact firmware SHA:

`389453882f0e0d2209c5bdece7eaf443895aa7ba`

Measured evidence:

- command wall time: `736.476 s`;
- final firmware uptime: `733249 ms`;
- startup difference: `3.227 s`;
- stable boot ID after startup: `54f2ecb1`;
- reset reason after startup: `1`;
- maximum observed heartbeat sequence: `72`;
- maximum heap-integrity check: `12`;
- final internal free/min/largest: `223792 / 223260 / 180224 B`;
- final PSRAM free/largest: `8358772 / 8257536 B`;
- main worst observed HWM: `7064 B` free;
- `stage27_store` worst observed HWM: `1884 B` free;
- final storage records observed in retained evidence: `83`;
- no queue drops, storage write errors, unexpected storage fallback, heap-integrity failure, coredump, Guru Meditation, corrupt heap, stack-canary failure, watchdog reset, or arbiter counter regression after the startup reset;
- outputs remained `fake-locked`;
- Shelly master remained ON, reanalysis median `65.10 W`.

The wall-time versus firmware-uptime difference proves that the reset was confined to the serial-open/startup boundary. A reset later in the approximately 12-minute soak would have made final firmware uptime materially smaller than wall time.

The same class of startup reset was also observed when Python configured `DTR=False` and `RTS=False` before opening the port. Therefore, on this exact board/adapter/driver path, pre-setting the modem-control values in pyserial is not sufficient evidence that opening the port will be reset-free.

## Mandatory interpretation rule for future runtime tests

Do **not** classify a ROM boot marker or uptime restart caused by opening `/dev/cu.usbserial-1130` as a spontaneous firmware failure.

For any runtime/soak harness that opens the serial port:

1. Open the port first.
2. Allow a short startup grace period (normally about 5 seconds is sufficient for this observed path).
3. Obtain a fresh `status` snapshot after the port is open.
4. Treat that post-open snapshot as the observation baseline: record firmware SHA, boot ID, reset reason, uptime, arbiter instance/construction state, memory, and output mode.
5. Start the bounded runtime/soak timer only after this baseline is established.
6. Ignore only the reset that is attributable to the port-open boundary before the baseline.
7. After the baseline, any new ROM boot marker, boot-ID change, uptime regression/restart, runtime lifecycle entry, arbiter reconstruction, crash/coredump, or reset evidence is a real runtime event and must fail the gate unless explicitly expected by that test.

A test must never hide or discard a reset that occurs after the post-open baseline.

## Harness guidance

Preferred pattern for Stage28E and later device tests:

```text
open serial port
-> tolerate/record port-open reset
-> wait for boot/runtime stabilization
-> request status
-> establish boot/session baseline
-> start observation window
-> fail on any later reset/session/lifecycle change
```

Do not use a blanket assertion such as `ESP-ROM must never appear anywhere in the complete serial capture` when the capture begins by opening the serial device. That assertion produces a false negative on this hardware.

When continuity across an already-running boot must be proven without allowing a port-open reset, use a monitoring path that is already attached before the measurement window or a hardware/adapter configuration demonstrated not to toggle the reset circuitry. Do not assume pyserial modem-control settings alone provide that guarantee on this board.
