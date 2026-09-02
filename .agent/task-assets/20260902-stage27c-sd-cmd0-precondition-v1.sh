#!/usr/bin/env bash
set -euo pipefail

BASE=e749b4f0e89b9ab78e18f7a487c519b15a791207
git fetch origin mvp/environment-controller agent-control
git reset --hard origin/mvp/environment-controller
git clean -fd
test "$(git rev-parse HEAD)" = "$BASE"

python3 - <<'PY'
from pathlib import Path
p = Path('src/climate/storage/Stage27SdDataLogger.cpp')
s = p.read_text()
anchor = "constexpr std::uint32_t kPowerOnDelayMs = 100U;\n\n} // namespace"
insert = r'''constexpr std::uint32_t kPowerOnDelayMs = 100U;
constexpr std::uint32_t kSdProbeFrequencyHz = 400'000U;

bool transferProbeByte(spi_device_handle_t device, std::uint8_t tx,
                       std::uint8_t& rx) noexcept {
  spi_transaction_t transaction{};
  transaction.length = 8U;
  transaction.tx_buffer = &tx;
  transaction.rx_buffer = &rx;
  return spi_device_polling_transmit(device, &transaction) == ESP_OK;
}

bool preconditionCardForIdfMount(int cs_pin) noexcept {
  spi_device_interface_config_t device_config{};
  device_config.clock_speed_hz = static_cast<int>(kSdProbeFrequencyHz);
  device_config.mode = 0;
  device_config.spics_io_num = -1;
  device_config.queue_size = 1;

  spi_device_handle_t device = nullptr;
  const esp_err_t add_error = spi_bus_add_device(kSdSpiHost, &device_config, &device);
  if (add_error != ESP_OK) {
    ESP_LOGW(kTag, "SD precondition device add failed: %s", esp_err_to_name(add_error));
    return false;
  }

  const auto cs = static_cast<gpio_num_t>(cs_pin);
  auto cleanup = [&]() noexcept {
    gpio_set_level(cs, 1);
    const esp_err_t remove_error = spi_bus_remove_device(device);
    if (remove_error != ESP_OK) {
      ESP_LOGW(kTag, "SD precondition device remove failed: %s",
               esp_err_to_name(remove_error));
    }
  };

  if (gpio_set_direction(cs, GPIO_MODE_OUTPUT) != ESP_OK || gpio_set_level(cs, 1) != ESP_OK) {
    ESP_LOGW(kTag, "SD precondition CS setup failed on GPIO%d", cs_pin);
    cleanup();
    return false;
  }

  std::uint8_t clocks[20];
  std::memset(clocks, 0xFF, sizeof(clocks));
  spi_transaction_t clock_transaction{};
  clock_transaction.length = sizeof(clocks) * 8U;
  clock_transaction.tx_buffer = clocks;
  if (spi_device_polling_transmit(device, &clock_transaction) != ESP_OK) {
    ESP_LOGW(kTag, "SD precondition startup clocks failed");
    cleanup();
    return false;
  }

  if (gpio_set_level(cs, 0) != ESP_OK) {
    ESP_LOGW(kTag, "SD precondition CS select failed");
    cleanup();
    return false;
  }

  // The proven Arduino transport on this CrowPanel intentionally ignores the
  // initial busy/wait result and sends CMD0 anyway. Reproduce only that narrow
  // compatibility preamble before handing the card back to ESP-IDF SDSPI.
  std::uint8_t ignored = 0xFF;
  if (!transferProbeByte(device, 0xFF, ignored)) {
    ESP_LOGW(kTag, "SD precondition initial probe failed");
    cleanup();
    return false;
  }

  const std::uint8_t cmd0[6] = {0x40, 0x00, 0x00, 0x00, 0x00, 0x95};
  spi_transaction_t cmd_transaction{};
  cmd_transaction.length = sizeof(cmd0) * 8U;
  cmd_transaction.tx_buffer = cmd0;
  if (spi_device_polling_transmit(device, &cmd_transaction) != ESP_OK) {
    ESP_LOGW(kTag, "SD precondition CMD0 transmit failed");
    cleanup();
    return false;
  }

  std::uint8_t response = 0xFF;
  bool response_seen = false;
  for (unsigned attempt = 0; attempt < 16U; ++attempt) {
    if (!transferProbeByte(device, 0xFF, response)) {
      ESP_LOGW(kTag, "SD precondition response read failed");
      cleanup();
      return false;
    }
    if ((response & 0x80U) == 0U) {
      response_seen = true;
      break;
    }
  }

  cleanup();
  if (!response_seen || response != 0x01U) {
    ESP_LOGW(kTag, "SD precondition CMD0 response=0x%02x", response);
    return false;
  }

  ESP_LOGI(kTag, "SD precondition CMD0 response=0x01");
  return true;
}

} // namespace'''
if anchor not in s:
    raise SystemExit('constant anchor not found')
s = s.replace(anchor, insert, 1)
anchor2 = "    spi_initialized_ = true;\n  }\n\n  sdmmc_host_t host = SDSPI_HOST_DEFAULT();"
replace2 = "    spi_initialized_ = true;\n  }\n\n  if (!preconditionCardForIdfMount(pins_.cs)) {\n    mount_errors_.fetch_add(1U, std::memory_order_relaxed);\n    releaseSpiBus();\n    disableStoragePower();\n    return false;\n  }\n\n  sdmmc_host_t host = SDSPI_HOST_DEFAULT();"
if anchor2 not in s:
    raise SystemExit('mount anchor not found')
s = s.replace(anchor2, replace2, 1)
p.write_text(s)
PY

.venv/bin/pre-commit run clang-format --files src/climate/storage/Stage27SdDataLogger.cpp || true
.venv/bin/pre-commit run --files src/climate/storage/Stage27SdDataLogger.cpp
git diff --check
.venv/bin/python -m pytest tests/test_stage27c_soak.py -q
cmake -S test/host -B build/host-tests
cmake --build build/host-tests --target stage27_telemetry_tests --parallel
ctest --test-dir build/host-tests -R '^stage27_telemetry_tests$' --output-on-failure
grep -q 'SD precondition CMD0 response=0x01' src/climate/storage/Stage27SdDataLogger.cpp
grep -q "kSdProbeFrequencyHz = 400'000U" src/climate/storage/Stage27SdDataLogger.cpp

git add src/climate/storage/Stage27SdDataLogger.cpp
git commit -m 'Precondition CrowPanel SD before IDF mount'
NEW_SHA="$(git rev-parse HEAD)"
echo "[AGENT_PROGRESS] sd_cmd0_precondition_sha=$NEW_SHA"

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
sleep 2
PROBE_POST="$(python -m esptool --port "$PORT_S3" chip_id 2>&1)"
echo "$PROBE_POST"
grep -q 'ESP32-S3' <<<"$PROBE_POST"

PORT_S3="$PORT_S3" .venv/bin/python - <<'PY'
import os, time, serial
port = os.environ['PORT_S3']
end = time.monotonic() + 20
lines = []
with serial.Serial(port, 115200, timeout=0.2, rtscts=False, dsrdtr=False) as s:
    s.rts = False
    s.dtr = False
    while time.monotonic() < end:
        raw = s.readline()
        if not raw:
            continue
        line = raw.decode('utf-8', 'replace').rstrip()
        if 'stage27_sd' in line or 'Stage27 soak boot' in line:
            lines.append(line)
for line in lines:
    print(line)
if not any('SD precondition CMD0 response=0x01' in line for line in lines):
    raise SystemExit('CMD0 precondition did not receive idle response')
if not any('SD mounted on SPI3' in line for line in lines):
    raise SystemExit('SD did not mount after successful CMD0 precondition')
PY

OUT="build/stage27c-sd-cmd0-precondition-${NEW_SHA:0:7}"
rm -rf "$OUT"
.venv/bin/python tools/stage27c_soak.py --port "$PORT_S3" --output-dir "$OUT" --duration 300 --progress-seconds 60 --expected-sha "$NEW_SHA" --max-scd-age-ms 15000 --max-tp-age-ms 60000 --max-xiaomi-age-ms 30000 --require-sd --strict
echo '[AGENT_PROGRESS] sd_cmd0_precondition_smoke_summary'
cat "$OUT/summary.json"
test -z "$(git status --short)"
echo "PUBLISHED_SHA=$NEW_SHA"
