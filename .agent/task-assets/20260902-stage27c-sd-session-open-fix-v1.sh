#!/usr/bin/env bash
set -euo pipefail

EXPECTED_BASE="dd0f97d81956501838ba2825c896f2043fea6154"
ROOT="$(pwd)"

git fetch origin mvp/environment-controller

git reset --hard origin/mvp/environment-controller
git clean -fd

ACTUAL_BASE="$(git rev-parse HEAD)"
if [[ "$ACTUAL_BASE" != "$EXPECTED_BASE" ]]; then
  echo "Expected base $EXPECTED_BASE, got $ACTUAL_BASE" >&2
  exit 2
fi

if [[ -f build/idf-stage27c-crowpanel/sdkconfig ]]; then
  echo "[AGENT_PROGRESS] previous_fatfs_config"
  grep -E '^CONFIG_FATFS_(LFN|MAX_LFN)' build/idf-stage27c-crowpanel/sdkconfig || true
fi

python3 - <<'PY'
from pathlib import Path
p = Path('config/idf/sdkconfig.defaults.stage27')
s = p.read_text()
block = '''\n# Stage27C SD logger uses descriptive per-session NDJSON filenames.\n# Keep FatFs long-filename support explicit so fopen() is not limited to 8.3 names.\nCONFIG_FATFS_LFN_HEAP=y\nCONFIG_FATFS_MAX_LFN=96\n'''
if 'CONFIG_FATFS_LFN_HEAP=y' not in s:
    s = s.rstrip() + '\n' + block
else:
    if 'CONFIG_FATFS_MAX_LFN=' not in s:
        s = s.rstrip() + '\nCONFIG_FATFS_MAX_LFN=96\n'
p.write_text(s)
PY

rm -rf build/idf-stage27c-crowpanel
./scripts/stage27c_crowpanel.sh build

grep -q '^CONFIG_FATFS_LFN_HEAP=y$' build/idf-stage27c-crowpanel/sdkconfig
grep -q '^CONFIG_FATFS_MAX_LFN=96$' build/idf-stage27c-crowpanel/sdkconfig
if grep -q '^CONFIG_FATFS_LFN_NONE=y$' build/idf-stage27c-crowpanel/sdkconfig; then
  echo "LFN_NONE still enabled" >&2
  exit 3
fi

echo "[AGENT_PROGRESS] rebuilt_fatfs_config"
grep -E '^CONFIG_FATFS_(LFN|MAX_LFN)' build/idf-stage27c-crowpanel/sdkconfig || true

git add config/idf/sdkconfig.defaults.stage27
git commit -m "Enable FatFs long session filenames"
NEW_SHA="$(git rev-parse HEAD)"
git push origin HEAD:mvp/environment-controller

echo "[AGENT_PROGRESS] firmware_sha=$NEW_SHA"

source scripts/source_idf.sh
PORT_S3="$(python3 - <<'PY'
from tools.stage27c_soak import detect_ch340_port
print(detect_ch340_port())
PY
)"
python -m esptool --port "$PORT_S3" chip_id | tee /tmp/stage27c-chip.txt
grep -q 'ESP32-S3' /tmp/stage27c-chip.txt

GROWBOX_FIRMWARE_GIT_SHA="$NEW_SHA" PORT="$PORT_S3" ./scripts/stage27c_crowpanel.sh flash

python3 - "$PORT_S3" <<'PY'
import serial, sys, time
port=sys.argv[1]
deadline=time.time()+12
with serial.Serial(port,115200,timeout=0.2) as s:
    while time.time()<deadline:
        line=s.readline().decode('utf-8','replace').strip()
        if 'stage27_sd' in line or 'Stage27 soak boot' in line:
            print(line)
PY

python3 tools/stage27c_soak.py \
  --duration 300 \
  --port "$PORT_S3" \
  --expected-sha "$NEW_SHA" \
  --max-scd-age-ms 15000 \
  --max-tp-age-ms 60000 \
  --max-xiaomi-age-ms 30000 \
  --require-sd \
  --strict

git diff --exit-code
git status --porcelain | grep -q '^$' || { git status --short; exit 4; }
