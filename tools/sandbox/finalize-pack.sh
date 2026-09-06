#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
  echo "usage: $0 <stage-dir> <pack-name> <dependency-key> <output-dir>" >&2
  exit 2
fi

STAGE="$(realpath "$1")"
PACK_NAME="$2"
KEY="$3"
OUT="$(realpath -m "$4")"
PART_SIZE="${SANDBOX_PACK_PART_SIZE:-180M}"
LEVEL="${SANDBOX_ZSTD_LEVEL:-10}"

command -v zstd >/dev/null || { echo "zstd is required" >&2; exit 1; }
mkdir -p "$OUT/manifest"
rm -f "$OUT"/part-* "$OUT/manifest/"*

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
ARCHIVE="$TMP/${PACK_NAME}-${KEY}.tar.zst"

printf '%s\n' "$PACK_NAME" > "$STAGE/.pack-name"
printf '%s\n' "$KEY" > "$STAGE/.dependency-key"
printf 'x86_64-linux\n' > "$STAGE/.platform"

tar -C "$STAGE" -cf - . | zstd -T0 "-${LEVEL}" -q -o "$ARCHIVE"
sha256sum "$ARCHIVE" | awk '{print $1}' > "$OUT/manifest/archive.sha256"
stat -c '%s' "$ARCHIVE" > "$OUT/manifest/archive.size"
printf '%s\n' "$PACK_NAME" > "$OUT/manifest/pack-name.txt"
printf '%s\n' "$KEY" > "$OUT/manifest/dependency-key.txt"
printf 'x86_64-linux\n' > "$OUT/manifest/platform.txt"

split -b "$PART_SIZE" -d -a 3 "$ARCHIVE" "$OUT/part-"
(
  cd "$OUT"
  sha256sum part-* > manifest/parts.sha256
)

echo "pack=$PACK_NAME"
echo "key=$KEY"
echo "archive_sha256=$(cat "$OUT/manifest/archive.sha256")"
echo "parts=$(find "$OUT" -maxdepth 1 -name 'part-*' | wc -l)"
du -sh "$OUT"
