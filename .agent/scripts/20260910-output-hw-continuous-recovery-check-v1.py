import re
import time

import serial

PORT = "/dev/cu.usbserial-1130"
FORBIDDEN = "/dev/cu.usbserial-10"
QUALIFIED = "02208d23f403bca3540dbbd652eb55703a044833"
MAX_SECONDS = 780.0
COMMAND_PERIOD_SECONDS = 10.0

ser = serial.Serial(port=None, baudrate=115200, timeout=0.2, write_timeout=1)
ser.dtr = False
ser.rts = False
ser.port = PORT
ser.open()

print(
    f"HW_CONTINUOUS_RECOVERY_OPEN port={PORT} forbidden_port_untouched={FORBIDDEN} "
    "expected_port_open_reset=1",
    flush=True,
)

status_identity = False
sensor_seen = False
safety_clear = False
disabled = False
off_requested = False
boot_ids: set[str] = set()
started = time.monotonic()
next_command = 0.0

try:
    while time.monotonic() - started < MAX_SECONDS:
        now = time.monotonic()
        raw = ser.readline()
        if raw:
            line = raw.decode(errors="replace").strip()
            print(line, flush=True)

            if "status firmware_sha=" in line:
                match = re.search(
                    r"status firmware_sha=([^ ]+).*?boot_id=([^ ]+).*?outputs=([^ ]+).*?rf_ready=([01])",
                    line,
                )
                if match:
                    if match.group(1) != QUALIFIED:
                        raise SystemExit(
                            f"HW_CONTINUOUS_RECOVERY_FAIL firmware_sha={match.group(1)} expected={QUALIFIED}"
                        )
                    boot_ids.add(match.group(2))
                    if len(boot_ids) != 1:
                        raise SystemExit(
                            f"HW_CONTINUOUS_RECOVERY_FAIL unexpected_restart boot_ids={sorted(boot_ids)}"
                        )
                    if match.group(3) == "real-bounded" and match.group(4) == "1":
                        status_identity = True

            if "tp357 temp_c=" in line and "available=1" not in line:
                sensor_seen = True
            if "tp_sample=1" in line:
                sensor_seen = True

            if "safety_latched=0" in line:
                safety_clear = True

            if "automation mode=Automatic" in line and not off_requested:
                ser.write(b"automation off\n")
                ser.flush()
                off_requested = True
                print("HW_CONTINUOUS_RECOVERY_AUTOMATION_OFF_REQUESTED supervisor_owned=1", flush=True)

            if "automation mode=Disabled requested=off transition_active=0 request_pending=0" in line:
                disabled = True

        if now >= next_command:
            ser.write(b"status\nautomation status\nsensors\n")
            ser.flush()
            next_command = now + COMMAND_PERIOD_SECONDS

        if status_identity and sensor_seen and safety_clear and disabled:
            break

        time.sleep(0.01)
finally:
    ser.close()

if not status_identity:
    raise SystemExit("HW_CONTINUOUS_RECOVERY_FAIL qualified_real_status=0")
if not sensor_seen:
    raise SystemExit("HW_CONTINUOUS_RECOVERY_FAIL sensor_evidence=0")
if not safety_clear:
    raise SystemExit("HW_CONTINUOUS_RECOVERY_FAIL safety_clear=0")
if not disabled:
    raise SystemExit("HW_CONTINUOUS_RECOVERY_FAIL disabled=0")

elapsed = time.monotonic() - started
print(
    f"OUTPUT_HW_CONTINUOUS_RECOVERY_PASS sha={QUALIFIED} port={PORT} "
    f"mode=Disabled safety_latched=0 elapsed_s={elapsed:.1f} flash_started=0 raw_rf=0 "
    f"forbidden_port_untouched={FORBIDDEN} hardware_started=1",
    flush=True,
)
