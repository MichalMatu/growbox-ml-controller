#!/usr/bin/env bash
set -euo pipefail
EXPECTED=60da0a4d2a99f3045596b6a8a8bf362a0c6e1aca
BRANCH=mvp/environment-controller

git fetch -q origin "$BRANCH" agent-control
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
git reset --hard "$EXPECTED"
git clean -fd
test "$(git rev-parse HEAD)" = "$EXPECTED"
test -z "$(git status --porcelain)"

git show origin/agent-control:.agent/payloads/20260904-growbox-prestage-docs-sync-v1/run.sh > /tmp/prestage-docs-sync-v1.sh
python3 - <<'PY'
from pathlib import Path
p = Path('/tmp/prestage-docs-sync-v1.sh')
s = p.read_text(encoding='utf-8')
needle = "\ngit diff --check\n\n# Active handoff/status docs"
insert = r'''
python3 - <<'PYEOF'
from pathlib import Path
for name in [
    'continuation.md',
    'README.md',
    'docs/CURRENT_STATUS.md',
    'docs/CONTINUATION_PLAN.md',
    'docs/ARCHITECTURE.md',
    'docs/STAGE28C_FINAL_EVIDENCE.md',
]:
    p = Path(name)
    p.write_text(p.read_text(encoding='utf-8').rstrip() + '\n', encoding='utf-8')
PYEOF

git diff --check

# Active handoff/status docs'''
if needle not in s:
    raise SystemExit('docs-sync v1 diff-check anchor not found')
p.write_text(s.replace(needle, insert, 1), encoding='utf-8')
PY
bash /tmp/prestage-docs-sync-v1.sh
