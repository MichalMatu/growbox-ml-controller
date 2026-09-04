#!/usr/bin/env bash
set -euo pipefail

EXPECTED=484a7dfa262165fc3e61716cc162a49d61a2ee8a
BRANCH=mvp/environment-controller

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

# First pass is allowed to rewrite formatting. The failed read-only golden gate
# proved clang-format is the only hook that currently wants to change files.
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

# Second pass must be fully clean.
"$PC" run --all-files

git diff --check
if [[ -z "$(git status --porcelain)" ]]; then
  echo "expected formatting changes were not present" >&2
  exit 1
fi

git add src test
git commit -m "Normalize formatting after Stage28C hardening"
NEW=$(git rev-parse HEAD)

# Run the full software quality gate on the committed candidate before pushing.
bash scripts/quality_gate_push.sh

export GROWBOX_FIRMWARE_GIT_SHA="$NEW"
export GROWBOX_RF433_LOOPBACK_ENABLED=1
export GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0
export GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0
export STAGE27C_BUILD_DIR=build/idf-prestage-format-gate-v1
scripts/stage27c_crowpanel.sh build 2>&1 | tee /tmp/prestage-format-crowpanel-build.log
if grep -q "unknown kconfig symbol" /tmp/prestage-format-crowpanel-build.log; then
  echo "unknown Kconfig warning returned" >&2
  exit 1
fi

git diff --check
test -z "$(git status --porcelain)"
git fetch -q origin "$BRANCH"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
git push origin HEAD:"$BRANCH"
test "$(git rev-parse origin/$BRANCH)" = "$NEW"

printf 'PRESTAGE_FORMAT_GATE_READY commit=%s parent=%s precommit=pass quality_gate=pass crowpanel_build=pass unknown_kconfig_warnings=0\n' "$NEW" "$EXPECTED"
