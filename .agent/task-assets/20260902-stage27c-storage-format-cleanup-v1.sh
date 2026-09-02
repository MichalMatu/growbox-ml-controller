#!/usr/bin/env bash
set -euo pipefail

EXPECTED_SHA="ebac362a67689bb0b58cd541c75deddf516a9bfe"
WORK_BRANCH="mvp/environment-controller"

git fetch origin "$WORK_BRANCH"
REMOTE_SHA="$(git rev-parse "origin/$WORK_BRANCH")"
if [[ "$REMOTE_SHA" != "$EXPECTED_SHA" ]]; then
  echo "Expected remote $EXPECTED_SHA but found $REMOTE_SHA" >&2
  exit 2
fi

git reset --hard "$REMOTE_SHA"

echo "[AGENT_PROGRESS] format_base_sha=$REMOTE_SHA"

PRECOMMIT=".venv/bin/pre-commit"
if [[ ! -x "$PRECOMMIT" ]]; then
  PRECOMMIT="$(command -v pre-commit)"
fi

"$PRECOMMIT" run --all-files || true
git diff --check
"$PRECOMMIT" run --all-files

if git diff --quiet; then
  echo "[AGENT_PROGRESS] formatting_changes=0"
  echo "PUBLISHED_SHA=$REMOTE_SHA"
  exit 0
fi

git add -u
git diff --cached --check
git commit -m "Format Stage27C storage refactor"
NEW_SHA="$(git rev-parse HEAD)"
echo "[AGENT_PROGRESS] formatting_changes=1 formatted_sha=$NEW_SHA"
git push origin "HEAD:$WORK_BRANCH"

test -z "$(git status --porcelain)"
echo "PUBLISHED_SHA=$NEW_SHA"
