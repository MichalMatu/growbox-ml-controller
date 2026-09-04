#!/usr/bin/env bash
set -euo pipefail
EXPECTED=6a5c3e1d4d016a515962bd39a2ac52a9477354c9
SRC=src/climate/rf433/Rf433RmtLoopback.cpp
ORIG=/tmp/stage28c-knownpair-idle20-probe-v1.orig.cpp
PORT=""

restore_source() {
  if [[ -f "$ORIG" ]]; then
    cp "$ORIG" "$SRC"
  fi
}
trap restore_source EXIT

test "$(git rev-parse HEAD)" = "$EXPECTED"
git fetch -q origin mvp/environment-controller
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
test -z "$(git status --porcelain)"
cp "$SRC" "$ORIG"

python3 - <<'PY'
from pathlib import Path
p=Path('src/climate/rf433/Rf433RmtLoopback.cpp')
s=p.read_text(encoding='utf-8')
old="constexpr std::uint32_t kRxMaximumSignalNs = 300'000'000U;"
new="constexpr std::uint32_t kRxMaximumSignalNs = 20'000'000U;"
assert s.count(old)==1, 'expected 300ms idle constant not found exactly once'
p.write_text(s.replace(old,new,1),encoding='utf-8')
PY

git diff --check
PORT=$(.venv/bin/python -c 'from tools.stage27c_soak import detect_ch340_port; print(detect_ch340_port())')
test -n "$PORT"
echo "STAGE28C_IDLE20_PORT=$PORT"

run_one() {
  local label="$1"
  local code="$2"
  local lower
  lower="$(printf '%s' "$label" | tr '[:upper:]' '[:lower:]')"
  local build_dir="build/idf-stage28c-idle20-${lower}-v1"
  local out="/tmp/stage28c-idle20-${lower}-v1"

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

  echo "STAGE28C_IDLE20_${label}_FLASH code=$code bits=32 protocol=2 pulse_us=575 repeat=10"
  scripts/stage27c_crowpanel.sh flash

  rm -rf "$out"
  .venv/bin/python tools/stage27c_soak.py --port "$PORT" --output-dir "$out" --duration 12 --progress-seconds 6 --expected-sha "$EXPECTED"

  .venv/bin/python - "$out" "$label" "$code" <<'PY'
from pathlib import Path
import sys
out=Path(sys.argv[1]); label=sys.argv[2]; code=int(sys.argv[3])
lines=[]
for p in sorted(out.glob('raw-*.log')):
    for line in p.read_text(encoding='utf-8', errors='replace').splitlines():
        if 'rf433_loopback_v=1 ' in line:
            lines.append(line)
assert len(lines)==1, (label, 'loopback line count', len(lines))
line=lines[0]
f={}
for token in line.split('rf433_loopback_v=1 ',1)[1].split():
    if '=' in token:
        k,v=token.split('=',1); f[k]=v
req={
 'requested_code':code,'requested_bits':32,'requested_protocol':2,
 'requested_repeat':10,'requested_pulse_us':575,'tx_queued':1,'tx_started':1,
 'tx_completed':1,'rx_captured':1,'decode_status':0,'decoded_code':code,
 'decoded_bits':32,'decoded_protocol':2,'classification':1,'pass':1,
}
for k,v in req.items():
    assert int(f[k],0)==v, (label,k,v,f)
assert int(f['observed_repeats'],0)>=1, (label,'observed_repeats',f)
assert int(f['rx_arm_errors'],0)==0, (label,'rx_arm_errors',f)
assert int(f['rx_timeouts'],0)==0, (label,'rx_timeouts',f)
assert f.get('outputs')=='fake-locked', (label,'outputs',f)
print(f"STAGE28C_IDLE20_{label}_PASS code={code} repeats={f['observed_repeats']} pulse={f['estimated_pulse_us']}")
print(line)
PY
}

run_one ON 906118656
run_one OFF 1040336384

restore_source
trap - EXIT
test -z "$(git status --porcelain)"

# Leave the board in passive RX-only diagnostics, not auto-transmit.
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
export STAGE27C_BUILD_DIR=build/idf-stage28c-idle20-safe-rx-v1
scripts/stage27c_crowpanel.sh flash

test -z "$(git status --porcelain)"
printf 'STAGE28C_IDLE20_KNOWNPAIR_DONE sha=%s on=%s off=%s safe_rx_restored=1\n' "$EXPECTED" 906118656 1040336384
