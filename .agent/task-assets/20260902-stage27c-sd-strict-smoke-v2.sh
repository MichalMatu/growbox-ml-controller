#!/usr/bin/env bash
set -euo pipefail

EXPECTED_SHA="5a985684ad223818e1cad9ada3713016c5f2be0b"
OUT_DIR="/tmp/20260902-stage27c-sd-strict-smoke-v2"

ACTUAL_SHA="$(git rev-parse HEAD)"
if [[ "$ACTUAL_SHA" != "$EXPECTED_SHA" ]]; then
  echo "Expected worktree HEAD $EXPECTED_SHA, got $ACTUAL_SHA" >&2
  exit 2
fi

git fetch origin mvp/environment-controller
REMOTE_SHA="$(git rev-parse origin/mvp/environment-controller)"
if [[ "$REMOTE_SHA" != "$EXPECTED_SHA" ]]; then
  echo "Expected remote HEAD $EXPECTED_SHA, got $REMOTE_SHA" >&2
  exit 2
fi

PORT_S3="$(python3 - <<'PY'
from tools.stage27c_soak import detect_ch340_port
print(detect_ch340_port())
PY
)"

echo "[AGENT_PROGRESS] port=$PORT_S3"
source scripts/source_idf.sh
python -m esptool --port "$PORT_S3" chip_id | tee /tmp/stage27c-sd-strict-chip-v2.txt
grep -q 'ESP32-S3' /tmp/stage27c-sd-strict-chip-v2.txt

rm -rf "$OUT_DIR"
python3 tools/stage27c_soak.py \
  --output-dir "$OUT_DIR" \
  --duration 300 \
  --progress-seconds 60 \
  --port "$PORT_S3" \
  --expected-sha "$EXPECTED_SHA" \
  --max-scd-age-ms 15000 \
  --max-tp-age-ms 60000 \
  --max-xiaomi-age-ms 30000 \
  --require-sd \
  --strict

echo "[AGENT_PROGRESS] strict_summary"
cat "$OUT_DIR/summary.json"

git diff --exit-code
if [[ -n "$(git status --porcelain)" ]]; then
  git status --short
  exit 4
fi
