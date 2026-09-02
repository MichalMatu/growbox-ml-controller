#!/usr/bin/env bash
set -euo pipefail

SHA=de88b381f9c5442029dfe54efc05cbba813b94f8

git fetch origin mvp/environment-controller
git reset --hard origin/mvp/environment-controller
git clean -fd
test "$(git rev-parse HEAD)" = "$SHA"

PORT_S3="$(.venv/bin/python -c 'from tools.stage27c_soak import detect_ch340_port; print(detect_ch340_port())')"
source scripts/source_idf.sh
PROBE="$(python -m esptool --port "$PORT_S3" chip_id 2>&1)"
echo "$PROBE"
grep -q 'ESP32-S3' <<<"$PROBE"

PORT_S3="$PORT_S3" .venv/bin/python - <<'PY'
import os, time, serial
port = os.environ['PORT_S3']
end = time.monotonic() + 15
lines = []
with serial.Serial(port, 115200, timeout=0.1, rtscts=False, dsrdtr=False) as s:
    s.rts = False
    s.dtr = False
    while time.monotonic() < end:
        raw = s.readline()
        if not raw:
            continue
        line = raw.decode('utf-8', 'replace').rstrip()
        if 'stage27_sd' in line or 'Stage27 soak boot' in line or 'soak_v=2' in line:
            lines.append(line)
            print(line)
mounted = any('SD mounted on SPI3' in x for x in lines)
failed = [x for x in lines if 'SD mount failed' in x or 'SD precondition' in x and ('failed' in x or 'response=0x01' not in x)]
print(f'[AGENT_PROGRESS] new_card_mount_seen={str(mounted).lower()}')
print(f'[AGENT_PROGRESS] new_card_mount_failures={len(failed)}')
if not mounted:
    raise SystemExit('New SD card did not mount during immediate boot capture')
PY

OUT="build/stage27c-sd-new-card-smoke-${SHA:0:7}"
rm -rf "$OUT"
.venv/bin/python tools/stage27c_soak.py \
  --port "$PORT_S3" \
  --output-dir "$OUT" \
  --duration 300 \
  --progress-seconds 60 \
  --expected-sha "$SHA" \
  --max-scd-age-ms 15000 \
  --max-tp-age-ms 60000 \
  --max-xiaomi-age-ms 30000 \
  --require-sd \
  --strict

echo '[AGENT_PROGRESS] new_card_strict_smoke_summary'
cat "$OUT/summary.json"
test -z "$(git status --short)"
