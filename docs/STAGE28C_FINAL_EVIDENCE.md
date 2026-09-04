# Stage28C final evidence — one learned RF433 remote/socket pair

Stage28C is frozen for exactly one original remote/socket pair under the neutral hardware label `remote_socket_1`.

## Frozen hardware identity

| command | decimal code | hex code | bits | protocol | pulse | validated TX repeat |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| ON | 906118656 | `0x36024600` | 32 | 2 | 575 us | 10 |
| OFF | 1040336384 | `0x3E024600` | 32 | 2 | 575 us | 10 |

`repeat=10` is the physically validated transmit setting that reliably controls the paired socket. It is deliberately recorded as an effective TX setting; Stage28C does not claim that the exact repeat count emitted by the original handheld remote was measured.

## Receiver hardening and physical evidence

Hardware-qualified source before this freeze: `2cb4b8dffb0835460a9e9ba920d9bd888c99d992`.

The final hardware recheck on that exact source required, independently for ON and OFF:

- TX queued, started and completed;
- RX capture completed without timeout;
- decoded code exactly matched the requested code;
- 32 bits and protocol 2 matched exactly;
- at least one repeat was observed;
- temporal classification was `SelfTx` for the local TX→RX qualification;
- output path remained `fake-locked`.

The task completed with marker:

`STAGE28C_FINAL_KNOWNPAIR_DONE sha=2cb4b8dffb0835460a9e9ba920d9bd888c99d992 on=906118656 off=1040336384 bits=32 protocol=2 pulse_us=575 tx_repeat=10 safe_rx_restored=1`

The board was finally reflashed into passive RX-only diagnostics with auto-transmit disabled.

## Boundary

The frozen identity is hardware/config only. No semantic role (for example `exhaust_fan`) is assigned here, no Rule/ML mapping is introduced, and this freeze is not physical socket-state acknowledgement. Stage28C does not authorize unattended mains-load control.
