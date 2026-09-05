#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

git fetch -q origin agent-control
SRC=/tmp/growbox-fan-short-diagnostic-fixed-port-v3-source.sh
RUN=/tmp/growbox-fan-short-diagnostic-fixed-port-v3-run.sh
git show origin/agent-control:.agent/payloads/20260905-growbox-fan-short-diagnostic-v1/run.sh > "$SRC"
cp "$SRC" "$RUN"
python3 - "$RUN" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text()
s=s.replace('from tools.stage27c_soak import detect_ch340_port\n','')
s=s.replace('port=detect_ch340_port()','port="/dev/cu.usbserial-1130"')
s=s.replace('bash scripts/stage27c_crowpanel.sh flash','PORT=/dev/cu.usbserial-1130 bash scripts/stage27c_crowpanel.sh flash')
if 'detect_ch340_port' in s:
    raise SystemExit('fixed-port patch incomplete: detect_ch340_port remains')
if '/dev/cu.usbserial-10' in s:
    raise SystemExit('forbidden unrelated serial port present')
if s.count('/dev/cu.usbserial-1130') < 3:
    raise SystemExit('fixed-port patch did not cover monitor/flash paths')
p.write_text(s)
PY
bash -n "$RUN"
exec bash "$RUN"
