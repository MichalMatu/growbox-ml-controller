#!/usr/bin/env bash
set -euo pipefail

TASK_ID="20260905-growbox-sd-readonly-extract-v1"
BRANCH="mvp/environment-controller"
EXPECTED_HEAD="e744e1fdf430ac35165f61a21f4c4b7fbf8a7e4f"
SAFE_SHA="3dfc4b552f669f628d5c9bee455a34666915088c"
ROOT="$(git rev-parse --show-toplevel)"
ARTIFACT_ROOT="$HOME/LocalAgentArtifacts/growbox-ml-controller/$TASK_ID"
RAW_DIR="$ARTIFACT_ROOT/raw"
EXTRACT_PROJECT="/tmp/$TASK_ID-project"
EXTRACT_BUILD="/tmp/$TASK_ID-build"
SAFE_WT="/tmp/$TASK_ID-safe-worktree"
SAFE_BUILD="/tmp/$TASK_ID-safe-build"
PORT=""
BOARD_NEEDS_SAFE=0

cd "$ROOT"

git fetch -q origin "$BRANCH"
git reset --hard "origin/$BRANCH" >/dev/null
test "$(git rev-parse HEAD)" = "$EXPECTED_HEAD"
test "$(git rev-parse "origin/$BRANCH")" = "$EXPECTED_HEAD"
test -z "$(git status --porcelain)"
echo "[AGENT_PROGRESS] source_head=$EXPECTED_HEAD"

# Use the repository's pinned ESP-IDF environment and fail before touching hardware
# unless the installed FatFs exposes a compile-time read-only mode.
# shellcheck disable=SC1091
source "$ROOT/scripts/source_idf.sh"
if ! grep -Rqs "config FATFS_READONLY" "$IDF_PATH/components/fatfs"; then
  echo "ESP-IDF FatFs does not expose CONFIG_FATFS_READONLY; refusing extraction" >&2
  exit 20
fi

echo "[AGENT_PROGRESS] fatfs_readonly_symbol=present idf_path=$IDF_PATH"

rm -rf "$ARTIFACT_ROOT" "$EXTRACT_PROJECT" "$EXTRACT_BUILD" "$SAFE_BUILD"
mkdir -p "$RAW_DIR" "$EXTRACT_PROJECT/main"

git worktree prune
git worktree remove --force "$SAFE_WT" >/dev/null 2>&1 || true
rm -rf "$SAFE_WT"
git worktree add --detach "$SAFE_WT" "$SAFE_SHA" >/dev/null

deferred_cleanup() {
  local rc=$?
  set +e
  if [[ "$BOARD_NEEDS_SAFE" == "1" && -n "$PORT" ]]; then
    echo "[AGENT_PROGRESS] emergency_safe_return=begin"
    GROWBOX_RF433_LOOPBACK_ENABLED=1 \
    GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=0 \
    GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=0 \
    GROWBOX_FIRMWARE_GIT_SHA="$SAFE_SHA" \
    STAGE27C_BUILD_DIR="$SAFE_BUILD" \
    PORT="$PORT" \
    bash "$SAFE_WT/scripts/stage27c_crowpanel.sh" flash
    echo "[AGENT_PROGRESS] emergency_safe_return=flash_attempted"
  fi
  git worktree remove --force "$SAFE_WT" >/dev/null 2>&1 || true
  rm -rf "$SAFE_WT" "$EXTRACT_PROJECT" "$EXTRACT_BUILD" "$SAFE_BUILD"
  exit "$rc"
}
trap deferred_cleanup EXIT INT TERM

# Build the exact previously hardware-qualified fake-locked image before replacing
# the board firmware, so a safe return image is already available locally.
(
  cd "$SAFE_WT"
  GROWBOX_RF433_LOOPBACK_ENABLED=1 \
  GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=0 \
  GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=0 \
  GROWBOX_FIRMWARE_GIT_SHA="$SAFE_SHA" \
  STAGE27C_BUILD_DIR="$SAFE_BUILD" \
  bash scripts/stage27c_crowpanel.sh build
)
grep -q '^GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED:STRING=0$' "$SAFE_BUILD/CMakeCache.txt"
grep -q '^GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED:STRING=0$' "$SAFE_BUILD/CMakeCache.txt"
grep -q '^GROWBOX_RF433_LOOPBACK_ENABLED:STRING=1$' "$SAFE_BUILD/CMakeCache.txt"
grep -aFq "$SAFE_SHA" "$SAFE_BUILD/growbox_ml_controller.bin"
echo "[AGENT_PROGRESS] safe_return_image=ready sha=$SAFE_SHA real_outputs=0 thermal_test=0"

cat > "$EXTRACT_PROJECT/CMakeLists.txt" <<'EOF'
cmake_minimum_required(VERSION 3.16)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(growbox_sd_readonly_extract)
EOF

cat > "$EXTRACT_PROJECT/main/CMakeLists.txt" <<'EOF'
idf_component_register(SRCS "main.c" INCLUDE_DIRS "." REQUIRES fatfs driver sdmmc mbedtls)
EOF

cat > "$EXTRACT_PROJECT/sdkconfig.defaults" <<'EOF'
CONFIG_FATFS_READONLY=y
CONFIG_ESP_CONSOLE_UART_DEFAULT=y
CONFIG_ESP_CONSOLE_UART_BAUDRATE=115200
CONFIG_LOG_DEFAULT_LEVEL_WARN=y
EOF

cat > "$EXTRACT_PROJECT/main/main.c" <<'EOF'
#include "sdkconfig.h"

#if !CONFIG_FATFS_READONLY
#error "The extraction firmware must be compiled with CONFIG_FATFS_READONLY=y"
#endif

#include <dirent.h>
#include <driver/gpio.h>
#include <driver/sdspi_host.h>
#include <driver/spi_master.h>
#include <esp_err.h>
#include <esp_vfs_fat.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <mbedtls/base64.h>
#include <sdmmc_cmd.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>

#define SD_HOST SPI3_HOST
#define SD_MOSI 40
#define SD_MISO 13
#define SD_CLK 39
#define SD_CS 10
#define SD_POWER 42
#define MOUNT_POINT "/sdcard"
#define LOG_DIR "/sdcard/GBLOG"
#define DATA_CHUNK 384

static bool probe_byte(spi_device_handle_t dev, uint8_t tx, uint8_t *rx) {
    spi_transaction_t tr = {0};
    tr.length = 8;
    tr.tx_buffer = &tx;
    tr.rx_buffer = rx;
    return spi_device_polling_transmit(dev, &tr) == ESP_OK;
}

static bool precondition_card(void) {
    spi_device_interface_config_t dev_cfg = {0};
    dev_cfg.clock_speed_hz = 400000;
    dev_cfg.mode = 0;
    dev_cfg.spics_io_num = -1;
    dev_cfg.queue_size = 1;
    spi_device_handle_t dev = NULL;
    if (spi_bus_add_device(SD_HOST, &dev_cfg, &dev) != ESP_OK) return false;

    gpio_set_direction((gpio_num_t)SD_CS, GPIO_MODE_OUTPUT);
    gpio_set_level((gpio_num_t)SD_CS, 1);
    uint8_t clocks[20];
    memset(clocks, 0xff, sizeof(clocks));
    spi_transaction_t clocks_tr = {0};
    clocks_tr.length = sizeof(clocks) * 8;
    clocks_tr.tx_buffer = clocks;
    if (spi_device_polling_transmit(dev, &clocks_tr) != ESP_OK) goto fail;

    gpio_set_level((gpio_num_t)SD_CS, 0);
    uint8_t ignored = 0xff;
    if (!probe_byte(dev, 0xff, &ignored)) goto fail;
    const uint8_t cmd0[6] = {0x40, 0, 0, 0, 0, 0x95};
    spi_transaction_t cmd_tr = {0};
    cmd_tr.length = sizeof(cmd0) * 8;
    cmd_tr.tx_buffer = cmd0;
    if (spi_device_polling_transmit(dev, &cmd_tr) != ESP_OK) goto fail;
    uint8_t response = 0xff;
    bool seen = false;
    for (unsigned i = 0; i < 16; ++i) {
        if (!probe_byte(dev, 0xff, &response)) goto fail;
        if ((response & 0x80U) == 0U) { seen = true; break; }
    }
    gpio_set_level((gpio_num_t)SD_CS, 1);
    spi_bus_remove_device(dev);
    return seen && response == 0x01U;

fail:
    gpio_set_level((gpio_num_t)SD_CS, 1);
    spi_bus_remove_device(dev);
    return false;
}

static bool has_jl_suffix(const char *name) {
    size_t n = strlen(name);
    return n >= 3 && strcmp(name + n - 3, ".JL") == 0;
}

static void print_name_hex(const char *name) {
    const unsigned char *p = (const unsigned char *)name;
    while (*p) { printf("%02X", (unsigned)*p++); }
}

static bool stream_file(unsigned index, const char *name, unsigned long long expected_size) {
    char path[512];
    if (snprintf(path, sizeof(path), "%s/%s", LOG_DIR, name) >= (int)sizeof(path)) return false;
    FILE *f = fopen(path, "rb");
    if (!f) return false;

    printf("FILE_BEGIN\t%u\t%llu\t", index, expected_size);
    print_name_hex(name);
    printf("\n");

    unsigned char raw[DATA_CHUNK];
    unsigned char enc[((DATA_CHUNK + 2) / 3) * 4 + 8];
    unsigned long long sent = 0;
    while (1) {
        size_t got = fread(raw, 1, sizeof(raw), f);
        if (got > 0) {
            size_t out_len = 0;
            if (mbedtls_base64_encode(enc, sizeof(enc) - 1, &out_len, raw, got) != 0) {
                fclose(f);
                return false;
            }
            enc[out_len] = 0;
            printf("DATA\t%u\t%s\n", index, enc);
            sent += got;
        }
        if (got < sizeof(raw)) {
            if (ferror(f)) { fclose(f); return false; }
            break;
        }
    }
    fclose(f);
    if (sent != expected_size) return false;
    printf("FILE_END\t%u\t%llu\n", index, sent);
    return true;
}

void app_main(void) {
    setvbuf(stdout, NULL, _IONBF, 0);
    printf("GBEXTRACT_BOOT readonly=1 spi_host=3 mosi=40 miso=13 clk=39 cs=10 power=42 path=/sdcard/GBLOG/*.JL\n");

    gpio_set_direction((gpio_num_t)SD_POWER, GPIO_MODE_OUTPUT);
    if (gpio_set_level((gpio_num_t)SD_POWER, 1) != ESP_OK) {
        printf("GBEXTRACT_ERROR power_gpio\n");
        goto halt;
    }
    vTaskDelay(pdMS_TO_TICKS(100));

    spi_bus_config_t bus = {0};
    bus.mosi_io_num = SD_MOSI;
    bus.miso_io_num = SD_MISO;
    bus.sclk_io_num = SD_CLK;
    bus.quadwp_io_num = -1;
    bus.quadhd_io_num = -1;
    bus.max_transfer_sz = 4096;
    esp_err_t err = spi_bus_initialize(SD_HOST, &bus, SPI_DMA_CH_AUTO);
    if (err != ESP_OK) {
        printf("GBEXTRACT_ERROR spi_init=%s\n", esp_err_to_name(err));
        goto halt;
    }
    if (!precondition_card()) {
        printf("GBEXTRACT_ERROR cmd0_precondition\n");
        goto halt;
    }

    sdmmc_host_t host = SDSPI_HOST_DEFAULT();
    host.slot = SD_HOST;
    sdspi_device_config_t slot = SDSPI_DEVICE_CONFIG_DEFAULT();
    slot.gpio_cs = (gpio_num_t)SD_CS;
    slot.host_id = SD_HOST;
    esp_vfs_fat_sdmmc_mount_config_t mount_cfg = {0};
    mount_cfg.format_if_mount_failed = false;
    mount_cfg.max_files = 2;
    mount_cfg.allocation_unit_size = 16 * 1024;
    sdmmc_card_t *card = NULL;
    err = esp_vfs_fat_sdspi_mount(MOUNT_POINT, &host, &slot, &mount_cfg, &card);
    if (err != ESP_OK) {
        printf("GBEXTRACT_ERROR mount=%s\n", esp_err_to_name(err));
        goto halt;
    }

    DIR *dir = opendir(LOG_DIR);
    if (!dir) {
        printf("GBEXTRACT_ERROR opendir=%s\n", LOG_DIR);
        goto halt;
    }
    closedir(dir);

    printf("GBEXTRACT_READY readonly=1\n");
    vTaskDelay(pdMS_TO_TICKS(15000));
    printf("GBEXTRACT_BEGIN\n");

    dir = opendir(LOG_DIR);
    if (!dir) {
        printf("GBEXTRACT_ERROR opendir_second=%s\n", LOG_DIR);
        goto halt;
    }
    unsigned index = 0;
    struct dirent *ent;
    while ((ent = readdir(dir)) != NULL) {
        if (!has_jl_suffix(ent->d_name)) continue;
        char path[512];
        if (snprintf(path, sizeof(path), "%s/%s", LOG_DIR, ent->d_name) >= (int)sizeof(path)) {
            printf("GBEXTRACT_ERROR path_too_long index=%u\n", index);
            closedir(dir);
            goto halt;
        }
        struct stat st;
        if (stat(path, &st) != 0 || !S_ISREG(st.st_mode)) {
            printf("GBEXTRACT_ERROR stat index=%u\n", index);
            closedir(dir);
            goto halt;
        }
        if (!stream_file(index, ent->d_name, (unsigned long long)st.st_size)) {
            printf("GBEXTRACT_ERROR stream index=%u\n", index);
            closedir(dir);
            goto halt;
        }
        ++index;
    }
    closedir(dir);
    printf("GBEXTRACT_DONE\t%u\n", index);

halt:
    // Deliberately do not unmount, format, create, truncate, rotate, or rewrite.
    // The temporary firmware stays inert until the exact fake-locked image is flashed.
    while (1) vTaskDelay(pdMS_TO_TICKS(1000));
}
EOF

(
  cd "$EXTRACT_PROJECT"
  idf.py -B "$EXTRACT_BUILD" -D "SDKCONFIG_DEFAULTS=$EXTRACT_PROJECT/sdkconfig.defaults" set-target esp32s3 >/dev/null
  idf.py -B "$EXTRACT_BUILD" -D "SDKCONFIG_DEFAULTS=$EXTRACT_PROJECT/sdkconfig.defaults" build
)
grep -q '^CONFIG_FATFS_READONLY=y$' "$EXTRACT_BUILD/sdkconfig"
grep -aFq 'GBEXTRACT_BOOT readonly=1' "$EXTRACT_BUILD/growbox_sd_readonly_extract.bin"
echo "[AGENT_PROGRESS] isolated_extractor=built fatfs_readonly=1 normal_logger=absent"

PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then PY="$(command -v python3)"; fi
PORT="$($PY -c 'from tools.stage27c_soak import detect_ch340_port; print(detect_ch340_port())')"
if [[ -z "$PORT" ]]; then
  echo "Unable to resolve CrowPanel serial port" >&2
  exit 21
fi
PROBE="$(esptool.py --port "$PORT" chip_id 2>&1)"
echo "$PROBE"
grep -q 'ESP32-S3' <<<"$PROBE"
echo "[AGENT_PROGRESS] board_verified port=$PORT chip=ESP32-S3"

BOARD_NEEDS_SAFE=1
(
  cd "$EXTRACT_PROJECT"
  idf.py -B "$EXTRACT_BUILD" -p "$PORT" flash
)

echo "[AGENT_PROGRESS] extractor_flashed; no RF/controller/logger code is present"

PORT_S3="$PORT" ARTIFACT_ROOT="$ARTIFACT_ROOT" RAW_DIR="$RAW_DIR" TASK_ID="$TASK_ID" EXPECTED_HEAD="$EXPECTED_HEAD" SAFE_SHA="$SAFE_SHA" "$PY" <<'PY'
import base64
import hashlib
import json
import os
import pathlib
import sys
import time
from datetime import datetime, timezone
import serial

port = os.environ['PORT_S3']
artifact_root = pathlib.Path(os.environ['ARTIFACT_ROOT'])
raw_dir = pathlib.Path(os.environ['RAW_DIR'])
raw_dir.mkdir(parents=True, exist_ok=True)
manifest_path = artifact_root / 'manifest.json'
transcript_path = artifact_root / 'extraction-transcript.txt'

files = []
current = None
started = False
ready = False
done_count = None
total_bytes = 0
last_progress = time.monotonic()
start = time.monotonic()
deadline = start + 6600
transcript = transcript_path.open('wb')

def fail(msg):
    raise RuntimeError(msg)

with serial.Serial(port, 115200, timeout=0.5, write_timeout=2, rtscts=False, dsrdtr=False) as s:
    try:
        s.dtr = False
        s.rts = False
    except Exception:
        pass
    while time.monotonic() < deadline:
        raw_line = s.readline()
        if not raw_line:
            if time.monotonic() - last_progress > 45:
                print(f'[AGENT_PROGRESS] extraction_wait elapsed_s={time.monotonic()-start:.1f} bytes={total_bytes}', flush=True)
                last_progress = time.monotonic()
            continue
        transcript.write(raw_line)
        transcript.flush()
        line = raw_line.decode('utf-8', 'replace').rstrip('\r\n')
        if line.startswith('GBEXTRACT_ERROR'):
            fail(line)
        if line.startswith('GBEXTRACT_READY'):
            if 'readonly=1' not in line:
                fail('extractor did not attest read-only mode')
            ready = True
            print('[AGENT_PROGRESS] sd_mounted_readonly=1 path=/sdcard/GBLOG', flush=True)
            last_progress = time.monotonic()
            continue
        if line == 'GBEXTRACT_BEGIN':
            if not ready:
                fail('stream began before read-only ready marker')
            started = True
            continue
        if not started:
            continue
        if line.startswith('FILE_BEGIN\t'):
            if current is not None:
                fail('nested FILE_BEGIN')
            parts = line.split('\t')
            if len(parts) != 4:
                fail('malformed FILE_BEGIN')
            index = int(parts[1]); expected_size = int(parts[2]); name_bytes = bytes.fromhex(parts[3])
            try:
                name = name_bytes.decode('utf-8')
            except UnicodeDecodeError:
                fail(f'non-UTF8 FAT filename at index {index}')
            if '/' in name or '\\' in name or name in ('.', '..'):
                fail(f'unsafe filename {name!r}')
            if index != len(files):
                fail(f'non-contiguous enumeration order index={index} expected={len(files)}')
            dest = raw_dir / name
            if dest.exists():
                fail(f'duplicate filename {name!r}')
            handle = dest.open('wb')
            current = {'index': index, 'filename': name, 'expected_size': expected_size,
                       'path': dest, 'handle': handle, 'hash': hashlib.sha256(), 'bytes': 0}
            print(f'[AGENT_PROGRESS] file_begin index={index} name={name} size={expected_size}', flush=True)
            last_progress = time.monotonic()
            continue
        if line.startswith('DATA\t'):
            if current is None:
                fail('DATA without FILE_BEGIN')
            parts = line.split('\t', 2)
            if len(parts) != 3 or int(parts[1]) != current['index']:
                fail('malformed DATA or wrong index')
            try:
                chunk = base64.b64decode(parts[2], validate=True)
            except Exception as exc:
                fail(f'base64 decode failed: {exc}')
            current['handle'].write(chunk)
            current['hash'].update(chunk)
            current['bytes'] += len(chunk)
            total_bytes += len(chunk)
            if time.monotonic() - last_progress > 10:
                print(f'[AGENT_PROGRESS] extraction_bytes={total_bytes} current_index={current["index"]}', flush=True)
                last_progress = time.monotonic()
            continue
        if line.startswith('FILE_END\t'):
            if current is None:
                fail('FILE_END without FILE_BEGIN')
            parts = line.split('\t')
            if len(parts) != 3 or int(parts[1]) != current['index']:
                fail('malformed FILE_END')
            firmware_sent = int(parts[2])
            current['handle'].flush()
            os.fsync(current['handle'].fileno())
            current['handle'].close()
            actual = current['bytes']
            if firmware_sent != actual or actual != current['expected_size']:
                fail(f'size mismatch index={current["index"]} expected={current["expected_size"]} host={actual} fw={firmware_sent}')
            digest = current['hash'].hexdigest()
            files.append({'index': current['index'], 'filename': current['filename'],
                          'size': actual, 'sha256': digest,
                          'relative_path': f'raw/{current["filename"]}'})
            print(f'[AGENT_PROGRESS] file_end index={current["index"]} size={actual} sha256={digest}', flush=True)
            current = None
            last_progress = time.monotonic()
            continue
        if line.startswith('GBEXTRACT_DONE\t'):
            if current is not None:
                fail('stream completed with open file')
            done_count = int(line.split('\t')[1])
            break

transcript.close()
if not ready or not started or done_count is None:
    fail('extractor did not complete')
if done_count != len(files):
    fail(f'file count mismatch firmware={done_count} host={len(files)}')
if not files:
    fail('no /sdcard/GBLOG/*.JL files were found; refusing to treat extraction as complete')

manifest = {
    'schema': 'growbox-sd-raw-extraction-v1',
    'task_id': os.environ['TASK_ID'],
    'repository': 'MichalMatu/growbox-ml-controller',
    'work_branch': 'mvp/environment-controller',
    'work_head': os.environ['EXPECTED_HEAD'],
    'last_physically_exercised_safe_sha': os.environ['SAFE_SHA'],
    'source_glob': '/sdcard/GBLOG/*.JL',
    'mount_policy': 'ESP-IDF FatFs CONFIG_FATFS_READONLY=y; format_if_mount_failed=false',
    'normal_telemetry_logger_started': False,
    'controller_or_rf_code_present_in_extractor': False,
    'host_extracted_at_utc': datetime.now(timezone.utc).isoformat(),
    'file_count': len(files),
    'total_bytes': sum(x['size'] for x in files),
    'files_in_fat_directory_order': files,
}
manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=False) + '\n')
print('[AGENT_PROGRESS] extraction_complete '+json.dumps({'files':len(files),'bytes':manifest['total_bytes'],'manifest':str(manifest_path)},separators=(',',':')), flush=True)
PY

# Return to the exact previously hardware-qualified fake-locked firmware.
GROWBOX_RF433_LOOPBACK_ENABLED=1 \
GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=0 \
GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=0 \
GROWBOX_FIRMWARE_GIT_SHA="$SAFE_SHA" \
STAGE27C_BUILD_DIR="$SAFE_BUILD" \
PORT="$PORT" \
bash "$SAFE_WT/scripts/stage27c_crowpanel.sh" flash

# Confirm the exact safe image and confirm the controlled load bank is still OFF
# without sending any RF command. If unexpected power is present, cut the Shelly
# master as the fail-closed fallback.
PORT_S3="$PORT" SAFE_SHA="$SAFE_SHA" ARTIFACT_ROOT="$ARTIFACT_ROOT" "$PY" <<'PY'
import json
import os
import pathlib
import statistics
import time
import urllib.request
import serial

port=os.environ['PORT_S3']; safe=os.environ['SAFE_SHA']; root=pathlib.Path(os.environ['ARTIFACT_ROOT'])

def collect(h, seconds):
    end=time.monotonic()+seconds; out=[]
    while time.monotonic()<end:
        b=h.read(4096)
        if b: out.append(b)
    return b''.join(out).decode(errors='replace')

def shelly_status():
    with urllib.request.urlopen('http://192.168.0.16/rpc/Switch.GetStatus?id=0', timeout=5) as r:
        return json.loads(r.read().decode())

def cutoff():
    body=json.dumps({'id':1,'method':'Switch.Set','params':{'id':0,'on':False,'tag':'growbox-sd-extract-failsafe'}}).encode()
    req=urllib.request.Request('http://192.168.0.16/rpc',data=body,headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=5) as r: r.read()

with serial.Serial(port,115200,timeout=.12,write_timeout=1,rtscts=False,dsrdtr=False) as h:
    try: h.dtr=False; h.rts=False
    except Exception: pass
    time.sleep(1); h.reset_input_buffer()
    text=''
    for _ in range(5):
        h.write(b'status\n'); h.flush(); text += collect(h,2.0)
        if safe in text and 'outputs=fake-locked' in text: break
if safe not in text or 'outputs=fake-locked' not in text:
    raise SystemExit('safe-return firmware identity/fake-lock not confirmed')

samples=[]; master_states=[]
for _ in range(7):
    st=shelly_status(); master_states.append(bool(st.get('output',False))); samples.append(float(st.get('apower',0.0))); time.sleep(.4)
master_on=all(master_states)
power=statistics.median(samples)
if master_on and power>8.0:
    cutoff()
    raise SystemExit(f'unexpected controlled-load power after extraction: {power:.3f}W; Shelly master cut OFF')

result={'safe_sha':safe,'outputs':'fake-locked','real_outputs':0,'thermal_test':0,
        'rf_commands_sent_during_extraction':0,'shelly_master_on':master_on,
        'median_power_w':power,'controlled_rf_loads_off': True}
(root/'safe-return.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print('[AGENT_PROGRESS] safe_return_confirmed '+json.dumps(result,separators=(',',':')), flush=True)
PY

BOARD_NEEDS_SAFE=0

test "$(git rev-parse HEAD)" = "$EXPECTED_HEAD"
test -z "$(git status --porcelain)"

echo "[AGENT_PROGRESS] manifest"
cat "$ARTIFACT_ROOT/manifest.json"
echo "[AGENT_PROGRESS] safe_return"
cat "$ARTIFACT_ROOT/safe-return.json"
echo "ARTIFACT_ROOT=$ARTIFACT_ROOT"
echo "SD_READONLY_EXTRACTION_PASS"
