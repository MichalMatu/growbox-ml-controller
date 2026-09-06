#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

OUT="${1:-$ROOT/build/sandbox-source}"
mkdir -p "$OUT"
SHA="$(git rev-parse HEAD)"
HOST_KEY="$(tools/sandbox/dependency-key.sh host)"
WEB_KEY="$(tools/sandbox/dependency-key.sh web)"
IDF_KEY="$(tools/sandbox/dependency-key.sh idf)"
NAME="growbox-source-${SHA}"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git archive HEAD | tar -C "$TMP" -xf -
mkdir -p "$TMP/.sandbox-snapshot"
printf '%s\n' "$SHA" > "$TMP/.sandbox-snapshot/git-sha.txt"
printf '%s\n' "$HOST_KEY" > "$TMP/.sandbox-snapshot/host-key.txt"
printf '%s\n' "$WEB_KEY" > "$TMP/.sandbox-snapshot/web-key.txt"
printf '%s\n' "$IDF_KEY" > "$TMP/.sandbox-snapshot/idf-key.txt"
printf '5.5.4\n' > "$TMP/.sandbox-snapshot/esp-idf-version.txt"
printf '3.11\n' > "$TMP/.sandbox-snapshot/python-version.txt"
printf '22\n' > "$TMP/.sandbox-snapshot/node-major.txt"
printf '11.10.0\n' > "$TMP/.sandbox-snapshot/pnpm-version.txt"

ARCHIVE="$OUT/${NAME}.tar.zst"
tar -C "$TMP" -cf - . | zstd -T0 -10 -q -o "$ARCHIVE"
(
  cd "$OUT"
  sha256sum "${NAME}.tar.zst" > "${NAME}.tar.zst.sha256"
)

echo "$ARCHIVE"
cat "${ARCHIVE}.sha256"
