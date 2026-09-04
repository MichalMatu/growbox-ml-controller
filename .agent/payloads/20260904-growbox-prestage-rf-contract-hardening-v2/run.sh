#!/usr/bin/env bash
set -euo pipefail

EXPECTED=a215cae35bbdee155a40fce0c7481a87191a3716
BRANCH=mvp/environment-controller

git fetch -q origin "$BRANCH" agent-control
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
git reset --hard "$EXPECTED"
rm -f src/climate/rf433/Rf433RmtTuning.h
test -z "$(git status --porcelain)"

git show origin/agent-control:.agent/payloads/20260904-growbox-prestage-rf-contract-hardening-v1/run.sh > /tmp/prestage-rf-contract-hardening-v2-inner.sh
python3 - <<'PY'
from pathlib import Path
p = Path('/tmp/prestage-rf-contract-hardening-v2-inner.sh')
s = p.read_text(encoding='utf-8')
old = 'std::min<std::size_t>(rx_symbol_count_, rx_symbols_.size());'
new = 'std::min<std::size_t>(static_cast<std::size_t>(rx_symbol_count_), rx_symbols_.size());'
if s.count(old) != 1:
    raise SystemExit(f'expected exactly one volatile min call, found {s.count(old)}')
p.write_text(s.replace(old, new, 1), encoding='utf-8')
PY
bash /tmp/prestage-rf-contract-hardening-v2-inner.sh
