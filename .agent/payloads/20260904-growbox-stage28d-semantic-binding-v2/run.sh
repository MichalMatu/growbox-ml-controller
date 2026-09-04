#!/usr/bin/env bash
set -euo pipefail

git fetch -q origin agent-control
BASE=/tmp/growbox-stage28d-semantic-binding-v2-base.sh
git show origin/agent-control:.agent/payloads/20260904-growbox-stage28d-semantic-binding-v1/run.sh > "$BASE"

python3 - "$BASE" <<'PY'
from pathlib import Path
import sys

p = Path(sys.argv[1])
s = p.read_text()
old = '''p = Path("docs/CURRENT_STATUS.md")
s = p.read_text()
if transition_old not in s:
    raise SystemExit("CURRENT_STATUS transition marker missing")
s = s.replace(transition_old, transition_new, 1)
s = s.replace(
'''
new = '''p = Path("docs/CURRENT_STATUS.md")
s = p.read_text()
status_old = "**Stage28A DONE -> Stage28B DONE -> Stage28C DONE -> pre-Stage28D golden gate COMPLETE -> Stage28D NOT STARTED**"
status_new = "**Stage28A DONE -> Stage28B DONE -> Stage28C DONE -> pre-Stage28D golden gate COMPLETE -> Stage28D IN PROGRESS**"
if status_old not in s:
    raise SystemExit("CURRENT_STATUS transition marker missing")
s = s.replace(status_old, status_new, 1)
s = s.replace(
'''
if old not in s:
    raise SystemExit("v1 CURRENT_STATUS block not found")
p.write_text(s.replace(old, new, 1))
PY

bash "$BASE"
