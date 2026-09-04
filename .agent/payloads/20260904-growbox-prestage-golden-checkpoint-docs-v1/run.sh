#!/usr/bin/env bash
set -euo pipefail
EXPECTED=316b58e76de609069ddbf2667fe86f6218fb2143
BRANCH=mvp/environment-controller

git fetch -q origin "$BRANCH"
git reset --hard "$EXPECTED"
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
test -z "$(git status --porcelain)"

cat > docs/PRESTAGE28D_GOLDEN_CHECKPOINT.md <<'EOF'
# Pre-Stage28D golden checkpoint

Date: 2026-09-04
Status: COMPLETE
Stage28D: NOT STARTED
Golden firmware/source checkpoint: `316b58e76de609069ddbf2667fe86f6218fb2143`

## Software gate

Task `20260904-growbox-prestage-format-gate-v2` passed on the exact checkpoint SHA. The gate included pre-commit, Python regressions, host C++/CTest, clang-tidy, ESP-IDF quality-gate build, exact CrowPanel build, zero unknown Kconfig-symbol warnings and a clean worktree.

Terminal marker:

`PRESTAGE_FORMAT_GATE_READY commit=316b58e76de609069ddbf2667fe86f6218fb2143 parent=484a7dfa262165fc3e61716cc162a49d61a2ee8a precommit=pass quality_gate=pass crowpanel_build=pass unknown_kconfig_warnings=0 cmake_parallel=2`

## Hardware soak

Task `20260904-growbox-prestage-golden-hardware-soak-v1` built and flashed the exact checkpoint SHA and ran a strict 5400-second real-hardware soak with SCD41, DS3231 RTC, both BLE climate inputs and SD telemetry active.

Observed evidence:

- 526 records;
- zero resets, serial disconnects, parse errors, unexpected-SHA records and strict violations;
- max SCD41 age 4050 ms, TP357 age 3052 ms, Xiaomi age 11962 ms;
- zero BLE scan errors, BLE lock drops, RTC read errors, RTC untrusted records, SCD41 read errors and SCD41 invalid records;
- minimum internal heap 226200 B and largest internal block 184320 B;
- minimum PSRAM free 8368044 B and largest PSRAM block 8257536 B;
- minimum free stack 9292 B;
- SD telemetry advanced by 612 records with zero mount/write/queue/skip errors;
- outputs remained `fake-locked`;
- RF automatic transmit was disabled and no RF433 TX lifecycle was observed in the raw soak logs.

Terminal markers:

`PRESTAGE_GOLDEN_SOAK_SUMMARY records=526 uptime_first=10939 uptime_last=5393079 heap_internal_first=226328 heap_internal_last=226200 heap_psram_first=8368044 heap_psram_last=8368044 min_stack_free=9292 sd_delta=612`

`PRESTAGE_GOLDEN_HARDWARE_SOAK_PASS sha=316b58e76de609069ddbf2667fe86f6218fb2143 duration_s=5400 outputs=fake-locked rf_auto_tx=0`

## Boundary

The historical Stage28C known-pair physical recheck remains tied to `2cb4b8dffb0835460a9e9ba920d9bd888c99d992`. The exact post-hardening firmware qualified by this golden gate is `316b58e76de609069ddbf2667fe86f6218fb2143`.

A later documentation-only commit may advance repository HEAD without becoming a separately hardware-soaked firmware SHA. Stage28D is intentionally not started by this checkpoint.
EOF

python3 - <<'PY'
from pathlib import Path

def one(path, old, new):
    p=Path(path); s=p.read_text()
    if s.count(old)!=1: raise SystemExit(f'unexpected match count: {path}')
    p.write_text(s.replace(old,new,1))

one('docs/CURRENT_STATUS.md',
    '**Stage28A DONE -> Stage28B DONE -> Stage28C DONE -> pre-Stage28D golden hardening active**',
    '**Stage28A DONE -> Stage28B DONE -> Stage28C DONE -> pre-Stage28D golden gate COMPLETE -> Stage28D NOT STARTED**')
one('docs/CURRENT_STATUS.md',
    'Current pre-stage source after software hardening:\n\n`60da0a4d2a99f3045596b6a8a8bf362a0c6e1aca`',
    'Golden firmware/source checkpoint:\n\n`316b58e76de609069ddbf2667fe86f6218fb2143`')
one('docs/CURRENT_STATUS.md',
    '## Next work\n\nFinish the golden pre-Stage28D gate: broad regressions, ESP-IDF build, documentation consistency and a bounded hardware soak with no semantic mains actuation. Only then begin Stage28D semantic integration.',
    '## Golden checkpoint\n\nThe pre-Stage28D golden gate is complete on firmware/source `316b58e76de609069ddbf2667fe86f6218fb2143`. The exact SHA passed the full software gate and a 90-minute strict hardware soak with 526 records, zero resets/disconnects/parse errors/violations, stable memory, continuous SD progress, outputs fake-locked and no RF433 transmit observed. See `docs/PRESTAGE28D_GOLDEN_CHECKPOINT.md`.\n\n## Next work\n\nStage28D remains intentionally NOT STARTED and must begin only as an explicit later step.')
one('continuation.md',
    '**Stage28A DONE -> Stage28B DONE -> Stage28C DONE -> pre-Stage28D golden hardening active**',
    '**Stage28A DONE -> Stage28B DONE -> Stage28C DONE -> pre-Stage28D golden gate COMPLETE -> Stage28D NOT STARTED**')
one('continuation.md',
    '## Next gate\n\nBefore Stage28D semantic integration, finish the pre-stage golden gate:\n\n1. documentation/source consistency;\n2. complete host regression and ESP-IDF build;\n3. static/format checks available in the repository;\n4. bounded real-hardware regression/soak with outputs fake-locked;\n5. record one clean checkpoint SHA.\n\nOnly after that may Stage28D map the frozen hardware identity to a semantic actuator role. `exhaust_fan` remains the intended first semantic role, but it is not part of Stage28C hardware config.\n\nNo unattended mains-load control is authorized by this handoff.',
    '## Golden gate complete\n\nThe clean golden firmware/source checkpoint is `316b58e76de609069ddbf2667fe86f6218fb2143`. It passed the complete software gate and the same exact SHA passed a 5400-second strict real-hardware soak with 526 records, zero resets/disconnects/parse errors/violations, healthy sensor freshness, stable memory, continuous SD progress, outputs fake-locked and no RF433 transmit observed. Full evidence is in `docs/PRESTAGE28D_GOLDEN_CHECKPOINT.md`.\n\nStage28D is intentionally NOT STARTED. No later semantic integration is implied by this checkpoint.')
PY

git diff --check
PC="$(git rev-parse --show-toplevel)/.venv/bin/pre-commit"
test -x "$PC"
"$PC" run --all-files || { git diff --check; "$PC" run --all-files; }
git diff --check

python3 - <<'PY'
import subprocess
allowed={'continuation.md','docs/CURRENT_STATUS.md','docs/PRESTAGE28D_GOLDEN_CHECKPOINT.md'}
paths=[line[3:] for line in subprocess.check_output(['git','status','--porcelain'], text=True).splitlines()]
bad=[p for p in paths if p not in allowed]
if bad: raise SystemExit('out-of-scope paths: '+', '.join(bad))
PY

git add continuation.md docs/CURRENT_STATUS.md docs/PRESTAGE28D_GOLDEN_CHECKPOINT.md
git commit -m "Record pre-Stage28D golden checkpoint"
NEW="$(git rev-parse HEAD)"
export CMAKE_BUILD_PARALLEL_LEVEL=2
bash scripts/quality_gate_push.sh

git diff --check
test -z "$(git status --porcelain)"
git fetch -q origin "$BRANCH"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
git push origin HEAD:"$BRANCH"
git fetch -q origin "$BRANCH"
test "$(git rev-parse origin/$BRANCH)" = "$NEW"
printf 'PRESTAGE_GOLDEN_CHECKPOINT_READY commit=%s hardware_tested=%s docs_only=1 precommit=pass quality_gate=pass stage28d_started=0\n' "$NEW" "$EXPECTED"
