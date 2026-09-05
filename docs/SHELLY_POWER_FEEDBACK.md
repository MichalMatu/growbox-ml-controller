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

## Intended growbox role

The Shelly can be installed upstream of the current growbox loads and used as an independent power-feedback channel. During actuator calibration, measure the stable power delta for:

- all controlled loads OFF (baseline);
- lamp only ON;
- exhaust fan only ON;
- humidifier only ON;
- useful combinations of the above.

The resulting power signatures can provide physical feedback after an RF command. For example, an RF `lamp ON` transmission followed by no expected increase in Shelly active power is evidence that the physical load probably did not change state. Local RF TX completion alone must not be treated as physical acknowledgement.

The power-feedback path should therefore be modeled as:

`requested actuator state -> RF command -> expected power signature -> Shelly measured power -> physical-state confidence / anomaly`

Do not require exact wattage equality. Use calibrated ranges/tolerances and settling time because mains voltage, lamp driver behavior, fan load and humidifier duty can vary.

## Master-switch role

The Shelly relay may also be used as an emergency master cutoff, but it is not the normal thermal-control mechanism.

The normal high-temperature response remains actuator-specific:

`thermal trip -> lamp OFF + exhaust fan ON`

A master cutoff that removes power from both the lamp and the exhaust fan would defeat active cooling, and a master cutoff that also powers down the ESP32 controller would remove telemetry/control. Therefore master OFF is reserved for higher-level fault handling such as an unsafe/unexplained power signature, failed actuator shutdown, overload/fault conditions, or an explicit emergency action.

Before enabling automatic Shelly relay writes, document exactly which loads and controller components are downstream of the plug and qualify the fail-safe behavior separately. Until that gate is explicitly opened, Shelly integration should remain read-only power telemetry.
