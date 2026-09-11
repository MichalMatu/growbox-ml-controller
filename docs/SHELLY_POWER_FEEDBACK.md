# Shelly power-feedback reference

Updated: 2026-09-05

## Available device

The current growbox test setup has a Shelly Plug S Gen3 reachable from the Local Agent host at:

`http://192.168.0.16`

Read-only RPC access was physically/network verified from the Local Agent host on 2026-09-05.

Observed device identity:

- model: `S3PL-00112EU`;
- generation: 3;
- application: `PlugSG3`;
- firmware observed during qualification: `1.7.5`;
- RPC authentication was disabled at the time of qualification.

Verified read-only RPC endpoints:

- `/rpc/Shelly.GetDeviceInfo`;
- `/rpc/Switch.GetStatus?id=0`.

`Switch.GetStatus` exposes the measurements needed for growbox feedback, including relay state, active power (`apower`), voltage, current, accumulated energy and plug temperature.

At the qualification read the relay was OFF and the plug reported `0.0 W` at approximately `244.4 V`. These values are evidence of the read-only probe only, not fixed operating values.

## RPC usage from the Local Agent host

Read device identity:

```sh
curl -fsS --max-time 5 http://192.168.0.16/rpc/Shelly.GetDeviceInfo
```

Read relay state and power telemetry:

```sh
curl -fsS --max-time 5 'http://192.168.0.16/rpc/Switch.GetStatus?id=0'
```

The most important response fields are:

- `output`: physical Shelly relay state;
- `apower`: active power in watts;
- `voltage`: mains voltage;
- `current`: current in amperes;
- `aenergy.total`: accumulated consumed energy;
- `temperature.tC`: Shelly internal temperature.

Control the Shelly relay through the official `Switch.Set` RPC method:

```sh
curl -fsS -X POST \
  -H 'Content-Type: application/json' \
  -d '{"id":1,"method":"Switch.Set","params":{"id":0,"on":true},"tag":"growbox"}' \
  http://192.168.0.16/rpc
```

Use `"on":false` for OFF. After every write, read `Switch.GetStatus?id=0` and verify the returned `output` state instead of assuming the write succeeded.

Do not use `Switch.Toggle` in automated control because an explicit requested state is safer and deterministic.

## Intended growbox role

The Shelly can be installed upstream of the current growbox loads and used as an independent power-feedback channel. It can remain upstream of a power strip: individual loads can still be identified from characteristic changes in total active power.

The core measurement is a delta, not an absolute total:

`device power contribution ~= stable power after command - stable power before command`

For an ON transition:

`delta_on_w = median(apower_after_on) - median(apower_before_on)`

For the matching OFF transition:

`delta_off_w = median(apower_before_off) - median(apower_after_off)`

The ON and OFF deltas should be similar in magnitude. Agreement between both directions increases confidence that the RF-controlled load really changed state.

During actuator calibration, measure the stable power delta for:

- all controlled loads OFF (baseline);
- lamp only ON;
- exhaust fan only ON;
- humidifier only ON;
- useful combinations of the above.

Use multiple Shelly samples before and after each transition, allow a short settling interval, and use a median/trimmed estimate rather than one instantaneous reading. Record mains voltage with each calibration because power can vary with supply voltage.

The resulting characteristic wattage ranges can provide physical feedback after an RF command. For example, an RF `lamp ON` transmission followed by the calibrated positive lamp power delta is strong evidence that the lamp physically turned on. An RF TX completion followed by no expected power change is evidence of a failed or ineffective physical state transition.

The power-feedback path should therefore be modeled as:

`requested actuator state -> RF command -> expected power delta/signature -> Shelly measured delta -> physical-state confidence / anomaly`

Do not require exact wattage equality. Use calibrated ranges/tolerances and settling time because mains voltage, lamp driver behavior, fan load and humidifier duty can vary.

A shared power strip is acceptable. If other constant loads are present, they become part of the baseline and cancel out in the before/after delta. If another load changes during the observation window, mark that sample ambiguous and do not use it as actuator-state confirmation.

## Calibration sequence

The safe reference sequence is:

1. ensure the Shelly master is ON and read a stable baseline;
2. send explicit RF OFF to lamp, fan and humidifier, then measure the all-controlled-loads-OFF baseline;
3. for each device separately: collect pre-transition samples, send RF ON, wait for settling, collect post-ON samples, send RF OFF, wait for settling, collect post-OFF samples;
4. derive characteristic ON and OFF power deltas and an initial tolerance band;
5. end with lamp OFF, fan OFF and humidifier OFF, then record the final Shelly status.

Never intentionally switch more than one actuator during a single calibration transition because that would make attribution ambiguous.

## First measured power signatures — 2026-09-05

A supervised Local Agent calibration was completed successfully with the Shelly master ON and the three RF loads exercised one at a time. The measurement sequence used multiple samples and median active power before and after each transition.

Observed all-controlled-loads-OFF baseline:

- `2.2 W` median;
- about `243.8 V` mains during baseline;
- final baseline after all tests returned to `2.2 W` exactly within measurement resolution.

Observed characteristic signatures:

| actuator | pre/OFF median | ON median | ON delta | OFF delta | observed mains |
| --- | ---: | ---: | ---: | ---: | ---: |
| lamp | 2.2 W | 99.3 W | +97.1 W | -97.1 W | about 243.4 V |
| exhaust fan | 2.2 W | 5.4 W | +3.2 W | -3.2 W | about 244.1 V |
| humidifier | 2.2 W | 17.6 W | +15.4 W | -15.4 W | about 244.1 V |

The ON and OFF deltas matched exactly for all three devices in this first calibration, which is strong evidence that the individual RF transitions corresponded to physical load changes measured independently by Shelly.

Initial reference signatures are therefore:

- lamp: approximately `97.1 W` contribution;
- exhaust fan: approximately `3.2 W` contribution;
- humidifier: approximately `15.4 W` contribution.

## 20-second settled repeat calibration — 2026-09-05

A second supervised calibration repeated the same one-device-at-a-time sequence but waited a full `20 s` after every RF ON and every RF OFF before sampling Shelly. Each stable state was then represented by the median of nine Shelly samples.

Results:

| actuator | pre/OFF median | ON median after 20 s | OFF median after 20 s | ON delta | OFF delta | ON/OFF delta disagreement | observed mains |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| lamp | 2.2 W | 99.2 W | 2.2 W | +97.0 W | -97.0 W | 0.0 W | about 243.8 V |
| exhaust fan | 2.3 W | 5.1 W | 2.2 W | +2.8 W | -2.9 W | 0.1 W | about 245.0 V |
| humidifier | 2.2 W | 17.9 W | 2.2 W | +15.7 W | -15.7 W | 0.0 W | about 243.9 V |

The all-controlled-loads-OFF baseline was `2.2 W` and the final state after the full repeat also returned to `2.2 W`.

This repeat strongly confirms that the characteristic load signatures remain visible after Shelly and the loads have had ample time to settle. It also demonstrates why production confirmation must use tolerance ranges rather than one exact wattage constant: the low-power fan moved from approximately `3.2 W` contribution in the first short-settle calibration to approximately `2.8-2.9 W` in the 20-second calibration, while the much larger lamp and humidifier signatures remained within a few tenths of a watt of the first test.

Practical initial centers from both supervised calibrations are therefore approximately:

- lamp: `97.0-97.1 W` contribution;
- exhaust fan: `2.8-3.2 W` contribution;
- humidifier: `15.4-15.7 W` contribution.

Do not freeze final acceptance bands from only two calibration cycles. Continue collecting signatures during supervised hardware tests, including mains voltage and settled state, and derive robust tolerance bands from the distribution. For low-power loads such as the fan, use a relative/wider tolerance and require a stable baseline because a small unrelated load change can be comparable with the fan signature.

The calibration ended safely with lamp OFF, fan OFF and humidifier OFF; the Shelly master remained ON and final measured power returned to the `2.2 W` baseline.

## Master-switch role

The Shelly relay may also be used as an emergency master cutoff, but it is not the normal thermal-control mechanism.

The normal high-temperature response remains actuator-specific:

`thermal trip -> lamp OFF + exhaust fan ON`

A master cutoff that removes power from both the lamp and the exhaust fan would defeat active cooling, and a master cutoff that also powers down the ESP32 controller would remove telemetry/control. Therefore master OFF is reserved for higher-level fault handling such as an unsafe/unexplained power signature, failed actuator shutdown, overload/fault conditions, or an explicit emergency action.

Before enabling automatic Shelly relay writes as a production safety action, document exactly which loads and controller components are downstream of the plug and qualify the fail-safe behavior separately. Shelly writes used during supervised calibration must be explicit and verified by readback.
