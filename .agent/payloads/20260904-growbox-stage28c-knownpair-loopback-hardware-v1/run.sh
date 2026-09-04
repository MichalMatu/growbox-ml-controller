#!/usr/bin/env bash
set -euo pipefail

EXPECTED=6a5c3e1d4d016a515962bd39a2ac52a9477354c9
BUILD_DIR=build/idf-stage28c-knownpair-loopback-v1

# Exact bound source preconditions.
test "$(git rev-parse HEAD)" = "$EXPECTED"
git fetch -q origin mvp/environment-controller
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
test -z "$(git status --porcelain)"

PORT=$(.venv/bin/python -c 'from tools.stage27c_soak import detect_ch340_port; print(detect_ch340_port())')
test -n "$PORT"
echo "STAGE28C_KNOWNPAIR_PORT=$PORT"

run_one() {
  local label="$1"
  local code="$2"
  local out="/tmp/stage28c-knownpair-${label}"

  export PORT
  export GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED"
  export GROWBOX_STAGE27_SD_ENABLED=1
  export GROWBOX_STAGE27_FLASH_FALLBACK_ENABLED=1
  export GROWBOX_SD_CMD0_PRECONDITION=0
  export GROWBOX_RF433_LOOPBACK_ENABLED=1
  export GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=1
  export GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0
  export GROWBOX_RF433_LOOPBACK_SMOKE_CODE="$code"
  export GROWBOX_RF433_LOOPBACK_SMOKE_BITS=32
  export GROWBOX_RF433_LOOPBACK_SMOKE_PROTOCOL=2
  export GROWBOX_RF433_LOOPBACK_SMOKE_REPEAT=10
  export GROWBOX_RF433_LOOPBACK_SMOKE_PULSE_US=575
  export GROWBOX_RF433_TX_GPIO=8
  export GROWBOX_RF433_RX_GPIO=14
  export STAGE27C_BUILD_DIR="$BUILD_DIR"

  echo "STAGE28C_KNOWNPAIR_${label}_FLASH code=$code bits=32 protocol=2 pulse_us=575 repeat=10"
  scripts/stage27c_crowpanel.sh flash

  rm -rf "$out"
  .venv/bin/python tools/stage27c_soak.py \
    --port "$PORT" \
    --output-dir "$out" \
    --duration 15 \
    --progress-seconds 5 \
    --expected-sha "$EXPECTED" \
    --strict

  .venv/bin/python - "$out" "$label" "$code" <<'PY'
from pathlib import Path
import sys
out = Path(sys.argv[1])
label = sys.argv[2]
expected_code = int(sys.argv[3])
lines = []
for path in sorted(out.glob('raw-*.log')):
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if 'rf433_loopback_v=1 ' in line:
            lines.append(line)
assert len(lines) == 1, f'{label}: expected one rf433_loopback line, got {len(lines)}'
line = lines[0]
fields = {}
for token in line.split('rf433_loopback_v=1 ', 1)[1].split():
    if '=' in token:
        k, v = token.split('=', 1)
        fields[k] = v
required = {
    'pass': 1,
    'requested_code': expected_code,
    'requested_bits': 32,
    'requested_protocol': 2,
    'requested_repeat': 10,
    'requested_pulse_us': 575,
    'tx_queued': 1,
    'tx_started': 1,
    'tx_completed': 1,
    'rx_captured': 1,
    'decode_status': 0,
    'decoded_code': expected_code,
    'decoded_bits': 32,
    'decoded_protocol': 2,
}
for key, value in required.items():
    assert int(fields[key], 0) == value, (key, value, fields)
assert fields.get('outputs') == 'fake-locked', fields
print(f'STAGE28C_KNOWNPAIR_{label}_PASS code={expected_code} bits=32 protocol=2 pulse_us=575 repeat=10 estimated_pulse_us={fields.get("estimated_pulse_us")} observed_repeats={fields.get("observed_repeats")}')
print(f'STAGE28C_KNOWNPAIR_{label}_EVIDENCE ' + line)
PY
}

run_one ON 906118656
run_one OFF 1040336384

test "$(git rev-parse HEAD)" = "$EXPECTED"
test -z "$(git status --porcelain)"
printf 'STAGE28C_KNOWNPAIR_LOOPBACK_HARDWARE_OK sha=%s on=%s off=%s bits=32 protocol=2 pulse_us=575 repeat=10 outputs=fake-locked\n' "$EXPECTED" 906118656 1040336384
