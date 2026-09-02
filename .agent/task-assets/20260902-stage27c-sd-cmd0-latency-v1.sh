#!/usr/bin/env bash
set -euo pipefail
BASE=b2ced315580791d4478940f168343136facf1d56

git fetch origin mvp/environment-controller agent-control
git reset --hard origin/mvp/environment-controller
git clean -fd
test "$(git rev-parse HEAD)" = "$BASE"

python3 - <<'PY'
from pathlib import Path
p = Path('src/climate/storage/Stage27SdDataLogger.cpp')
s = p.read_text()
old = '''  std::uint8_t response = 0xFF;\n  bool response_seen = false;\n  for (unsigned attempt = 0; attempt < 16U; ++attempt) {\n    if (!transferProbeByte(device, 0xFF, response)) {\n      ESP_LOGW(kTag, "SD precondition response read failed");\n      cleanup();\n      return false;\n    }\n    if ((response & 0x80U) == 0U) {\n      response_seen = true;\n      break;\n    }\n  }\n\n  cleanup();\n  if (!response_seen || response != 0x01U) {\n    ESP_LOGW(kTag, "SD precondition CMD0 response=0x%02x", response);\n    return false;\n  }\n\n  ESP_LOGI(kTag, "SD precondition CMD0 response=0x01");\n'''
new = '''  std::uint8_t response = 0xFF;\n  bool response_seen = false;\n  unsigned response_bytes = 0U;\n  for (unsigned attempt = 0; attempt < 16U; ++attempt) {\n    if (!transferProbeByte(device, 0xFF, response)) {\n      ESP_LOGW(kTag, "SD precondition response read failed");\n      cleanup();\n      return false;\n    }\n    if ((response & 0x80U) == 0U) {\n      response_seen = true;\n      response_bytes = attempt + 1U;\n      break;\n    }\n  }\n\n  cleanup();\n  if (!response_seen || response != 0x01U) {\n    ESP_LOGW(kTag, "SD precondition CMD0 response=0x%02x after=%u", response, response_bytes);\n    return false;\n  }\n\n  ESP_LOGI(kTag, "SD precondition CMD0 response=0x01 after=%u", response_bytes);\n'''
if old not in s:
    raise SystemExit('CMD0 response block not found')
p.write_text(s.replace(old, new, 1))
PY

.venv/bin/pre-commit run clang-format --files src/climate/storage/Stage27SdDataLogger.cpp || true
.venv/bin/pre-commit run --files src/climate/storage/Stage27SdDataLogger.cpp
git diff --check
.venv/bin/python -m pytest tests/test_stage27c_soak.py -q

git add src/climate/storage/Stage27SdDataLogger.cpp
git commit -m 'Log CrowPanel SD CMD0 response latency'
NEW_SHA="$(git rev-parse HEAD)"
echo "[AGENT_PROGRESS] cmd0_latency_sha=$NEW_SHA"

bash scripts/stage27c_crowpanel.sh clean
GROWBOX_FIRMWARE_GIT_SHA="$NEW_SHA" bash scripts/stage27c_crowpanel.sh build
test -f build/idf-stage27c-crowpanel/growbox_ml_controller.bin
grep -aFq "$NEW_SHA" build/idf-stage27c-crowpanel/growbox_ml_controller.bin
git push origin HEAD:mvp/environment-controller
test -z "$(git status --short)"

PORT_S3="$(.venv/bin/python -c 'from tools.stage27c_soak import detect_ch340_port; print(detect_ch340_port())')"
source scripts/source_idf.sh
PROBE="$(python -m esptool --port "$PORT_S3" chip_id 2>&1)"
echo "$PROBE"
grep -q 'ESP32-S3' <<<"$PROBE"
PORT="$PORT_S3" GROWBOX_FIRMWARE_GIT_SHA="$NEW_SHA" bash scripts/stage27c_crowpanel.sh flash
sleep 2

PORT_S3="$PORT_S3" .venv/bin/python - <<'PY'
import os, re, time, serial
port = os.environ['PORT_S3']
end = time.monotonic() + 20
matches = []
with serial.Serial(port, 115200, timeout=0.2, rtscts=False, dsrdtr=False) as s:
    s.rts = False
    s.dtr = False
    while time.monotonic() < end:
        raw = s.readline()
        if not raw:
            continue
        line = raw.decode('utf-8', 'replace').rstrip()
        if 'stage27_sd' in line or 'Stage27 soak boot' in line:
            print(line)
        m = re.search(r'SD precondition CMD0 response=0x01 after=(\d+)', line)
        if m:
            matches.append(int(m.group(1)))
if not matches:
    raise SystemExit('No CMD0 latency measurement captured')
print('[AGENT_PROGRESS] cmd0_response_bytes=%s' % ','.join(map(str, matches)))
PY

test -z "$(git status --short)"
echo "PUBLISHED_SHA=$NEW_SHA"
