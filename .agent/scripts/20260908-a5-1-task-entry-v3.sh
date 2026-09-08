#!/usr/bin/env bash
set -euo pipefail

git show FETCH_HEAD:.agent/scripts/20260908-a5-1-schedule-intent-v1.py > /tmp/a5_1_edit.py
git show FETCH_HEAD:.agent/scripts/20260908-a5-1-schedule-intent-v1-run.sh > /tmp/a5_1_run.sh
git show FETCH_HEAD:.agent/scripts/20260908-a5-1-schedule-intent-v3-fix.py > /tmp/a5_1_fix.py
python3 - <<'PY'
from pathlib import Path
path = Path('/tmp/a5_1_run.sh')
text = path.read_text()
needle = 'python3 /tmp/a5_1_edit.py\n'
if needle not in text:
    raise SystemExit('A5.1 edit invocation not found')
path.write_text(text.replace(needle, needle + 'python3 /tmp/a5_1_fix.py\n', 1))
PY
bash /tmp/a5_1_run.sh
