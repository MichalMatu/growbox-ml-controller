#!/usr/bin/env bash
set -euo pipefail

EXPECTED=316b58e76de609069ddbf2667fe86f6218fb2143
BRANCH=mvp/environment-controller
OUT=/tmp/growbox-prestage-golden-hardware-soak-v1

# Exact source and clean-worktree guard.
git fetch -q origin "$BRANCH"
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
test -z "$(git status --porcelain)"
git diff --check

# Build/flash exactly the golden candidate. Keep RF transport compiled/initialized,
# but disable both automatic smoke TX and passive remote-capture diagnostics.
export GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED"
export GROWBOX_RF433_LOOPBACK_ENABLED=1
export GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0
export GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0
export STAGE27C_BUILD_DIR=build/idf-prestage-golden-hardware-soak-v1
scripts/stage27c_crowpanel.sh flash

rm -rf "$OUT"
mkdir -p "$OUT"

PY=.venv/bin/python
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3)"
fi

# Wait for the known CH340 adapter to be visible after the flash/reset before the
# strict capture starts, so a normal post-flash enumeration delay is not counted
# as a runtime serial disconnect.
PORT=""
for _ in $(seq 1 30); do
  if PORT="$($PY -c 'from tools.stage27c_soak import detect_ch340_port; print(detect_ch340_port())' 2>/dev/null)" && [[ -n "$PORT" ]]; then
    break
  fi
  PORT=""
  sleep 1
done
if [[ -z "$PORT" ]]; then
  echo "CrowPanel CH340 serial adapter unavailable after flash" >&2
  exit 2
fi
sleep 3
printf 'PRESTAGE_GOLDEN_SOAK_PORT port=%s\n' "$PORT"

# 90-minute strict physical soak. Thresholds are deliberately looser than the
# already-qualified Stage27C observed freshness while still catching real stalls.
$PY tools/stage27c_soak.py \
  --port "$PORT" \
  --output-dir "$OUT" \
  --duration 5400 \
  --segment-seconds 900 \
  --progress-seconds 300 \
  --expected-sha "$EXPECTED" \
  --max-scd-age-ms 15000 \
  --max-tp-age-ms 120000 \
  --max-xiaomi-age-ms 30000 \
  --require-sd \
  --strict

# Strengthen the generic soak acceptance with bounded progress and memory checks.
$PY - "$OUT/soak.ndjson" "$OUT/summary.json" <<'PY'
import json
import sys
from pathlib import Path

records_path = Path(sys.argv[1])
summary_path = Path(sys.argv[2])
summary = json.loads(summary_path.read_text(encoding='utf-8'))
records = [json.loads(line) for line in records_path.read_text(encoding='utf-8').splitlines() if line.strip()]
if not summary.get('passed'):
    raise SystemExit('strict soak summary did not pass: ' + repr(summary.get('violations')))
if len(records) < 500:
    raise SystemExit(f'insufficient soak records: {len(records)} < 500')
first, last = records[0], records[-1]

# Require meaningful physical progress from all qualified sources.
for key, minimum_delta in {
    'scd_samples': 900,
    'rtc_reads': 400,
    'tp_accepted': 100,
    'xiaomi_accepted': 400,
}.items():
    delta = int(last[key]) - int(first[key])
    if delta < minimum_delta:
        raise SystemExit(f'{key} progressed only {delta}, expected >= {minimum_delta}')

# Storage should continue to make meaningful progress throughout the soak.
sd_delta = int(last.get('sd_records_written', 0)) - int(first.get('sd_records_written', 0))
if sd_delta < 400:
    raise SystemExit(f'SD telemetry progressed only {sd_delta} records, expected >= 400')

# Catch material memory regressions while allowing normal allocator noise.
internal_loss = int(first['heap_internal']) - int(last['heap_internal'])
psram_loss = int(first['heap_psram']) - int(last['heap_psram'])
if internal_loss > 16384:
    raise SystemExit(f'internal heap loss too large: {internal_loss} bytes')
if psram_loss > 16384:
    raise SystemExit(f'PSRAM loss too large: {psram_loss} bytes')
if int(summary.get('min_stack_free') or 0) < 2048:
    raise SystemExit(f'min stack free too low: {summary.get("min_stack_free")} bytes')

print(
    'PRESTAGE_GOLDEN_SOAK_SUMMARY '
    f'records={len(records)} uptime_first={first["uptime_ms"]} uptime_last={last["uptime_ms"]} '
    f'heap_internal_first={first["heap_internal"]} heap_internal_last={last["heap_internal"]} '
    f'heap_psram_first={first["heap_psram"]} heap_psram_last={last["heap_psram"]} '
    f'min_stack_free={summary.get("min_stack_free")} sd_delta={sd_delta}'
)
PY

# No local RF transmission is permitted during this unattended soak.
if grep -Ehi 'RF433.*TX (queued|started|completed)|TX (queued|started|completed).*RF433' "$OUT"/raw-*.log >/tmp/prestage-golden-unexpected-rf-tx.log; then
  cat /tmp/prestage-golden-unexpected-rf-tx.log >&2
  echo "unexpected RF433 TX observed during unattended soak" >&2
  exit 1
fi

# The hardware task must not mutate source state.
git diff --check
test -z "$(git status --porcelain)"
test "$(git rev-parse HEAD)" = "$EXPECTED"
git fetch -q origin "$BRANCH"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"

printf 'PRESTAGE_GOLDEN_HARDWARE_SOAK_PASS sha=%s duration_s=5400 outputs=fake-locked rf_auto_tx=0\n' "$EXPECTED"
