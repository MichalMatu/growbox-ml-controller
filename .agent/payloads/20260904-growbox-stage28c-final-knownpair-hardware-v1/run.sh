#!/usr/bin/env bash
set -euo pipefail

EXPECTED=2cb4b8dffb0835460a9e9ba920d9bd888c99d992
PORT=""

test "$(git rev-parse HEAD)" = "$EXPECTED"
git fetch -q origin mvp/environment-controller
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
test -z "$(git status --porcelain)"

PORT=$(.venv/bin/python -c 'from tools.stage27c_soak import detect_ch340_port; print(detect_ch340_port())')
test -n "$PORT"
echo "STAGE28C_FINAL_KNOWNPAIR_PORT=$PORT"

run_one() {
  local label="$1"
  local code="$2"
  local lower
  lower="$(printf '%s' "$label" | tr '[:upper:]' '[:lower:]')"
  local build_dir="build/idf-stage28c-final-knownpair-${lower}-v1"
  local out="/tmp/stage28c-final-knownpair-${lower}-v1"

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
  export STAGE27C_BUILD_DIR="$build_dir"

  scripts/stage27c_crowpanel.sh flash
  rm -rf "$out"
  .venv/bin/python tools/stage27c_soak.py \
    --port "$PORT" --output-dir "$out" --duration 12 --progress-seconds 6 --expected-sha "$EXPECTED"

  .venv/bin/python - "$out" "$label" "$code" <<'PY'
from pathlib import Path
import sys
out=Path(sys.argv[1]); label=sys.argv[2]; expected_code=int(sys.argv[3])
lines=[]
for p in sorted(out.glob('raw-*.log')):
    for line in p.read_text(encoding='utf-8', errors='replace').splitlines():
        if 'rf433_loopback_v=1 ' in line:
            lines.append(line)
assert len(lines)==1, (label, 'loopback_line_count', len(lines))
line=lines[0]
f={}
for token in line.split('rf433_loopback_v=1 ',1)[1].split():
    if '=' in token:
        k,v=token.split('=',1); f[k]=v
required={
    'pass':1,
    'requested_code':expected_code,
    'requested_bits':32,
    'requested_protocol':2,
    'requested_repeat':10,
    'requested_pulse_us':575,
    'tx_queued':1,
    'tx_started':1,
    'tx_completed':1,
    'rx_captured':1,
    'decode_status':0,
    'decoded_code':expected_code,
    'decoded_bits':32,
    'decoded_protocol':2,
    'classification':1,
    'rx_arm_errors':0,
    'rx_timeouts':0,
}
for k,v in required.items():
    assert int(f[k],0)==v, (label,k,v,f)
assert int(f['observed_repeats'],0) >= 1, (label,'observed_repeats',f)
assert f.get('outputs') == 'fake-locked', (label,'outputs',f)
print(f"STAGE28C_FINAL_KNOWNPAIR_{label}_PASS code={expected_code} bits=32 protocol=2 pulse_us=575 tx_repeat=10 observed_repeats={f['observed_repeats']} estimated_pulse_us={f['estimated_pulse_us']}")
PY
}

run_one ON 906118656
run_one OFF 1040336384

test -z "$(git status --porcelain)"

# End in passive RX-only firmware so a reset cannot replay a transmit smoke.
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
export STAGE27C_BUILD_DIR=build/idf-stage28c-final-knownpair-safe-rx-v1
scripts/stage27c_crowpanel.sh flash

test -z "$(git status --porcelain)"
printf 'STAGE28C_FINAL_KNOWNPAIR_DONE sha=%s on=%s off=%s bits=32 protocol=2 pulse_us=575 tx_repeat=10 safe_rx_restored=1\n' "$EXPECTED" 906118656 1040336384
