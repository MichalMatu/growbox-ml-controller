from pathlib import Path

path = Path("src/CMakeLists.txt")
text = path.read_text(encoding="utf-8")

req_anchor = """    esp_driver_gpio
    nvs_flash
"""
if req_anchor not in text:
    raise SystemExit("CMake REQUIRES anchor not found")
text = text.replace(req_anchor, """    esp_driver_gpio
    esp_driver_rmt
    nvs_flash
""", 1)

src_anchor = """      \"climate/native/Ds3231ClockSource.cpp\"
  )
"""
if src_anchor not in text:
    raise SystemExit("CMake source anchor not found")
text = text.replace(src_anchor, """      \"climate/native/Ds3231ClockSource.cpp\"
      \"climate/rf433/Rf433ProtocolCodec.cpp\"
      \"climate/rf433/Rf433RmtLoopback.cpp\"
  )
""", 1)

cache_anchor = """set(GROWBOX_SD_POWER_GPIO \"-1\" CACHE STRING \"Stage27 SD power-enable GPIO\")
"""
if cache_anchor not in text:
    raise SystemExit("CMake cache anchor not found")
text = text.replace(cache_anchor, cache_anchor + """set(GROWBOX_RF433_LOOPBACK_ENABLED \"0\" CACHE STRING \"Enable Stage28 RF433 loopback transport\")
set(GROWBOX_RF433_LOOPBACK_AUTO_SMOKE \"0\" CACHE STRING \"Run one Stage28 RF433 boot loopback smoke\")
set(GROWBOX_RF433_TX_GPIO \"8\" CACHE STRING \"Stage28 RF433 TX GPIO\")
set(GROWBOX_RF433_RX_GPIO \"14\" CACHE STRING \"Stage28 RF433 RX GPIO\")
""", 1)

defs_anchor = """    GROWBOX_SD_POWER_GPIO=${GROWBOX_SD_POWER_GPIO}
)
"""
if defs_anchor not in text:
    raise SystemExit("CMake definitions anchor not found")
text = text.replace(defs_anchor, """    GROWBOX_SD_POWER_GPIO=${GROWBOX_SD_POWER_GPIO}
    GROWBOX_RF433_LOOPBACK_ENABLED=${GROWBOX_RF433_LOOPBACK_ENABLED}
    GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=${GROWBOX_RF433_LOOPBACK_AUTO_SMOKE}
    GROWBOX_RF433_TX_GPIO=${GROWBOX_RF433_TX_GPIO}
    GROWBOX_RF433_RX_GPIO=${GROWBOX_RF433_RX_GPIO}
)
""", 1)
path.write_text(text, encoding="utf-8")

path = Path("scripts/stage27c_crowpanel.sh")
text = path.read_text(encoding="utf-8")
env_anchor = """SD_CMD0_PRECONDITION=\"${GROWBOX_SD_CMD0_PRECONDITION:-0}\"
STAGE27C_PYTHON=\"${STAGE27C_PYTHON:-$ROOT/.venv/bin/python}\"
"""
if env_anchor not in text:
    raise SystemExit("stage27c script env anchor not found")
text = text.replace(env_anchor, """SD_CMD0_PRECONDITION=\"${GROWBOX_SD_CMD0_PRECONDITION:-0}\"
RF433_LOOPBACK_ENABLED=\"${GROWBOX_RF433_LOOPBACK_ENABLED:-0}\"
RF433_LOOPBACK_AUTO_SMOKE=\"${GROWBOX_RF433_LOOPBACK_AUTO_SMOKE:-0}\"
RF433_TX_GPIO=\"${GROWBOX_RF433_TX_GPIO:-8}\"
RF433_RX_GPIO=\"${GROWBOX_RF433_RX_GPIO:-14}\"
STAGE27C_PYTHON=\"${STAGE27C_PYTHON:-$ROOT/.venv/bin/python}\"
""", 1)
args_anchor = """  -D \"GROWBOX_SD_POWER_GPIO=42\"
)
"""
if args_anchor not in text:
    raise SystemExit("stage27c script args anchor not found")
text = text.replace(args_anchor, """  -D \"GROWBOX_SD_POWER_GPIO=42\"
  -D \"GROWBOX_RF433_LOOPBACK_ENABLED=$RF433_LOOPBACK_ENABLED\"
  -D \"GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=$RF433_LOOPBACK_AUTO_SMOKE\"
  -D \"GROWBOX_RF433_TX_GPIO=$RF433_TX_GPIO\"
  -D \"GROWBOX_RF433_RX_GPIO=$RF433_RX_GPIO\"
)
""", 1)
path.write_text(text, encoding="utf-8")

path = Path("src/climate/ClimateV6RealInputRuntime.cpp")
text = path.read_text(encoding="utf-8")
include_anchor = '#include "climate/native/Scd41InsideSource.h"\n'
if include_anchor not in text:
    raise SystemExit("runtime include anchor not found")
text = text.replace(include_anchor, include_anchor + '#include "climate/rf433/Rf433RmtLoopback.h"\n', 1)

macro_anchor = """#ifndef GROWBOX_SD_POWER_GPIO
#define GROWBOX_SD_POWER_GPIO -1
#endif
"""
if macro_anchor not in text:
    raise SystemExit("runtime macro anchor not found")
text = text.replace(macro_anchor, macro_anchor + """#ifndef GROWBOX_RF433_LOOPBACK_ENABLED
#define GROWBOX_RF433_LOOPBACK_ENABLED 0
#endif
#ifndef GROWBOX_RF433_LOOPBACK_AUTO_SMOKE
#define GROWBOX_RF433_LOOPBACK_AUTO_SMOKE 0
#endif
#ifndef GROWBOX_RF433_TX_GPIO
#define GROWBOX_RF433_TX_GPIO 8
#endif
#ifndef GROWBOX_RF433_RX_GPIO
#define GROWBOX_RF433_RX_GPIO 14
#endif
""", 1)

storage_anchor = """  storage::Stage27TelemetryLogger storage_logger(storage_config);
  const bool storage_enabled = storage_config.sd_enabled || storage_config.flash_fallback_enabled;
  const bool storage_logger_ready =
      storage_enabled && storage_logger.begin(GROWBOX_FIRMWARE_GIT_SHA);

  Stage27InsideSource inside(ble, scd41);
"""
if storage_anchor not in text:
    raise SystemExit("runtime storage anchor not found")
text = text.replace(storage_anchor, """  storage::Stage27TelemetryLogger storage_logger(storage_config);
  const bool storage_enabled = storage_config.sd_enabled || storage_config.flash_fallback_enabled;
  const bool storage_logger_ready =
      storage_enabled && storage_logger.begin(GROWBOX_FIRMWARE_GIT_SHA);

  rf433::Rf433RmtLoopback rf_loopback(
      rf433::Rf433RmtLoopback::Config{GROWBOX_RF433_TX_GPIO, GROWBOX_RF433_RX_GPIO});
  const bool rf_loopback_ready =
      GROWBOX_RF433_LOOPBACK_ENABLED != 0 && rf_loopback.begin();

  Stage27InsideSource inside(ble, scd41);
""", 1)

boot_anchor = """  ESP_LOGI(kTag,
           \"Stage27 real-input runtime: i2c=%d scd41=%d ds3231=%d ble=%d sd=%d \"
           \"flash_fallback=%d storage_logger=%d outputs=fake-locked\",
           i2c_ready, scd41_ready, rtc_ready, ble_ready, storage_config.sd_enabled,
           storage_config.flash_fallback_enabled, storage_logger_ready);
"""
if boot_anchor not in text:
    raise SystemExit("runtime boot anchor not found")
text = text.replace(boot_anchor, """  ESP_LOGI(kTag,
           \"Stage27 real-input runtime: i2c=%d scd41=%d ds3231=%d ble=%d sd=%d \"
           \"flash_fallback=%d storage_logger=%d rf433_loopback=%d rf433_tx_gpio=%d \"
           \"rf433_rx_gpio=%d outputs=fake-locked\",
           i2c_ready, scd41_ready, rtc_ready, ble_ready, storage_config.sd_enabled,
           storage_config.flash_fallback_enabled, storage_logger_ready, rf_loopback_ready,
           GROWBOX_RF433_TX_GPIO, GROWBOX_RF433_RX_GPIO);
""", 1)

loop_anchor = """  std::uint32_t diagnostic_tick = 0U;
  while (true) {
    const std::uint64_t now_ms = monotonicMilliseconds();
    ::growbox::climate::ClimateRuntimeDecision decision{};
"""
if loop_anchor not in text:
    raise SystemExit("runtime loop anchor not found")
text = text.replace(loop_anchor, """  std::uint32_t diagnostic_tick = 0U;
  bool rf_smoke_attempted = false;
  while (true) {
    const std::uint64_t now_ms = monotonicMilliseconds();
    if (rf_loopback_ready && GROWBOX_RF433_LOOPBACK_AUTO_SMOKE != 0 &&
        !rf_smoke_attempted && now_ms >= 3'000U) {
      rf_smoke_attempted = true;
      rf433::LoopbackEvidence evidence{};
      const rf433::FrameConfig smoke{{0xA55AU, 16U, 1U}, 3U, 0U};
      const bool passed = rf_loopback.transmitAndReceive(smoke, 1'500U, evidence);
      const auto& rf_diag = rf_loopback.diagnostics();
      ESP_LOGI(
          kTag,
          \"rf433_loopback_v=1 pass=%d tx_id=%llu requested_code=%lu requested_bits=%u \"
          \"requested_protocol=%u requested_repeat=%u requested_pulse_us=%u tx_queued=%d \"
          \"tx_started=%d tx_completed=%d tx_started_ms=%lu tx_completed_ms=%lu \"
          \"rx_captured=%d rx_start_ms=%lu rx_finish_ms=%lu decode_status=%u \"
          \"decoded_code=%lu decoded_bits=%u decoded_protocol=%u estimated_pulse_us=%u \"
          \"observed_repeats=%u classification=%u tx_queue_errors=%lu tx_wait_errors=%lu \"
          \"rx_arm_errors=%lu rx_timeouts=%lu rx_decode_failures=%lu rx_ambiguous=%lu \"
          \"rx_self_tx=%lu rx_interference=%lu outputs=fake-locked\",
          passed, static_cast<unsigned long long>(evidence.tx_id),
          static_cast<unsigned long>(smoke.key.code), smoke.key.bit_length,
          smoke.key.protocol, smoke.repeat, smoke.pulse_us, evidence.tx_queued,
          evidence.tx_started, evidence.tx_completed,
          static_cast<unsigned long>(evidence.tx_started_at_ms),
          static_cast<unsigned long>(evidence.tx_completed_at_ms), evidence.rx_captured,
          static_cast<unsigned long>(evidence.rx_started_at_ms),
          static_cast<unsigned long>(evidence.rx_finished_at_ms),
          static_cast<unsigned>(evidence.decoded.status),
          static_cast<unsigned long>(evidence.decoded.frame.code),
          evidence.decoded.frame.bit_length, evidence.decoded.frame.protocol,
          evidence.decoded.estimated_pulse_us, evidence.decoded.observed_repeats,
          static_cast<unsigned>(evidence.classification),
          static_cast<unsigned long>(rf_diag.tx_queue_errors),
          static_cast<unsigned long>(rf_diag.tx_wait_errors),
          static_cast<unsigned long>(rf_diag.rx_arm_errors),
          static_cast<unsigned long>(rf_diag.rx_timeouts),
          static_cast<unsigned long>(rf_diag.rx_decode_failures),
          static_cast<unsigned long>(rf_diag.rx_ambiguous),
          static_cast<unsigned long>(rf_diag.rx_self_tx),
          static_cast<unsigned long>(rf_diag.rx_interference));
    }

    ::growbox::climate::ClimateRuntimeDecision decision{};
""", 1)
path.write_text(text, encoding="utf-8")
