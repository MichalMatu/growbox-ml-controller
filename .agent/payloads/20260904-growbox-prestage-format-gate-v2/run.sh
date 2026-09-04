#!/usr/bin/env bash
set -euo pipefail

EXPECTED=484a7dfa262165fc3e61716cc162a49d61a2ee8a
BRANCH=mvp/environment-controller

# Retry from the exact remote source; the previous task only created a local
# formatting commit and was killed by the 4 GiB task memory limit before push.
git fetch -q origin "$BRANCH"
git reset --hard "$EXPECTED"
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
test -z "$(git status --porcelain)"

PC="$(git rev-parse --show-toplevel)/.venv/bin/pre-commit"
if [[ ! -x "$PC" ]]; then
  echo "pre-commit missing" >&2
  exit 2
fi

# Apply only repository-defined automatic formatting/fixes, then require the
# second pass to be clean.
set +e
"$PC" run --all-files
FIRST_RC=$?
set -e
if [[ "$FIRST_RC" -ne 0 && -z "$(git status --porcelain)" ]]; then
  echo "pre-commit failed without producing a fixable diff" >&2
  exit "$FIRST_RC"
fi

python3 - <<'PY'
import subprocess
paths=[]
for line in subprocess.check_output(['git','status','--porcelain'], text=True).splitlines():
    path=line[3:]
    if ' -> ' in path:
        path=path.split(' -> ',1)[1]
    paths.append(path)
invalid=[p for p in paths if not (p.startswith('src/') or p.startswith('test/'))]
if invalid:
    raise SystemExit('format hook touched out-of-scope paths: ' + ', '.join(invalid))
print('PRESTAGE_FORMAT_CHANGED_FILES count=%d' % len(paths))
for p in paths:
    print(p)
PY

git diff --check
"$PC" run --all-files
git diff --check
if [[ -z "$(git status --porcelain)" ]]; then
  echo "expected formatting changes were not present" >&2
  exit 1
fi

git add src test
git commit -m "Normalize formatting after Stage28C hardening"
NEW=$(git rev-parse HEAD)

# Bound host-build concurrency so the full gate stays below Local Agent's 4 GiB
# memory ceiling. quality_gate_push.sh and run_clang_tidy_host.sh both use
# `cmake --build --parallel` and honor this environment variable.
export CMAKE_BUILD_PARALLEL_LEVEL=2

bash scripts/quality_gate_push.sh

export GROWBOX_FIRMWARE_GIT_SHA="$NEW"
export GROWBOX_RF433_LOOPBACK_ENABLED=1
export GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0
export GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0
export STAGE27C_BUILD_DIR=build/idf-prestage-format-gate-v2
scripts/stage27c_crowpanel.sh build 2>&1 | tee /tmp/prestage-format-crowpanel-build-v2.log
if grep -q "unknown kconfig symbol" /tmp/prestage-format-crowpanel-build-v2.log; then
  echo "unknown Kconfig warning returned" >&2
  exit 1
fi

git diff --check
test -z "$(git status --porcelain)"
git fetch -q origin "$BRANCH"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
git push origin HEAD:"$BRANCH"
git fetch -q origin "$BRANCH"
test "$(git rev-parse origin/$BRANCH)" = "$NEW"

printf 'PRESTAGE_FORMAT_GATE_READY commit=%s parent=%s precommit=pass quality_gate=pass crowpanel_build=pass unknown_kconfig_warnings=0 cmake_parallel=2\n' "$NEW" "$EXPECTED"
