#!/usr/bin/env bash
set -euo pipefail

EXPECTED_REMOTE_HEAD=7f8ed8588408fccdfcd2ed8b3531f40f530bb02f
VALIDATION_COMMIT=1d60eec27bc2d5b2459eec11ff84b5ecc64cb16d
BRANCH=mvp/environment-controller

git fetch -q origin "$BRANCH"
REMOTE_HEAD="$(git rev-parse "origin/$BRANCH")"
test "$REMOTE_HEAD" = "$EXPECTED_REMOTE_HEAD"

git cat-file -e "$VALIDATION_COMMIT^{commit}"
PARENT="$(git rev-parse "$VALIDATION_COMMIT^")"
test "$PARENT" = "$EXPECTED_REMOTE_HEAD"

CHANGED="$(git diff-tree --no-commit-id --name-only -r "$VALIDATION_COMMIT")"
test "$CHANGED" = "docs/RF433_DEVICE_CODES.md"

git push origin "$VALIDATION_COMMIT:refs/heads/$BRANCH"
git fetch -q origin "$BRANCH"
test "$(git rev-parse "origin/$BRANCH")" = "$VALIDATION_COMMIT"

printf 'STAGE28D_RF_PHYSICAL_VALIDATION_PUBLISHED commit=%s parent=%s branch=%s\n' "$VALIDATION_COMMIT" "$EXPECTED_REMOTE_HEAD" "$BRANCH"
