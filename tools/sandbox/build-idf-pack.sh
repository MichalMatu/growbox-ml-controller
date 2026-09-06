#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

: "${IDF_PATH:?IDF_PATH must point to ESP-IDF 5.5.4}"
: "${IDF_TOOLS_PATH:?IDF_TOOLS_PATH must be set}"
OUT="${1:-$ROOT/build/sandbox-idf-pack}"
KEY="$(tools/sandbox/dependency-key.sh idf)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
STAGE="$TMP/stage"
mkdir -p "$STAGE/esp-idf" "$STAGE/idf-tools" "$STAGE/wheelhouse" "$STAGE/meta"

VERSION="$(git -C "$IDF_PATH" describe --tags --always 2>/dev/null || true)"
if [[ "$VERSION" != v5.5.4* && "$VERSION" != 5.5.4* ]]; then
  echo "Expected ESP-IDF v5.5.4, got: $VERSION" >&2
  exit 1
fi

python "$IDF_PATH/tools/idf_tools.py" install esp-clang
# shellcheck disable=SC1090
source "$IDF_PATH/export.sh"

rsync -a --delete \
  --exclude='.git' \
  --exclude='examples' \
  --exclude='docs' \
  "$IDF_PATH/" "$STAGE/esp-idf/"

if [[ -d "$IDF_TOOLS_PATH/tools" ]]; then
  rsync -a "$IDF_TOOLS_PATH/tools/" "$STAGE/idf-tools/tools/"
else
  echo "Missing IDF tools directory: $IDF_TOOLS_PATH/tools" >&2
  exit 1
fi

python -m pip list --format=freeze \
  | grep -vE '(@ file:|@ git\+|^-e )' \
  > "$STAGE/meta/idf-python-requirements.txt"
python -m pip download \
  --dest "$STAGE/wheelhouse" \
  -r "$STAGE/meta/idf-python-requirements.txt"

printf '5.5.4\n' > "$STAGE/meta/esp-idf-version.txt"
printf 'esp32s3\n' > "$STAGE/meta/target.txt"
printf '%s\n' "$VERSION" > "$STAGE/meta/idf-describe.txt"
python "$IDF_PATH/tools/idf_tools.py" list > "$STAGE/meta/idf-tools-list.txt"

tools/sandbox/finalize-pack.sh "$STAGE" growbox-idf "$KEY" "$OUT"
