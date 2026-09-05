#!/usr/bin/env bash
set -euo pipefail
BRANCH="mvp/environment-controller"
EXPECTED_HEAD="e744e1fdf430ac35165f61a21f4c4b7fbf8a7e4f"
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
git fetch -q origin "$BRANCH"
git reset --hard "origin/$BRANCH" >/dev/null
test "$(git rev-parse HEAD)" = "$EXPECTED_HEAD"
test -z "$(git status --porcelain)"
# shellcheck disable=SC1091
source scripts/source_idf.sh

echo '[AGENT_PROGRESS] ffconf_readonly_definitions'
grep -R -n -E 'FF_FS_READONLY|FATFS_READONLY' "$IDF_PATH/components/fatfs" || true

echo '[AGENT_PROGRESS] diskio_registration_symbols'
grep -R -n -E 'ff_diskio_register|disk_write|sdmmc_write_sectors|esp_vfs_fat_sdspi_mount' "$IDF_PATH/components/fatfs" "$IDF_PATH/components/sdmmc" | head -n 240 || true

echo '[AGENT_PROGRESS] candidate_files'
find "$IDF_PATH/components/fatfs" -maxdepth 4 -type f \( -name 'ffconf.h' -o -name '*diskio*' -o -name '*sdmmc*' -o -name '*vfs_fat*' \) -print | sort

echo '[AGENT_PROGRESS] ffconf_context'
FFCONF="$(find "$IDF_PATH/components/fatfs" -type f -name ffconf.h | head -n1)"
test -n "$FFCONF"
grep -n -C 8 'FF_FS_READONLY' "$FFCONF" || true

echo '[AGENT_PROGRESS] sdmmc_diskio_source'
DISKIO="$(grep -R -l 'sdmmc_write_sectors' "$IDF_PATH/components/fatfs" | head -n1 || true)"
if [[ -n "$DISKIO" ]]; then
  sed -n '1,260p' "$DISKIO"
fi

echo '[AGENT_PROGRESS] sdspi_mount_source'
MOUNT="$(grep -R -l 'esp_vfs_fat_sdspi_mount' "$IDF_PATH/components/fatfs" | head -n1 || true)"
if [[ -n "$MOUNT" ]]; then
  sed -n '1,360p' "$MOUNT"
fi

test -z "$(git status --porcelain)"
echo 'SD_READONLY_CAPABILITY_INSPECTION_PASS'
