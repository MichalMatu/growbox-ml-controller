from pathlib import Path

console = Path("src/climate/runtime/Stage28ServiceConsole.cpp")
runtime = Path("src/climate/ClimateV6RealInputRuntime.cpp")

console_text = console.read_text()
old_include = '#include "climate/runtime/Stage28ServiceConsole.h"\n\n#include "climate/rf433/Rf433HardwareConfig.h"'
new_include = '#include "climate/runtime/Stage28ServiceConsole.h"\n\n#include "climate/runtime/Stage28ePlatformDiagnostics.h"\n#include "climate/rf433/Rf433HardwareConfig.h"'
if console_text.count(old_include) != 1:
    raise RuntimeError("unexpected Stage28ServiceConsole include shape")
console_text = console_text.replace(old_include, new_include)

old_status = '''void Stage28ServiceConsole::printStatus(std::uint64_t now_ms) noexcept {
  const std::uint32_t free_internal =
      static_cast<std::uint32_t>(heap_caps_get_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT));
  const std::uint32_t free_psram =
      static_cast<std::uint32_t>(heap_caps_get_free_size(MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
  const UBaseType_t stack_watermark = uxTaskGetStackHighWaterMark(nullptr);
  writeFormatted("status firmware_sha=%s uptime_ms=%llu outputs=%s rf_ready=%d "
                 "free_internal=%lu free_psram=%lu stack_high_water=%lu\\r\\n",
                 config_.firmware_sha != nullptr ? config_.firmware_sha : "unknown",
                 static_cast<unsigned long long>(now_ms), outputModeName(), rf_diagnostics_.ready(),
                 static_cast<unsigned long>(free_internal), static_cast<unsigned long>(free_psram),
                 static_cast<unsigned long>(stack_watermark));
}
'''
new_status = '''void Stage28ServiceConsole::printStatus(std::uint64_t now_ms) noexcept {
  const auto& boot = bootIdentity(config_.firmware_sha);
  const RuntimeMemoryMetrics memory = sampleRuntimeMemoryMetrics();
  const UBaseType_t stack_watermark_bytes = uxTaskGetStackHighWaterMark(nullptr);
  writeFormatted(
      "status firmware_sha=%s boot_id=%08lx reset_reason=%ld uptime_ms=%llu outputs=%s rf_ready=%d "
      "internal_total=%lu internal_free=%lu internal_min=%lu internal_largest=%lu "
      "psram_total=%lu psram_free=%lu psram_min=%lu psram_largest=%lu "
      "free_internal=%lu free_psram=%lu stack_high_water=%lu current_task_stack_hwm_bytes=%lu\\r\\n",
      boot.firmware_sha, static_cast<unsigned long>(boot.boot_id), static_cast<long>(boot.reset_reason),
      static_cast<unsigned long long>(now_ms), outputModeName(), rf_diagnostics_.ready(),
      static_cast<unsigned long>(memory.internal.total_bytes),
      static_cast<unsigned long>(memory.internal.free_bytes),
      static_cast<unsigned long>(memory.internal.minimum_free_bytes),
      static_cast<unsigned long>(memory.internal.largest_free_block_bytes),
      static_cast<unsigned long>(memory.psram.total_bytes),
      static_cast<unsigned long>(memory.psram.free_bytes),
      static_cast<unsigned long>(memory.psram.minimum_free_bytes),
      static_cast<unsigned long>(memory.psram.largest_free_block_bytes),
      static_cast<unsigned long>(memory.internal.free_bytes),
      static_cast<unsigned long>(memory.psram.free_bytes),
      static_cast<unsigned long>(stack_watermark_bytes),
      static_cast<unsigned long>(stack_watermark_bytes));
}
'''
if console_text.count(old_status) != 1:
    raise RuntimeError("unexpected Stage28ServiceConsole status shape")
console.write_text(console_text.replace(old_status, new_status))

runtime_text = runtime.read_text()
old_runtime_include = '#include "climate/runtime/Stage28ServiceConsole.h"\n#include "climate/storage/Stage27TelemetryLogger.h"'
new_runtime_include = '#include "climate/runtime/Stage28ServiceConsole.h"\n#include "climate/runtime/Stage28ePlatformDiagnostics.h"\n#include "climate/storage/Stage27TelemetryLogger.h"'
if runtime_text.count(old_runtime_include) != 1:
    raise RuntimeError("unexpected runtime include shape")
runtime_text = runtime_text.replace(old_runtime_include, new_runtime_include)

old_reset = '  const esp_reset_reason_t reset_reason = esp_reset_reason();\n'
new_reset = '''  const auto& boot_identity = runtime::bootIdentity(GROWBOX_FIRMWARE_GIT_SHA);
  const esp_reset_reason_t reset_reason =
      static_cast<esp_reset_reason_t>(boot_identity.reset_reason);
'''
if runtime_text.count(old_reset) != 1:
    raise RuntimeError("unexpected reset-reason shape")
runtime_text = runtime_text.replace(old_reset, new_reset)

old_boot_log = '''  ESP_LOGI(kTag, "Stage27 soak boot: firmware_sha=%s reset_reason=%d", GROWBOX_FIRMWARE_GIT_SHA,
           static_cast<int>(reset_reason));
'''
new_boot_log = '''  ESP_LOGI(kTag,
           "Stage27 soak boot: firmware_sha=%s boot_id=%08lx reset_reason=%d started_us=%llu",
           boot_identity.firmware_sha, static_cast<unsigned long>(boot_identity.boot_id),
           static_cast<int>(reset_reason),
           static_cast<unsigned long long>(boot_identity.started_monotonic_us));
'''
if runtime_text.count(old_boot_log) != 1:
    raise RuntimeError("unexpected boot-log shape")
runtime.write_text(runtime_text.replace(old_boot_log, new_boot_log))
