#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
git fetch -q origin agent-control
BASE=/tmp/20260905-growbox-sd-readonly-extract-v1-base.sh
RUN=/tmp/20260905-growbox-sd-readonly-extract-v2-run.sh
git show origin/agent-control:.agent/payloads/20260905-growbox-sd-readonly-extract-v1/run.sh > "$BASE"
python3 - "$BASE" "$RUN" <<'PY'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text()
s=s.replace('20260905-growbox-sd-readonly-extract-v1','20260905-growbox-sd-readonly-extract-v2')
old='''if ! grep -Rqs "config FATFS_READONLY" "$IDF_PATH/components/fatfs"; then
  echo "ESP-IDF FatFs does not expose CONFIG_FATFS_READONLY; refusing extraction" >&2
  exit 20
fi

echo "[AGENT_PROGRESS] fatfs_readonly_symbol=present idf_path=$IDF_PATH"
'''
new='''FFCONF_SOURCE="$IDF_PATH/components/fatfs/src/ffconf.h"
test -f "$FFCONF_SOURCE"
grep -Eq '^#define[[:space:]]+FF_FS_READONLY[[:space:]]+0' "$FFCONF_SOURCE"
echo "[AGENT_PROGRESS] fatfs_readonly_upstream_default=0; preparing isolated vendored read-only component"
'''
if old not in s:
    raise SystemExit('v2 readonly capability block target not found')
s=s.replace(old,new,1)
old='mkdir -p "$RAW_DIR" "$EXTRACT_PROJECT/main"\n'
new='''mkdir -p "$RAW_DIR" "$EXTRACT_PROJECT/main" "$EXTRACT_PROJECT/components"
cp -R "$IDF_PATH/components/fatfs" "$EXTRACT_PROJECT/components/fatfs"
python3 - "$EXTRACT_PROJECT/components/fatfs" <<'PY_FATFS'
from pathlib import Path
import sys
root=Path(sys.argv[1])
ffconf=root/'src'/'ffconf.h'
s=ffconf.read_text()
old='#define FF_FS_READONLY\\t0'
if old not in s:
    old='#define FF_FS_READONLY  0'
if old not in s:
    raise SystemExit('FF_FS_READONLY upstream definition not found')
s=s.replace(old, old[:-1]+'1', 1)
ffconf.write_text(s)
diskio=root/'diskio'/'diskio_sdmmc.c'
d=diskio.read_text()
needle='sdmmc_write_sectors(card, buff, sector, count)'
if d.count(needle) != 1:
    raise SystemExit(f'unexpected sdmmc write call count={d.count(needle)}')
d=d.replace(needle, '((void)buff, (void)sector, (void)count, ESP_ERR_NOT_SUPPORTED)', 1)
diskio.write_text(d)
PY_FATFS
grep -Eq '^#define[[:space:]]+FF_FS_READONLY[[:space:]]+1' "$EXTRACT_PROJECT/components/fatfs/src/ffconf.h"
! grep -q 'sdmmc_write_sectors(card, buff, sector, count)' "$EXTRACT_PROJECT/components/fatfs/diskio/diskio_sdmmc.c"
echo "[AGENT_PROGRESS] read_only_guards=FF_FS_READONLY_1+sdmmc_diskio_write_disabled"
'''
if old not in s:
    raise SystemExit('v2 project mkdir target not found')
s=s.replace(old,new,1)
s=s.replace('CONFIG_FATFS_READONLY=y\n','',1)
old='''#include "sdkconfig.h"

#if !CONFIG_FATFS_READONLY
#error "The extraction firmware must be compiled with CONFIG_FATFS_READONLY=y"
#endif
'''
new='''#include "ff.h"

#if !FF_FS_READONLY
#error "The extraction firmware must be compiled with FF_FS_READONLY=1"
#endif
'''
if old not in s:
    raise SystemExit('v2 main readonly assertion target not found')
s=s.replace(old,new,1)
old='''grep -q '^CONFIG_FATFS_READONLY=y$' "$EXTRACT_BUILD/sdkconfig"
grep -aFq 'GBEXTRACT_BOOT readonly=1' "$EXTRACT_BUILD/growbox_sd_readonly_extract.bin"
echo "[AGENT_PROGRESS] isolated_extractor=built fatfs_readonly=1 normal_logger=absent"
'''
new='''grep -Eq '^#define[[:space:]]+FF_FS_READONLY[[:space:]]+1' "$EXTRACT_PROJECT/components/fatfs/src/ffconf.h"
! grep -q 'sdmmc_write_sectors(card, buff, sector, count)' "$EXTRACT_PROJECT/components/fatfs/diskio/diskio_sdmmc.c"
grep -q "$EXTRACT_PROJECT/components/fatfs/src/ff.c" "$EXTRACT_BUILD/build.ninja"
grep -aFq 'GBEXTRACT_BOOT readonly=1' "$EXTRACT_BUILD/growbox_sd_readonly_extract.bin"
echo "[AGENT_PROGRESS] isolated_extractor=built fatfs_readonly=1 diskio_write_disabled=1 normal_logger=absent"
'''
if old not in s:
    raise SystemExit('v2 post-build readonly assertion target not found')
s=s.replace(old,new,1)
s=s.replace("'mount_policy': 'ESP-IDF FatFs CONFIG_FATFS_READONLY=y; format_if_mount_failed=false',",
            "'mount_policy': 'isolated vendored FatFs FF_FS_READONLY=1 + SDMMC diskio write path disabled; format_if_mount_failed=false',",1)
Path(sys.argv[2]).write_text(s)
PY
bash -n "$RUN"
bash "$RUN"
