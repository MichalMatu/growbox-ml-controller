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

# Install the complete tool set selected by this ESP-IDF installation, not just
# the compiler used by a single esp32s3 build. The official export path validates
# every tool recorded in idf-env.json (including debugger tools), so an offline
# pack must preserve that complete environment. esp-clang is an additional tool
# used by this repository's clang-check profile.
python "$IDF_PATH/tools/idf_tools.py" install
python "$IDF_PATH/tools/idf_tools.py" install esp-clang
# shellcheck disable=SC1090
source "$IDF_PATH/export.sh"

# Fail while constructing the pack if the ESP-IDF environment itself cannot be
# exported. This prevents publishing an archive which compiles in the producer
# job only because the runner happens to contain extra tools.
python "$IDF_PATH/tools/idf_tools.py" export --format key-value \
  > "$STAGE/meta/idf-export.txt"

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

# idf_tools.py needs these files from the IDF_TOOLS_PATH root to reproduce the
# selected target/tool set and to validate the Python environment. Without
# idf-env.json it loses the install selection; without the constraints file
# export/idf.py fails even when all tool binaries are already present.
[[ -f "$IDF_TOOLS_PATH/idf-env.json" ]] || {
  echo "Missing IDF environment metadata: $IDF_TOOLS_PATH/idf-env.json" >&2
  exit 1
}
cp "$IDF_TOOLS_PATH/idf-env.json" "$STAGE/idf-tools/"

shopt -s nullglob
CONSTRAINTS=("$IDF_TOOLS_PATH"/espidf.constraints.*.txt)
shopt -u nullglob
(( ${#CONSTRAINTS[@]} > 0 )) || {
  echo "Missing ESP-IDF constraints file under $IDF_TOOLS_PATH" >&2
  exit 1
}
cp "${CONSTRAINTS[@]}" "$STAGE/idf-tools/"

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
