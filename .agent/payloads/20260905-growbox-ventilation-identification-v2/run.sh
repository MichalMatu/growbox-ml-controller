#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

git fetch -q origin agent-control
git show origin/agent-control:.agent/payloads/20260905-growbox-ventilation-identification-v1/run.sh > /tmp/growbox-ventilation-identification-v1.sh
chmod +x /tmp/growbox-ventilation-identification-v1.sh

child_pid=""
cleanup() {
  if [[ -n "$child_pid" ]] && kill -0 "$child_pid" 2>/dev/null; then
    kill -TERM "$child_pid" 2>/dev/null || true
    wait "$child_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

PYTHONUNBUFFERED=1 bash /tmp/growbox-ventilation-identification-v1.sh &
child_pid=$!
started="$(date +%s)"

while kill -0 "$child_pid" 2>/dev/null; do
  now="$(date +%s)"
  elapsed=$((now - started))
  printf 'VENT_ID_HEARTBEAT elapsed_s=%d child_pid=%s\n' "$elapsed" "$child_pid"
  sleep 30
 done

set +e
wait "$child_pid"
rc=$?
set -e
child_pid=""
trap - EXIT INT TERM

if [[ "$rc" -ne 0 ]]; then
  echo "VENT_ID_V2_FAIL child_rc=$rc"
  exit "$rc"
fi

echo "VENT_ID_V2_COMPLETE"
