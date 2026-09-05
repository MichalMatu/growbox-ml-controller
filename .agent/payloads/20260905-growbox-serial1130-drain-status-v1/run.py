import time
import serial

PORT = "/dev/cu.usbserial-1130"

h = serial.Serial(port=None, baudrate=115200, timeout=0.08, write_timeout=1)
h.dtr = False
h.rts = False
h.port = PORT
h.open()
try:
    start = time.monotonic()
    buf = ""
    next_status = start + 8.0
    end = start + 28.0
    while time.monotonic() < end:
        now = time.monotonic()
        if now >= next_status:
            h.write(b"status\n")
            h.flush()
            next_status += 4.0
        b = h.read(4096)
        if b:
            buf += b.decode(errors="replace")
    print(f"SERIAL1130_DRAIN_BYTES {len(buf)}")
    lines = [ln for ln in buf.splitlines() if "status firmware_sha=" in ln or "outputs=" in ln or "rf_ready=" in ln or "stage28d_output" in ln or "soak_v=2" in ln]
    print(f"SERIAL1130_MATCHING_LINES {len(lines)}")
    for line in lines[-80:]:
        print(line[:4000])
finally:
    h.close()
