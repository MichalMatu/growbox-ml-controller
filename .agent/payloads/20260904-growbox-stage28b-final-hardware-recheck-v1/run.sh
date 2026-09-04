#!/usr/bin/env bash
set -euo pipefail
EXPECTED=a87169748ee2bd42bc4d35cfe3b2964b90f40eb8

test "$(git rev-parse HEAD)" = "$EXPECTED"
git fetch -q origin mvp/environment-controller
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
test -z "$(git status --porcelain)"

PORT=$(.venv/bin/python -c 'from tools.stage27c_soak import detect_ch340_port; print(detect_ch340_port())')
echo "STAGE28B_PORT=$PORT"

export PORT
export GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED"
export GROWBOX_STAGE27_SD_ENABLED=1
export GROWBOX_STAGE27_FLASH_FALLBACK_ENABLED=1
export GROWBOX_SD_CMD0_PRECONDITION=0
export GROWBOX_RF433_LOOPBACK_ENABLED=1
export GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=1
export GROWBOX_RF433_TX_GPIO=8
export GROWBOX_RF433_RX_GPIO=14
export STAGE27C_BUILD_DIR=build/idf-stage28b-final-hardware-recheck-v1

scripts/stage27c_crowpanel.sh flash

OUT=/tmp/stage28b-final-hardware-recheck-v1
rm -rf "$OUT"
.venv/bin/python tools/stage27c_soak.py \
  --port "$PORT" \
  --output-dir "$OUT" \
  --duration 180 \
  --progress-seconds 30 \
  --expected-sha "$EXPECTED" \
  --require-sd \
  --strict

.venv/bin/python - "$OUT" <<'PY'
from pathlib import Path
import sys

out = Path(sys.argv[1])
rf = []
for path in sorted(out.glob('raw-*.log')):
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if 'rf433_loopback_v=1 ' in line:
            rf.append(line)

assert rf, 'no RF loopback evidence captured'
assert len(rf) == 1, f'unexpected RF smoke count: {len(rf)}'
line = rf[0]
print('STAGE28B_FINAL_RF_RESULT', line)
fields = {}
for token in line.split('rf433_loopback_v=1 ', 1)[1].split():
    if '=' in token:
        key, value = token.split('=', 1)
        fields[key] = value

def iv(key):
    return int(fields[key], 0)

assert iv('pass') == 1, fields
assert iv('tx_id') == 1, fields
assert iv('requested_code') == 0xA55A, fields
assert iv('requested_bits') == 16, fields
assert iv('requested_protocol') == 1, fields
assert iv('requested_repeat') == 3, fields
assert iv('tx_queued') == 1, fields
assert iv('tx_started') == 1, fields
assert iv('tx_completed') == 1, fields
assert iv('rx_captured') == 1, fields
assert iv('decode_status') == 0, fields
assert iv('decoded_code') == 0xA55A, fields
assert iv('decoded_bits') == 16, fields
assert iv('decoded_protocol') == 1, fields
assert iv('classification') == 1, fields
assert iv('rx_arm_errors') == 0, fields
assert iv('rx_timeouts') == 0, fields
assert iv('rx_decode_failures') == 0, fields
assert iv('rx_ambiguous') == 0, fields
assert iv('rx_self_tx') == 1, fields
assert iv('rx_interference') == 0, fields
assert fields.get('outputs') == 'fake-locked', fields
print('STAGE28B_FINAL_LOOPBACK_PASS')
PY

test -z "$(git status --porcelain)"
printf 'STAGE28B_FINAL_HARDWARE_RECHECK_OK sha=%s\n' "$EXPECTED"
