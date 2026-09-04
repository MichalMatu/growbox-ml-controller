#!/usr/bin/env bash
set -euo pipefail

EXPECTED=b3e90c92dd39c50c23ed618aba47e9fe8ddf26ec

test "$(git rev-parse HEAD)" = "$EXPECTED"
git fetch -q origin mvp/environment-controller
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
test -z "$(git status --porcelain)"

printf 'GOLDEN_AUDIT_HEAD=%s\n' "$EXPECTED"

python3 - <<'PY'
from pathlib import Path
import re

roots = [Path('src'), Path('lib'), Path('test/host'), Path('test')]
files=[]
for root in roots:
    if not root.exists():
        continue
    for p in root.rglob('*'):
        if p.is_file() and p.suffix in {'.cpp','.cc','.cxx','.h','.hpp'}:
            try:
                lines=p.read_text(encoding='utf-8', errors='replace').splitlines()
            except OSError:
                continue
            files.append((len(lines), str(p)))
print('GOLDEN_AUDIT_TOP_CPP_FILES')
for n,p in sorted(files, reverse=True)[:30]:
    print(f'{n:5d} {p}')

focus=[
 'src/climate/ClimateV6RealInputRuntime.cpp',
 'src/climate/rf433/Rf433RmtLoopback.cpp',
 'src/climate/rf433/Rf433ProtocolCodec.cpp',
 'src/climate/storage/Stage27TelemetryLogger.cpp',
 'src/climate/telemetry/Stage27Telemetry.cpp',
]
print('GOLDEN_AUDIT_FOCUS_SYMBOLS')
for name in focus:
    p=Path(name)
    if not p.exists():
        continue
    text=p.read_text(encoding='utf-8', errors='replace')
    lines=text.splitlines()
    classes=re.findall(r'\b(?:class|struct)\s+([A-Za-z_][A-Za-z0-9_]*)', text)
    funcs=[]
    for i,line in enumerate(lines,1):
        s=line.strip()
        if re.search(r'\)\s*(?:const\s*)?(?:noexcept\s*)?\{\s*$', s) and not s.startswith(('if ','if(','for ','for(','while ','while(','switch ','switch(')):
            funcs.append((i,s[:180]))
    print(f'FILE {name} lines={len(lines)} classes={classes}')
    for i,s in funcs[:80]:
        print(f'  FN line={i}: {s}')
PY

printf '%s\n' 'GOLDEN_AUDIT_STAGE28_STALE_DOCS'
grep -RInE 'Stage28C: NEXT|Stage28C NEXT|Stage28C is the exact next|RX resolution `1 MHz`|1,250 ns|12 ms|12,000,000 ns' \
  continuation.md docs README.md || true

printf '%s\n' 'GOLDEN_AUDIT_RF_REFERENCES'
grep -RInE 'Rf433|RF433|remote_socket_1|906118656|1040336384|kRxMaximumSignalNs|kRxMinimumSignalNs|kRxResolutionHz' \
  src test docs continuation.md README.md | head -n 500 || true

cmake -S test/host -B build/host-golden-audit-v1
cmake --build build/host-golden-audit-v1 -j2
ctest --test-dir build/host-golden-audit-v1 --output-on-failure

if [[ -x .venv/bin/python ]]; then
  .venv/bin/python -m pytest tests/test_panel_layout.py -q
fi

export GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED"
export GROWBOX_RF433_LOOPBACK_ENABLED=1
export GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0
export GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0
export STAGE27C_BUILD_DIR=build/idf-prestage-golden-audit-v1
scripts/stage27c_crowpanel.sh build

git diff --check
test -z "$(git status --porcelain)"
printf 'PRESTAGE_GOLDEN_AUDIT_PASS sha=%s\n' "$EXPECTED"
