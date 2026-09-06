from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    if text.count(old) != 1:
        raise SystemExit(f"expected one match in {path}, got {text.count(old)}")
    p.write_text(text.replace(old, new, 1))

# Enable FreeRTOS task snapshots only for the Stage27C/CrowPanel diagnostic profile.
p = Path("config/idf/sdkconfig.defaults.stage27c")
text = p.read_text()
needle = "CONFIG_WL_SECTOR_MODE_SAFE=y\n"
if text.count(needle) != 1:
    raise SystemExit("unexpected Stage27C sdkconfig overlay")
p.write_text(text.replace(
    needle,
    needle + "\n# Stage28E Phase A task diagnostics. uxTaskGetSystemState() is gated by this option.\n"
             "CONFIG_FREERTOS_USE_TRACE_FACILITY=y\n",
    1,
))

# Expose the storage task's configured stack without duplicating the value in diagnostics.
replace_once(
    "src/climate/storage/Stage27TelemetryLogger.h",
    "  Stage27StorageStatus status() const noexcept;\n\nprivate:\n",
    "  Stage27StorageStatus status() const noexcept;\n\n"
    "  static constexpr std::uint32_t taskStackBytes() noexcept { return 7168U; }\n\nprivate:\n",
)
replace_once(
    "src/climate/storage/Stage27TelemetryLogger.cpp",
    "constexpr std::uint32_t kTaskStackBytes = 7168U;\n",
    "",
)
replace_once(
    "src/climate/storage/Stage27TelemetryLogger.cpp",
    "  if (xTaskCreate(&Stage27TelemetryLogger::taskEntry, \"stage27_store\", kTaskStackBytes, this,\n",
    "  if (xTaskCreate(&Stage27TelemetryLogger::taskEntry, \"stage27_store\", taskStackBytes(), this,\n",
)

# Add task-name helpers next to the existing service-console local helpers.
replace_once(
    "src/climate/runtime/Stage28ServiceConsole.cpp",
    "const KnownRfDevice* findKnownDevice(ServiceConsoleRfDevice id) noexcept {\n"
    "  for (const KnownRfDevice& device : kKnownRfDevices) {\n"
    "    if (device.id == id) {\n"
    "      return &device;\n"
    "    }\n"
    "  }\n"
    "  return nullptr;\n"
    "}\n",
    "const KnownRfDevice* findKnownDevice(ServiceConsoleRfDevice id) noexcept {\n"
    "  for (const KnownRfDevice& device : kKnownRfDevices) {\n"
    "    if (device.id == id) {\n"
    "      return &device;\n"
    "    }\n"
    "  }\n"
    "  return nullptr;\n"
    "}\n\n"
    "std::uint32_t knownConfiguredTaskStackBytes(const char* name) noexcept {\n"
    "  if (name == nullptr) {\n"
    "    return 0U;\n"
    "  }\n"
    "  if (std::strcmp(name, \"main\") == 0) {\n"
    "    return static_cast<std::uint32_t>(CONFIG_ESP_MAIN_TASK_STACK_SIZE);\n"
    "  }\n"
    "  if (std::strcmp(name, \"stage27_store\") == 0) {\n"
    "    return storage::Stage27TelemetryLogger::taskStackBytes();\n"
    "  }\n"
    "#if defined(CONFIG_ESP_TIMER_TASK_STACK_SIZE)\n"
    "  if (std::strcmp(name, \"esp_timer\") == 0) {\n"
    "    return static_cast<std::uint32_t>(CONFIG_ESP_TIMER_TASK_STACK_SIZE);\n"
    "  }\n"
    "#endif\n"
    "#if defined(CONFIG_ESP_SYSTEM_EVENT_TASK_STACK_SIZE)\n"
    "  if (std::strcmp(name, \"sys_evt\") == 0) {\n"
    "    return static_cast<std::uint32_t>(CONFIG_ESP_SYSTEM_EVENT_TASK_STACK_SIZE);\n"
    "  }\n"
    "#endif\n"
    "#if defined(CONFIG_BT_NIMBLE_HOST_TASK_STACK_SIZE)\n"
    "  if (std::strcmp(name, \"nimble_host\") == 0) {\n"
    "    return static_cast<std::uint32_t>(CONFIG_BT_NIMBLE_HOST_TASK_STACK_SIZE);\n"
    "  }\n"
    "#endif\n"
    "  return 0U;\n"
    "}\n\n"
    "const char* stackMarginSeverityName(StackMarginSeverity severity) noexcept {\n"
    "  switch (severity) {\n"
    "  case StackMarginSeverity::Normal:\n"
    "    return \"normal\";\n"
    "  case StackMarginSeverity::Warning:\n"
    "    return \"warning\";\n"
    "  case StackMarginSeverity::Critical:\n"
    "    return \"critical\";\n"
    "  case StackMarginSeverity::Unknown:\n"
    "    break;\n"
    "  }\n"
    "  return \"unknown\";\n"
    "}\n",
)

old_status = '''void Stage28ServiceConsole::printStatus(std::uint64_t now_ms) noexcept {
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
new_status = '''void Stage28ServiceConsole::printStatus(std::uint64_t now_ms) noexcept {
  const auto& boot = bootIdentity(config_.firmware_sha);
  const RuntimeMemoryMetrics memory = sampleRuntimeMemoryMetrics();
  const UBaseType_t stack_watermark_bytes = uxTaskGetStackHighWaterMark(nullptr);

  UBaseType_t task_total = 0U;
  UBaseType_t task_captured = 0U;
  TaskStatus_t* task_status = nullptr;
#if CONFIG_FREERTOS_USE_TRACE_FACILITY
  task_total = uxTaskGetNumberOfTasks();
  const UBaseType_t task_capacity = task_total + 2U;
  const std::size_t task_bytes = static_cast<std::size_t>(task_capacity) * sizeof(TaskStatus_t);
  task_status = static_cast<TaskStatus_t*>(
      heap_caps_malloc(task_bytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
  if (task_status != nullptr) {
    task_captured = uxTaskGetSystemState(task_status, task_capacity, nullptr);
  }
#endif

  writeFormatted(
      "status firmware_sha=%s boot_id=%08lx reset_reason=%ld uptime_ms=%llu outputs=%s rf_ready=%d "
      "internal_total=%lu internal_free=%lu internal_min=%lu internal_largest=%lu "
      "psram_total=%lu psram_free=%lu psram_min=%lu psram_largest=%lu "
      "free_internal=%lu free_psram=%lu stack_high_water=%lu current_task_stack_hwm_bytes=%lu "
      "task_total=%lu task_captured=%lu task_snapshot_psram=%d hwm_semantics=min_free_since_create\\r\\n",
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
      static_cast<unsigned long>(stack_watermark_bytes), static_cast<unsigned long>(task_total),
      static_cast<unsigned long>(task_captured), task_status != nullptr);

  for (UBaseType_t index = 0U; index < task_captured; ++index) {
    const TaskStatus_t& task = task_status[index];
    const std::uint32_t configured_stack_bytes = knownConfiguredTaskStackBytes(task.pcTaskName);
    const std::uint32_t high_water_bytes = static_cast<std::uint32_t>(task.usStackHighWaterMark);
    const StackMarginSeverity severity =
        classifyStackMargin(high_water_bytes, configured_stack_bytes);
    writeFormatted(
        "task name=%s task_no=%lu core=%ld priority=%lu configured_stack_bytes=%lu "
        "hwm_bytes=%lu worst_hwm_bytes=%lu severity=%s\\r\\n",
        task.pcTaskName != nullptr ? task.pcTaskName : "unknown",
        static_cast<unsigned long>(task.xTaskNumber), static_cast<long>(task.xCoreID),
        static_cast<unsigned long>(task.uxCurrentPriority),
        static_cast<unsigned long>(configured_stack_bytes),
        static_cast<unsigned long>(high_water_bytes), static_cast<unsigned long>(high_water_bytes),
        stackMarginSeverityName(severity));
  }
  if (task_status != nullptr) {
    heap_caps_free(task_status);
  }
}
'''
replace_once("src/climate/runtime/Stage28ServiceConsole.cpp", old_status, new_status)
