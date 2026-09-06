from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one match in {path}, got {count}")
    p.write_text(text.replace(old, new, 1))

# Fixed-size timing bundle; no dynamic allocation in the runtime hot path.
replace_once(
    "src/climate/runtime/Stage28eDiagnosticsCore.h",
    "struct BootIdentity {\n",
    "struct RuntimeTimingMetrics {\n"
    "  TimingAccumulator service_console{};\n"
    "  TimingAccumulator rf_tick{};\n"
    "  TimingAccumulator control_cycle{};\n"
    "  TimingAccumulator telemetry{};\n"
    "  TimingAccumulator loop_active{};\n"
    "};\n\n"
    "struct BootIdentity {\n",
)

# Service console receives a read-only view of timing accumulators.
replace_once(
    "src/climate/runtime/Stage28ServiceConsole.h",
    "#include \"climate/runtime/Stage28RfDiagnostics.h\"\n",
    "#include \"climate/runtime/Stage28RfDiagnostics.h\"\n"
    "#include \"climate/runtime/Stage28eDiagnosticsCore.h\"\n",
)
replace_once(
    "src/climate/runtime/Stage28ServiceConsole.h",
    "    const storage::Stage27TelemetryLogger* storage_logger{nullptr};\n",
    "    const storage::Stage27TelemetryLogger* storage_logger{nullptr};\n"
    "    const RuntimeTimingMetrics* timing_metrics{nullptr};\n",
)

# Status prints bounded fixed-format timing evidence only on demand.
needle = "  for (UBaseType_t index = 0U; index < task_captured; ++index) {\n"
insert = '''  if (config_.timing_metrics != nullptr) {
    const RuntimeTimingMetrics& timing = *config_.timing_metrics;
    writeFormatted(
        "timing loop_samples=%llu loop_max_us=%llu loop_overruns=%llu loop_budget_us=%llu "
        "control_samples=%llu control_max_us=%llu rf_samples=%llu rf_max_us=%llu "
        "telemetry_samples=%llu telemetry_max_us=%llu console_samples=%llu console_max_us=%llu\\r\\n",
        static_cast<unsigned long long>(timing.loop_active.sample_count),
        static_cast<unsigned long long>(timing.loop_active.max_us),
        static_cast<unsigned long long>(timing.loop_active.overrun_count),
        static_cast<unsigned long long>(timing.loop_active.budget_us),
        static_cast<unsigned long long>(timing.control_cycle.sample_count),
        static_cast<unsigned long long>(timing.control_cycle.max_us),
        static_cast<unsigned long long>(timing.rf_tick.sample_count),
        static_cast<unsigned long long>(timing.rf_tick.max_us),
        static_cast<unsigned long long>(timing.telemetry.sample_count),
        static_cast<unsigned long long>(timing.telemetry.max_us),
        static_cast<unsigned long long>(timing.service_console.sample_count),
        static_cast<unsigned long long>(timing.service_console.max_us));
  }

'''
replace_once("src/climate/runtime/Stage28ServiceConsole.cpp", needle, insert + needle)

# Runtime owns timing accumulators for the whole boot and passes them to status.
replace_once(
    "src/climate/ClimateV6RealInputRuntime.cpp",
    "  runtime::Stage28ServiceConsole service_console(\n"
    "      {GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED != 0, GROWBOX_FIRMWARE_GIT_SHA,\n"
    "       &real_output_ready, &storage_logger},\n",
    "  runtime::RuntimeTimingMetrics runtime_timing{};\n"
    "  runtime_timing.loop_active.budget_us = kTickIntervalMs * 1000U;\n"
    "  runtime::Stage28ServiceConsole service_console(\n"
    "      {GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED != 0, GROWBOX_FIRMWARE_GIT_SHA,\n"
    "       &real_output_ready, &storage_logger, &runtime_timing},\n",
)

replace_once(
    "src/climate/ClimateV6RealInputRuntime.cpp",
    "  while (true) {\n"
    "    const std::uint64_t now_ms = monotonicMilliseconds();\n"
    "    service_console.poll(now_ms);\n"
    "    rf_diagnostics.tick(now_ms);\n",
    "  while (true) {\n"
    "    const std::uint64_t loop_started_us = static_cast<std::uint64_t>(esp_timer_get_time());\n"
    "    const std::uint64_t now_ms = loop_started_us / 1000U;\n"
    "    const std::uint64_t console_started_us = static_cast<std::uint64_t>(esp_timer_get_time());\n"
    "    service_console.poll(now_ms);\n"
    "    runtime_timing.service_console.observe(\n"
    "        static_cast<std::uint64_t>(esp_timer_get_time()) - console_started_us);\n"
    "    const std::uint64_t rf_started_us = static_cast<std::uint64_t>(esp_timer_get_time());\n"
    "    rf_diagnostics.tick(now_ms);\n"
    "    runtime_timing.rf_tick.observe(static_cast<std::uint64_t>(esp_timer_get_time()) - rf_started_us);\n",
)

replace_once(
    "src/climate/ClimateV6RealInputRuntime.cpp",
    "    stage28d::LampSafetyDecision lamp_decision{};\n\n"
    "    if (GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED != 0 && real_output_ready &&\n",
    "    stage28d::LampSafetyDecision lamp_decision{};\n\n"
    "    const std::uint64_t control_started_us = static_cast<std::uint64_t>(esp_timer_get_time());\n"
    "    if (GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED != 0 && real_output_ready &&\n",
)

replace_once(
    "src/climate/ClimateV6RealInputRuntime.cpp",
    "    }\n\n"
    "    if ((diagnostic_tick++ % kTelemetryEveryTicks) == 0U) {\n",
    "    }\n"
    "    runtime_timing.control_cycle.observe(\n"
    "        static_cast<std::uint64_t>(esp_timer_get_time()) - control_started_us);\n\n"
    "    if ((diagnostic_tick++ % kTelemetryEveryTicks) == 0U) {\n"
    "      const std::uint64_t telemetry_started_us =\n"
    "          static_cast<std::uint64_t>(esp_timer_get_time());\n",
)

replace_once(
    "src/climate/ClimateV6RealInputRuntime.cpp",
    "               static_cast<unsigned long>(physical_endpoint.transmitErrorCount()));\n"
    "    }\n\n"
    "    vTaskDelay(pdMS_TO_TICKS(kTickIntervalMs));\n",
    "               static_cast<unsigned long>(physical_endpoint.transmitErrorCount()));\n"
    "      runtime_timing.telemetry.observe(\n"
    "          static_cast<std::uint64_t>(esp_timer_get_time()) - telemetry_started_us);\n"
    "    }\n\n"
    "    runtime_timing.loop_active.observe(\n"
    "        static_cast<std::uint64_t>(esp_timer_get_time()) - loop_started_us);\n"
    "    vTaskDelay(pdMS_TO_TICKS(kTickIntervalMs));\n",
)
