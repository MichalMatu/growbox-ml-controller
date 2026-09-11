#ifndef GROWBOX_APP_CLIMATE_V6_FAKE
#define GROWBOX_APP_CLIMATE_V6_FAKE 0
#endif
#ifndef GROWBOX_APP_CLIMATE_V6_REAL_INPUTS
#define GROWBOX_APP_CLIMATE_V6_REAL_INPUTS 0
#endif
#ifndef GROWBOX_FIRMWARE_GIT_SHA
#define GROWBOX_FIRMWARE_GIT_SHA "unknown"
#endif

#if GROWBOX_APP_CLIMATE_V6_FAKE
#include "climate/ClimateV6FakeRuntime.h"
#elif GROWBOX_APP_CLIMATE_V6_REAL_INPUTS
#include "climate/ClimateV6RealInputRuntime.h"
#else
#include "legacy/LegacyRuntime.h"
#endif
#include "climate/runtime/Stage28eBreadcrumbs.h"
#include "climate/runtime/Stage28ePlatformDiagnostics.h"

#include <esp_core_dump.h>
#include <esp_err.h>

#include <cstddef>
#include <cstdint>
#include <cstdio>

namespace {

std::uint32_t g_runtime_entry_count = 0U;

const char* runtimeModeName() noexcept {
#if GROWBOX_APP_CLIMATE_V6_FAKE
  return "climate-v6-fake";
#elif GROWBOX_APP_CLIMATE_V6_REAL_INPUTS
  return "climate-v6-real-inputs";
#else
  return "legacy";
#endif
}

void emitCoreDumpBootDiagnostics() noexcept {
  std::size_t dump_address = 0U;
  std::size_t dump_size = 0U;
  const esp_err_t get_result = esp_core_dump_image_get(&dump_address, &dump_size);
  const bool present = get_result == ESP_OK && dump_size > 0U;
  esp_err_t check_result = get_result;
#if CONFIG_ESP_COREDUMP_ENABLE_TO_FLASH
  if (present) {
    check_result = esp_core_dump_image_check();
  }
#endif
  std::printf("stage28e_coredump present=%d valid=%d size=%lu get_err=%ld check_err=%ld\n", present,
              present && check_result == ESP_OK, static_cast<unsigned long>(dump_size),
              static_cast<long>(get_result), static_cast<long>(check_result));
}

void emitBreadcrumbBootDiagnostics() noexcept {
  using namespace growbox::app::climate_io::runtime;
  const Stage28eBreadcrumbState raw_previous = readStage28eBreadcrumb();
  const bool previous_valid = stage28eBreadcrumbValid(raw_previous);
  const Stage28eBreadcrumbState previous =
      previous_valid ? raw_previous : Stage28eBreadcrumbState{};
  std::printf(
      "stage28e_breadcrumb previous_valid=%d write_seq=%lu boot_seq=%lu boot_id=%08lx "
      "reset_reason=%ld last_log_seq=%lu last_log_uptime_ms=%llu last_log_module=%lu "
      "last_log_level=%lu fault_code=%lu fault_seq=%lu fault_uptime_ms=%llu "
      "arbiter_instance=%lu arbiter_constructions=%lu arbiter_transitions=%lu "
      "arbiter_dwell_holds=%lu arbiter_safety_overrides=%lu arbiter_continuity_faults=%lu\n",
      previous_valid, static_cast<unsigned long>(previous.write_sequence),
      static_cast<unsigned long>(previous.boot_sequence),
      static_cast<unsigned long>(previous.boot_id), static_cast<long>(previous.reset_reason),
      static_cast<unsigned long>(previous.last_log_sequence),
      static_cast<unsigned long long>(previous.last_log_uptime_ms),
      static_cast<unsigned long>(previous.last_log_module),
      static_cast<unsigned long>(previous.last_log_level),
      static_cast<unsigned long>(previous.last_fault_code),
      static_cast<unsigned long>(previous.last_fault_sequence),
      static_cast<unsigned long long>(previous.last_fault_uptime_ms),
      static_cast<unsigned long>(previous.arbiter_instance_id),
      static_cast<unsigned long>(previous.arbiter_construction_count),
      static_cast<unsigned long>(previous.arbiter_transition_count),
      static_cast<unsigned long>(previous.arbiter_dwell_hold_count),
      static_cast<unsigned long>(previous.arbiter_safety_override_count),
      static_cast<unsigned long>(previous.arbiter_continuity_fault_count));

  const BootIdentity& boot = bootIdentity(GROWBOX_FIRMWARE_GIT_SHA);
  beginStage28eBreadcrumb(boot.boot_id, boot.reset_reason);
}

void emitRuntimeLifecycleDiagnostics() noexcept {
  ++g_runtime_entry_count;
  std::printf("stage28e_runtime_lifecycle entry_count=%lu mode=%s\n",
              static_cast<unsigned long>(g_runtime_entry_count), runtimeModeName());
}

} // namespace

extern "C" void app_main() {
  emitCoreDumpBootDiagnostics();
  emitBreadcrumbBootDiagnostics();
  emitRuntimeLifecycleDiagnostics();
#if GROWBOX_APP_CLIMATE_V6_FAKE
  growbox::app::climate_io::runClimateV6FakeRuntime();
#elif GROWBOX_APP_CLIMATE_V6_REAL_INPUTS
  growbox::app::climate_io::runClimateV6RealInputRuntime();
#else
  growbox::app::legacy::runLegacyRuntime();
#endif
}
