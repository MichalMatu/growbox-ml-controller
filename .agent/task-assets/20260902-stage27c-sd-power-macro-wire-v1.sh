#!/usr/bin/env bash
set -euo pipefail

BASE=08298e95ae46e807667b860141f21cf75eeaa15c

git fetch origin mvp/environment-controller agent-control
git reset --hard origin/mvp/environment-controller
git clean -fd
test "$(git rev-parse HEAD)" = "$BASE"

python3 - <<'PY'
from pathlib import Path
p = Path('src/CMakeLists.txt')
s = p.read_text()
old = 'set(GROWBOX_SD_CS_GPIO "10" CACHE STRING "Stage27 SD SPI chip-select GPIO")\n'
new = old + 'set(GROWBOX_SD_POWER_GPIO "-1" CACHE STRING "Stage27 SD power-enable GPIO")\n'
if old not in s:
    raise SystemExit('SD CS cache anchor not found')
s = s.replace(old, new, 1)
old2 = '    GROWBOX_SD_CS_GPIO=${GROWBOX_SD_CS_GPIO}\n'
new2 = old2 + '    GROWBOX_SD_POWER_GPIO=${GROWBOX_SD_POWER_GPIO}\n'
if old2 not in s:
    raise SystemExit('SD CS compile-definition anchor not found')
s = s.replace(old2, new2, 1)
p.write_text(s)
PY

git diff --check
.venv/bin/pre-commit run --files src/CMakeLists.txt
.venv/bin/python -m pytest tests/test_stage27c_soak.py -q

git add src/CMakeLists.txt
git commit -m 'Wire Stage27C SD power GPIO into runtime'
NEW_SHA="$(git rev-parse HEAD)"
echo "[AGENT_PROGRESS] sd_power_macro_sha=$NEW_SHA"

bash scripts/stage27c_crowpanel.sh clean
GROWBOX_FIRMWARE_GIT_SHA="$NEW_SHA" bash scripts/stage27c_crowpanel.sh build
test -f build/idf-stage27c-crowpanel/growbox_ml_controller.bin
grep -aFq "$NEW_SHA" build/idf-stage27c-crowpanel/growbox_ml_controller.bin
grep -Fq 'GROWBOX_SD_POWER_GPIO=42' build/idf-stage27c-crowpanel/compile_commands.json
echo '[AGENT_PROGRESS] compile_definition_power_gpio=42'

git push origin HEAD:mvp/environment-controller
test -z "$(git status --short)"

PORT_S3="$(.venv/bin/python -c 'from tools.stage27c_soak import detect_ch340_port; print(detect_ch340_port())')"
source scripts/source_idf.sh
PROBE="$(python -m esptool --port "$PORT_S3" chip_id 2>&1)"
echo "$PROBE"
grep -q 'ESP32-S3' <<<"$PROBE"
PORT="$PORT_S3" GROWBOX_FIRMWARE_GIT_SHA="$NEW_SHA" bash scripts/stage27c_crowpanel.sh flash

# Capture long enough to see either the initial mount or the next 30 s retry.
PORT_S3="$PORT_S3" .venv/bin/python - <<'PY'
import os, time, serial
port = os.environ['PORT_S3']
end = time.monotonic() + 45
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
power_begin = any('GPIO42 held HIGH continuously' in x for x in lines)
before_high = any('level before mount=1' in x for x in lines)
after_high = any('level after mount failure=1' in x for x in lines)
mount_failed = any('SD mount failed' in x for x in lines)
mounted = any('SD mounted on SPI3' in x or 'sd_mounted=1' in x for x in lines)
print('[AGENT_PROGRESS] power_begin_high=%s' % str(power_begin).lower())
print('[AGENT_PROGRESS] power_before_mount_high=%s' % str(before_high).lower())
print('[AGENT_PROGRESS] power_after_failure_high=%s' % str(after_high).lower())
print('[AGENT_PROGRESS] mount_seen=%s' % str(mounted).lower())
print('[AGENT_PROGRESS] mount_failed=%s' % str(mount_failed).lower())
if mount_failed and (not before_high or not after_high):
    raise SystemExit('Mount failed without GPIO42 high proof')
if not mounted and not (power_begin or before_high):
    raise SystemExit('No evidence that GPIO42=42 reached runtime')
PY

OUT="build/stage27c-sd-power-macro-${NEW_SHA:0:7}"
rm -rf "$OUT"
.venv/bin/python tools/stage27c_soak.py \
  --port "$PORT_S3" \
  --output-dir "$OUT" \
  --duration 300 \
  --progress-seconds 60 \
  --expected-sha "$NEW_SHA" \
  --max-scd-age-ms 15000 \
  --max-tp-age-ms 60000 \
  --max-xiaomi-age-ms 30000 \
  --require-sd \
  --strict

echo '[AGENT_PROGRESS] sd_power_macro_strict_smoke_summary'
cat "$OUT/summary.json"
test -z "$(git status --short)"
echo "PUBLISHED_SHA=$NEW_SHA"
