#!/usr/bin/env bash
set -euo pipefail
EXPECTED=00cc0137adb7aeaa6d69bb6781ac97cb0784c5ab
SRC=src/climate/ClimateV6RealInputRuntime.cpp
ORIG=/tmp/stage28c-scanner-tx-onoff-v1.orig.cpp

restore() {
  if [[ -f "$ORIG" ]]; then
    cp "$ORIG" "$SRC"
  fi
}
trap restore EXIT

test "$(git rev-parse HEAD)" = "$EXPECTED"
git fetch -q origin mvp/environment-controller
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
test -z "$(git status --porcelain)"
cp "$SRC" "$ORIG"

PORT=$(.venv/bin/python -c 'from tools.stage27c_soak import detect_ch340_port; print(detect_ch340_port())')
echo "STAGE28C_SCANNER_TX_PORT=$PORT"

patch_smoke() {
  local code="$1"
  .venv/bin/python - "$SRC" "$code" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
code = sys.argv[2]
text = path.read_text(encoding='utf-8')
old_variants = [
    'const rf433::FrameConfig smoke{{0xA55AU, 16U, 1U}, 3U, 0U};',
    'const rf433::FrameConfig smoke{{906118656U, 32U, 2U}, 3U, 575U};',
    'const rf433::FrameConfig smoke{{1040336384U, 32U, 2U}, 3U, 575U};',
]
found = [v for v in old_variants if v in text]
assert len(found) == 1, f'unexpected smoke source state: {found}'
new = f'const rf433::FrameConfig smoke{{{{{code}U, 32U, 2U}}, 3U, 575U}};'
path.write_text(text.replace(found[0], new, 1), encoding='utf-8')
PY
}

run_one() {
  local label="$1"
  local code="$2"
  local build_dir="build/idf-stage28c-scanner-tx-${label,,}-v1"
  local out="/tmp/stage28c-scanner-tx-${label,,}-v1"

  patch_smoke "$code"
  export PORT
  export GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED"
  export GROWBOX_STAGE27_SD_ENABLED=1
  export GROWBOX_STAGE27_FLASH_FALLBACK_ENABLED=1
  export GROWBOX_SD_CMD0_PRECONDITION=0
  export GROWBOX_RF433_LOOPBACK_ENABLED=1
  export GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=1
  export GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0
  export GROWBOX_RF433_TX_GPIO=8
  export GROWBOX_RF433_RX_GPIO=14
  export STAGE27C_BUILD_DIR="$build_dir"

  echo "STAGE28C_SCANNER_TX_${label}_FLASH code=$code bits=32 protocol=2 pulse_us=575 repeat=3"
  scripts/stage27c_crowpanel.sh flash

  rm -rf "$out"
  .venv/bin/python tools/stage27c_soak.py \
    --port "$PORT" \
    --output-dir "$out" \
    --duration 12 \
    --progress-seconds 6 \
    --expected-sha "$EXPECTED"

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
assert int(fields['requested_code'], 0) == expected_code, fields
assert int(fields['requested_bits'], 0) == 32, fields
assert int(fields['requested_protocol'], 0) == 2, fields
assert int(fields['requested_repeat'], 0) == 3, fields
assert int(fields['requested_pulse_us'], 0) == 575, fields
assert int(fields['tx_queued'], 0) == 1, fields
assert int(fields['tx_started'], 0) == 1, fields
assert int(fields['tx_completed'], 0) == 1, fields
assert fields.get('outputs') == 'fake-locked', fields
print(f'STAGE28C_SCANNER_TX_{label}_SENT code={expected_code} bits=32 protocol=2 pulse_us=575 repeat=3 tx_completed=1')
print(f'STAGE28C_SCANNER_TX_{label}_LOOPBACK ' + line)
PY
}

run_one ON 906118656
run_one OFF 1040336384

restore
trap - EXIT
test -z "$(git status --porcelain)"
printf 'STAGE28C_SCANNER_TX_ONOFF_DONE sha=%s on=%s off=%s\n' "$EXPECTED" 906118656 1040336384
