#!/usr/bin/env bash
set -euo pipefail

EXPECTED=00cc0137adb7aeaa6d69bb6781ac97cb0784c5ab

test "$(git rev-parse HEAD)" = "$EXPECTED"
git fetch -q origin mvp/environment-controller
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
test -z "$(git status --porcelain)"

PORT=$(.venv/bin/python -c 'from tools.stage27c_soak import detect_ch340_port; print(detect_ch340_port())')
echo "STAGE28C_PORT=$PORT"

export PORT
export GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED"
export GROWBOX_STAGE27_SD_ENABLED=1
export GROWBOX_STAGE27_FLASH_FALLBACK_ENABLED=1
export GROWBOX_SD_CMD0_PRECONDITION=0
export GROWBOX_RF433_LOOPBACK_ENABLED=1
export GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0
export GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=1
export GROWBOX_RF433_TX_GPIO=8
export GROWBOX_RF433_RX_GPIO=14
export STAGE27C_BUILD_DIR=build/idf-stage28c-capture-ready-hardware-v1

scripts/stage27c_crowpanel.sh flash

OUT=/tmp/stage28c-capture-ready-hardware-v1
rm -rf "$OUT"
.venv/bin/python tools/stage27c_soak.py \
  --port "$PORT" \
  --output-dir "$OUT" \
  --duration 30 \
  --progress-seconds 10 \
  --expected-sha "$EXPECTED" \
  --require-sd

.venv/bin/python - "$OUT" <<'PY'
from pathlib import Path
import sys

out = Path(sys.argv[1])
ready = []
self_tx = []
for path in sorted(out.glob('raw-*.log')):
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if 'rf433_remote_capture_ready_v=1 ' in line:
            ready.append(line)
        if 'rf433_loopback_v=1 ' in line:
            self_tx.append(line)

assert ready, 'no Stage28C remote-capture ready evidence captured'
assert len(ready) == 1, f'unexpected ready marker count: {len(ready)}'
assert not self_tx, f'auto self-TX unexpectedly active: {self_tx}'
line = ready[0]
print('STAGE28C_CAPTURE_READY_RESULT', line)
fields = {}
for token in line.split('rf433_remote_capture_ready_v=1 ', 1)[1].split():
    if '=' in token:
        key, value = token.split('=', 1)
        fields[key] = value
assert int(fields['rx_gpio'], 0) == 14, fields
assert int(fields['passive_rx_only'], 0) == 1, fields
assert fields.get('outputs') == 'fake-locked', fields
print('STAGE28C_CAPTURE_READY_PASS')
PY

test -z "$(git status --porcelain)"
printf 'STAGE28C_CAPTURE_READY_HARDWARE_OK sha=%s\n' "$EXPECTED"
