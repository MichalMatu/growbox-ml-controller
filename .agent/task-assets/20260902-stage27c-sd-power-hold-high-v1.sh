#!/usr/bin/env bash
set -euo pipefail

BASE=de88b381f9c5442029dfe54efc05cbba813b94f8

git fetch origin mvp/environment-controller agent-control
git reset --hard origin/mvp/environment-controller
git clean -fd
test "$(git rev-parse HEAD)" = "$BASE"

python3 - <<'PY'
from pathlib import Path
p = Path('src/climate/storage/Stage27SdDataLogger.cpp')
s = p.read_text()
old = '''    const esp_err_t level_error = gpio_set_level(power_gpio, 0);\n    if (level_error != ESP_OK) {\n      ESP_LOGE(kTag, "Failed to initialize SD power GPIO %d low: %s", pins_.power,\n               esp_err_to_name(level_error));\n      return false;\n    }\n    ESP_LOGI(kTag, "SD power control initialized on GPIO%d", pins_.power);'''
new = '''    const esp_err_t level_error = gpio_set_level(power_gpio, 1);\n    if (level_error != ESP_OK) {\n      ESP_LOGE(kTag, "Failed to initialize SD power GPIO %d high: %s", pins_.power,\n               esp_err_to_name(level_error));\n      return false;\n    }\n    ESP_LOGI(kTag, "SD power diagnostic: GPIO%d held HIGH continuously", pins_.power);'''
if old not in s:
    raise SystemExit('begin power anchor not found')
s = s.replace(old, new, 1)
old2 = '''  card_ = nullptr;\n  const esp_err_t mount_error =\n      esp_vfs_fat_sdspi_mount(kMountPoint, &host, &slot_config, &mount_config, &card_);\n  if (mount_error != ESP_OK) {\n    mount_errors_.fetch_add(1U, std::memory_order_relaxed);\n    ESP_LOGW(kTag, "SD mount failed at uptime=%llu: %s",\n             static_cast<unsigned long long>(snapshot.uptime_ms), esp_err_to_name(mount_error));'''
new2 = '''  card_ = nullptr;\n  if (pins_.power >= 0) {\n    ESP_LOGI(kTag, "SD power diagnostic: level before mount=%d",\n             gpio_get_level(static_cast<gpio_num_t>(pins_.power)));\n  }\n  const esp_err_t mount_error =\n      esp_vfs_fat_sdspi_mount(kMountPoint, &host, &slot_config, &mount_config, &card_);\n  if (mount_error != ESP_OK) {\n    mount_errors_.fetch_add(1U, std::memory_order_relaxed);\n    if (pins_.power >= 0) {\n      ESP_LOGI(kTag, "SD power diagnostic: level after mount failure=%d",\n               gpio_get_level(static_cast<gpio_num_t>(pins_.power)));\n    }\n    ESP_LOGW(kTag, "SD mount failed at uptime=%llu: %s",\n             static_cast<unsigned long long>(snapshot.uptime_ms), esp_err_to_name(mount_error));'''
if old2 not in s:
    raise SystemExit('mount diagnostic anchor not found')
s = s.replace(old2, new2, 1)
old3 = '''void Stage27SdDataLogger::disableStoragePower() noexcept {\n  if (pins_.power < 0) {\n    return;\n  }\n  const esp_err_t error = gpio_set_level(static_cast<gpio_num_t>(pins_.power), 0);\n  if (error != ESP_OK) {\n    ESP_LOGW(kTag, "Failed to disable SD power GPIO %d: %s", pins_.power, esp_err_to_name(error));\n  }\n}'''
new3 = '''void Stage27SdDataLogger::disableStoragePower() noexcept {\n  if (pins_.power < 0) {\n    return;\n  }\n  // Diagnostic only: keep the CrowPanel TF power/ground gate asserted continuously.\n  const esp_err_t error = gpio_set_level(static_cast<gpio_num_t>(pins_.power), 1);\n  if (error != ESP_OK) {\n    ESP_LOGW(kTag, "Failed to keep SD power GPIO %d high: %s", pins_.power, esp_err_to_name(error));\n  }\n}'''
if old3 not in s:
    raise SystemExit('disable power anchor not found')
s = s.replace(old3, new3, 1)
p.write_text(s)
PY

.venv/bin/pre-commit run clang-format --files src/climate/storage/Stage27SdDataLogger.cpp || true
.venv/bin/pre-commit run --files src/climate/storage/Stage27SdDataLogger.cpp
git diff --check
.venv/bin/python -m pytest tests/test_stage27c_soak.py -q

git add src/climate/storage/Stage27SdDataLogger.cpp
git commit -m 'Hold CrowPanel SD power high for diagnostic'
NEW_SHA="$(git rev-parse HEAD)"
echo "[AGENT_PROGRESS] sd_power_hold_sha=$NEW_SHA"

bash scripts/stage27c_crowpanel.sh clean
GROWBOX_FIRMWARE_GIT_SHA="$NEW_SHA" bash scripts/stage27c_crowpanel.sh build
test -f build/idf-stage27c-crowpanel/growbox_ml_controller.bin
grep -aFq "$NEW_SHA" build/idf-stage27c-crowpanel/growbox_ml_controller.bin
git push origin HEAD:mvp/environment-controller
test -z "$(git status --short)"

PORT_S3="$(.venv/bin/python -c 'from tools.stage27c_soak import detect_ch340_port; print(detect_ch340_port())')"
source scripts/source_idf.sh
PROBE="$(python -m esptool --port "$PORT_S3" chip_id 2>&1)"
echo "$PROBE"
grep -q 'ESP32-S3' <<<"$PROBE"
PORT="$PORT_S3" GROWBOX_FIRMWARE_GIT_SHA="$NEW_SHA" bash scripts/stage27c_crowpanel.sh flash

# Force one clean reset, then capture boot immediately.
python -m esptool --port "$PORT_S3" chip_id >/tmp/stage27c-power-probe.txt 2>&1
cat /tmp/stage27c-power-probe.txt
grep -q 'ESP32-S3' /tmp/stage27c-power-probe.txt

PORT_S3="$PORT_S3" .venv/bin/python - <<'PY'
import os, time, serial
port=os.environ['PORT_S3']
end=time.monotonic()+15
lines=[]
with serial.Serial(port,115200,timeout=0.1,rtscts=False,dsrdtr=False) as s:
    s.rts=False
    s.dtr=False
    while time.monotonic()<end:
        raw=s.readline()
        if not raw:
            continue
        line=raw.decode('utf-8','replace').rstrip()
        if 'stage27_sd' in line or 'Stage27 soak boot' in line or 'soak_v=2' in line:
            lines.append(line)
            print(line)
required=[
    'held HIGH continuously',
    'level before mount=1',
]
for token in required:
    if not any(token in line for line in lines):
        raise SystemExit('Missing power diagnostic token: '+token)
mounted=any('SD mounted on SPI3' in line for line in lines)
failed=any('SD mount failed' in line for line in lines)
after_high=any('level after mount failure=1' in line for line in lines)
print('[AGENT_PROGRESS] power_hold_mount_seen=%s' % str(mounted).lower())
print('[AGENT_PROGRESS] power_hold_mount_failed=%s' % str(failed).lower())
print('[AGENT_PROGRESS] power_hold_after_failure_high=%s' % str(after_high).lower())
if failed and not after_high:
    raise SystemExit('Mount failed without proof GPIO42 remained high')
if not mounted:
    raise SystemExit('SD did not mount with GPIO42 held continuously high')
PY

OUT="build/stage27c-sd-power-hold-${NEW_SHA:0:7}"
rm -rf "$OUT"
.venv/bin/python tools/stage27c_soak.py --port "$PORT_S3" --output-dir "$OUT" --duration 300 --progress-seconds 60 --expected-sha "$NEW_SHA" --max-scd-age-ms 15000 --max-tp-age-ms 60000 --max-xiaomi-age-ms 30000 --require-sd --strict
echo '[AGENT_PROGRESS] power_hold_strict_smoke_summary'
cat "$OUT/summary.json"
test -z "$(git status --short)"
echo "PUBLISHED_SHA=$NEW_SHA"
