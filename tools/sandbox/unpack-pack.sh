#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <pack-dir> <destination>" >&2
  exit 2
fi

PACK="$(realpath "$1")"
DEST="$(realpath -m "$2")"
[[ -f "$PACK/manifest/archive.sha256" ]] || { echo "Missing pack manifest in $PACK" >&2; exit 1; }
[[ -f "$PACK/manifest/parts.sha256" ]] || { echo "Missing part checksums in $PACK" >&2; exit 1; }

(
  cd "$PACK"
  sha256sum -c manifest/parts.sha256
)

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
cat "$PACK"/part-* > "$TMP"
ACTUAL="$(sha256sum "$TMP" | awk '{print $1}')"
EXPECTED="$(cat "$PACK/manifest/archive.sha256")"
[[ "$ACTUAL" == "$EXPECTED" ]] || {
  echo "Archive checksum mismatch: expected $EXPECTED got $ACTUAL" >&2
  exit 1
}

rm -rf "$DEST"
mkdir -p "$DEST"
tar --zstd -xf "$TMP" -C "$DEST"

PACK_NAME="$(cat "$PACK/manifest/pack-name.txt")"
KEY="$(cat "$PACK/manifest/dependency-key.txt")"
[[ "$(cat "$DEST/.pack-name")" == "$PACK_NAME" ]]
[[ "$(cat "$DEST/.dependency-key")" == "$KEY" ]]
echo "$DEST"
