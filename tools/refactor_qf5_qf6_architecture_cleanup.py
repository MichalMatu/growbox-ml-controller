#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if text.count(old) != 1:
        raise SystemExit(f"anchor mismatch in {path.relative_to(ROOT)}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1))


# Make console command routing an explicit, host-testable boundary.
router_h = ROOT / "src/climate/runtime/Stage28ServiceConsoleRouter.h"
router_h.write_text('''#pragma once

#include "climate/runtime/Stage28ServiceConsoleCommand.h"

#include <cstdint>

namespace growbox::app::climate_io::runtime {

enum class ServiceConsoleCommandDomain : std::uint8_t {
  None = 0U,
  Builtin,
  Output,
  Storage,
  System,
  Invalid,
};

ServiceConsoleCommandDomain serviceConsoleCommandDomain(ServiceConsoleCommandKind kind) noexcept;

} // namespace growbox::app::climate_io::runtime
''')

router_cpp = ROOT / "src/climate/runtime/Stage28ServiceConsoleRouter.cpp"
router_cpp.write_text('''#include "climate/runtime/Stage28ServiceConsoleRouter.h"

namespace growbox::app::climate_io::runtime {

ServiceConsoleCommandDomain serviceConsoleCommandDomain(ServiceConsoleCommandKind kind) noexcept {
  switch (kind) {
  case ServiceConsoleCommandKind::None:
    return ServiceConsoleCommandDomain::None;
  case ServiceConsoleCommandKind::Help:
    return ServiceConsoleCommandDomain::Builtin;
  case ServiceConsoleCommandKind::ManualOutput:
  case ServiceConsoleCommandKind::AutomationStatus:
  case ServiceConsoleCommandKind::AutomationEnable:
  case ServiceConsoleCommandKind::AutomationDisable:
  case ServiceConsoleCommandKind::MaintenanceStatus:
  case ServiceConsoleCommandKind::MaintenanceEnter:
  case ServiceConsoleCommandKind::MaintenanceExit:
  case ServiceConsoleCommandKind::MaintenanceRawOutput:
    return ServiceConsoleCommandDomain::Output;
  case ServiceConsoleCommandKind::SdLogStatus:
  case ServiceConsoleCommandKind::SdLogList:
  case ServiceConsoleCommandKind::SdLogRead:
  case ServiceConsoleCommandKind::SdLogSelfTest:
    return ServiceConsoleCommandDomain::Storage;
  case ServiceConsoleCommandKind::Status:
  case ServiceConsoleCommandKind::Sensors:
  case ServiceConsoleCommandKind::RfList:
  case ServiceConsoleCommandKind::RfReceive:
  case ServiceConsoleCommandKind::RtcSetUnix:
    return ServiceConsoleCommandDomain::System;
  case ServiceConsoleCommandKind::Invalid:
    return ServiceConsoleCommandDomain::Invalid;
  }
  return ServiceConsoleCommandDomain::Invalid;
}

} // namespace growbox::app::climate_io::runtime
''')

console = ROOT / "src/climate/runtime/Stage28ServiceConsole.cpp"
replace_once(
    console,
    '#include "climate/runtime/Stage28ServiceConsole.h"\n',
    '#include "climate/runtime/Stage28ServiceConsole.h"\n\n#include "climate/runtime/Stage28ServiceConsoleRouter.h"\n',
)
old_process = '''void Stage28ServiceConsole::processLine(std::uint64_t now_ms) noexcept {
  const ServiceConsoleCommand command = parseServiceConsoleCommand(line_.data());
  if (command.kind == ServiceConsoleCommandKind::None) {
    return;
  }
  if (command.kind == ServiceConsoleCommandKind::Help) {
    printHelp();
    return;
  }
  if (output_commands_.handle(command, now_ms) || storage_commands_.handle(command) ||
      system_commands_.handle(command, now_ms)) {
    return;
  }
  writeText("error: unknown/invalid command; type 'help'\\r\\n");
}
'''
new_process = '''void Stage28ServiceConsole::processLine(std::uint64_t now_ms) noexcept {
  const ServiceConsoleCommand command = parseServiceConsoleCommand(line_.data());
  const ServiceConsoleCommandDomain domain = serviceConsoleCommandDomain(command.kind);
  switch (domain) {
  case ServiceConsoleCommandDomain::None:
    return;
  case ServiceConsoleCommandDomain::Builtin:
    if (command.kind == ServiceConsoleCommandKind::Help) {
      printHelp();
      return;
    }
    break;
  case ServiceConsoleCommandDomain::Output:
    if (output_commands_.handle(command, now_ms)) {
      return;
    }
    break;
  case ServiceConsoleCommandDomain::Storage:
    if (storage_commands_.handle(command)) {
      return;
    }
    break;
  case ServiceConsoleCommandDomain::System:
    if (system_commands_.handle(command, now_ms)) {
      return;
    }
    break;
  case ServiceConsoleCommandDomain::Invalid:
    break;
  }
  writeText("error: unknown/invalid command; type 'help'\\r\\n");
}
'''
replace_once(console, old_process, new_process)

src_cmake = ROOT / "src/CMakeLists.txt"
replace_once(
    src_cmake,
    '      "climate/runtime/Stage28ServiceConsoleCommand.cpp"\n',
    '      "climate/runtime/Stage28ServiceConsoleCommand.cpp"\n      "climate/runtime/Stage28ServiceConsoleRouter.cpp"\n',
)

host_cmake = ROOT / "test/host/CMakeLists.txt"
replace_once(
    host_cmake,
    '  "${PROJECT_ROOT}/src/climate/runtime/Stage28ServiceConsoleCommand.cpp"\n)\n',
    '  "${PROJECT_ROOT}/src/climate/runtime/Stage28ServiceConsoleCommand.cpp"\n  "${PROJECT_ROOT}/src/climate/runtime/Stage28ServiceConsoleRouter.cpp"\n)\n',
)

console_test = ROOT / "test/test_stage28_service_console/test_main.cpp"
replace_once(
    console_test,
    '#include "climate/runtime/Stage28ServiceConsoleCommand.h"\n',
    '#include "climate/runtime/Stage28ServiceConsoleCommand.h"\n#include "climate/runtime/Stage28ServiceConsoleRouter.h"\n',
)
router_test = '''void testCommandDomains() {
  const auto expect = [](ServiceConsoleCommandKind kind, ServiceConsoleCommandDomain domain) {
    assert(serviceConsoleCommandDomain(kind) == domain);
  };
  expect(ServiceConsoleCommandKind::None, ServiceConsoleCommandDomain::None);
  expect(ServiceConsoleCommandKind::Help, ServiceConsoleCommandDomain::Builtin);
  expect(ServiceConsoleCommandKind::Status, ServiceConsoleCommandDomain::System);
  expect(ServiceConsoleCommandKind::Sensors, ServiceConsoleCommandDomain::System);
  expect(ServiceConsoleCommandKind::RfList, ServiceConsoleCommandDomain::System);
  expect(ServiceConsoleCommandKind::RfReceive, ServiceConsoleCommandDomain::System);
  expect(ServiceConsoleCommandKind::RtcSetUnix, ServiceConsoleCommandDomain::System);
  expect(ServiceConsoleCommandKind::ManualOutput, ServiceConsoleCommandDomain::Output);
  expect(ServiceConsoleCommandKind::AutomationStatus, ServiceConsoleCommandDomain::Output);
  expect(ServiceConsoleCommandKind::AutomationEnable, ServiceConsoleCommandDomain::Output);
  expect(ServiceConsoleCommandKind::AutomationDisable, ServiceConsoleCommandDomain::Output);
  expect(ServiceConsoleCommandKind::MaintenanceStatus, ServiceConsoleCommandDomain::Output);
  expect(ServiceConsoleCommandKind::MaintenanceEnter, ServiceConsoleCommandDomain::Output);
  expect(ServiceConsoleCommandKind::MaintenanceExit, ServiceConsoleCommandDomain::Output);
  expect(ServiceConsoleCommandKind::MaintenanceRawOutput, ServiceConsoleCommandDomain::Output);
  expect(ServiceConsoleCommandKind::SdLogStatus, ServiceConsoleCommandDomain::Storage);
  expect(ServiceConsoleCommandKind::SdLogList, ServiceConsoleCommandDomain::Storage);
  expect(ServiceConsoleCommandKind::SdLogRead, ServiceConsoleCommandDomain::Storage);
  expect(ServiceConsoleCommandKind::SdLogSelfTest, ServiceConsoleCommandDomain::Storage);
  expect(ServiceConsoleCommandKind::Invalid, ServiceConsoleCommandDomain::Invalid);
  expect(static_cast<ServiceConsoleCommandKind>(255U), ServiceConsoleCommandDomain::Invalid);
}
'''
replace_once(console_test, '} // namespace\nint main() {\n', router_test + '} // namespace\nint main() {\n')
replace_once(
    console_test,
    '  testInvalidCommandsFailClosed();\n  return 0;\n',
    '  testInvalidCommandsFailClosed();\n  testCommandDomains();\n  return 0;\n',
)

# Extend the generated typed configuration with the board-profile identity.
build_config = ROOT / "src/climate/runtime/RuntimeBuildConfig.h.in"
replace_once(
    build_config,
    'namespace growbox::app::climate_io::runtime_config {\n\n',
    'namespace growbox::app::climate_io::runtime_config {\n\ninline constexpr char kBoardProfile[] = "@GROWBOX_BOARD_PROFILE@";\n',
)

# Remove production fallback defaults and consume the generated typed values where possible.
main = ROOT / "src/main.cpp"
replace_once(
    main,
    '''#ifndef GROWBOX_APP_CLIMATE_V6_FAKE
#define GROWBOX_APP_CLIMATE_V6_FAKE 0
#endif
#ifndef GROWBOX_APP_CLIMATE_V6_REAL_INPUTS
#define GROWBOX_APP_CLIMATE_V6_REAL_INPUTS 0
#endif
#ifndef GROWBOX_FIRMWARE_GIT_SHA
#define GROWBOX_FIRMWARE_GIT_SHA "unknown"
#endif

''',
    '',
)
replace_once(
    main,
    '#include "climate/runtime/Stage28ePlatformDiagnostics.h"\n',
    '#include "climate/runtime/Stage28ePlatformDiagnostics.h"\n#include "climate/runtime/RuntimeBuildConfig.h"\n',
)
main_text = main.read_text()
if main_text.count('bootIdentity(GROWBOX_FIRMWARE_GIT_SHA)') != 1:
    raise SystemExit('main firmware SHA anchor mismatch')
main.write_text(main_text.replace(
    'bootIdentity(GROWBOX_FIRMWARE_GIT_SHA)',
    'bootIdentity(::growbox::app::climate_io::runtime_config::kFirmwareGitSha)',
    1,
))

legacy = ROOT / "src/legacy/LegacyRuntime.cpp"
replace_once(
    legacy,
    '#include "legacy/LegacyRuntime.h"\n',
    '#include "legacy/LegacyRuntime.h"\n\n#include "climate/runtime/RuntimeBuildConfig.h"\n',
)
replace_once(
    legacy,
    '''#ifndef GROWBOX_BOARD_PROFILE
#define GROWBOX_BOARD_PROFILE "esp32s3-devkitc1-n16r8"
#endif

''',
    '',
)
legacy_text = legacy.read_text()
if legacy_text.count('GROWBOX_BOARD_PROFILE') != 1:
    raise SystemExit('legacy board profile anchor mismatch')
legacy.write_text(legacy_text.replace(
    'GROWBOX_BOARD_PROFILE',
    '::growbox::app::climate_io::runtime_config::kBoardProfile',
    1,
))

diagnostics = ROOT / "src/demo/protocol/DiagnosticsWireCodec.cpp"
replace_once(
    diagnostics,
    '#include "DiagnosticsWireCodec.h"\n',
    '#include "DiagnosticsWireCodec.h"\n\n#include "climate/runtime/RuntimeBuildConfig.h"\n',
)
replace_once(
    diagnostics,
    '''#ifndef GROWBOX_BOARD_PROFILE
#define GROWBOX_BOARD_PROFILE "esp32s3-devkitc1-n16r8"
#endif

''',
    '',
)
diag_text = diagnostics.read_text()
if diag_text.count('GROWBOX_BOARD_PROFILE') != 1:
    raise SystemExit('diagnostics board profile anchor mismatch')
diagnostics.write_text(diag_text.replace(
    'GROWBOX_BOARD_PROFILE',
    '::growbox::app::climate_io::runtime_config::kBoardProfile',
    1,
))

telemetry = ROOT / "src/climate/runtime/Stage27TelemetryReporter.cpp"
replace_once(
    telemetry,
    '#include "climate/runtime/Stage27TelemetryReporter.h"\n',
    '#include "climate/runtime/Stage27TelemetryReporter.h"\n\n#include "climate/runtime/RuntimeBuildConfig.h"\n',
)
replace_once(
    telemetry,
    '''#ifndef GROWBOX_FIRMWARE_GIT_SHA
#define GROWBOX_FIRMWARE_GIT_SHA "unknown"
#endif

''',
    '',
)
telemetry_text = telemetry.read_text()
if telemetry_text.count('GROWBOX_FIRMWARE_GIT_SHA') != 1:
    raise SystemExit('telemetry firmware SHA anchor mismatch')
telemetry.write_text(telemetry_text.replace(
    'GROWBOX_FIRMWARE_GIT_SHA',
    '::growbox::app::climate_io::runtime_config::kFirmwareGitSha',
    1,
))

stage28e_log_h = ROOT / "src/climate/runtime/Stage28eLog.h"
replace_once(
    stage28e_log_h,
    '''#ifndef GROWBOX_STAGE28E_LOG_COMPILE_LEVEL
#define GROWBOX_STAGE28E_LOG_COMPILE_LEVEL 2
#endif

''',
    '',
)

stage28e_log_cpp = ROOT / "src/climate/runtime/Stage28eLog.cpp"
replace_once(
    stage28e_log_cpp,
    '''#ifndef GROWBOX_STAGE28E_BREADCRUMB_RESTART_SELFTEST
#define GROWBOX_STAGE28E_BREADCRUMB_RESTART_SELFTEST 0
#endif

''',
    '',
)

# Generic IDF gate selects overrides only; canonical CMake owns the defaults.
idf_gate = ROOT / "scripts/idf_gate_build.sh"
idf_gate.write_text('''#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

# shellcheck disable=SC1091
source "${ROOT}/scripts/source_idf.sh"

BUILD_DIR="${IDF_GATE_BUILD_DIR:-build/idf-gate}"
SDKCONFIG_DEFAULTS="${IDF_GATE_SDKCONFIG:-config/idf/sdkconfig.defaults}"
SDKCONFIG_PATH="${IDF_GATE_SDKCONFIG_PATH:-${BUILD_DIR}/sdkconfig}"
PROFILE="${IDF_GATE_PROFILE:-}"
APP_MODE="${IDF_GATE_APP_MODE:-}"

mkdir -p "${BUILD_DIR}"

CMAKE_ARGS=(
  -D "SDKCONFIG=${SDKCONFIG_PATH}"
  -D "SDKCONFIG_DEFAULTS=${SDKCONFIG_DEFAULTS}"
)
if [[ -n "${PROFILE}" ]]; then
  CMAKE_ARGS+=( -D "GROWBOX_BOARD_PROFILE=${PROFILE}" )
fi
if [[ -n "${APP_MODE}" ]]; then
  CMAKE_ARGS+=( -D "GROWBOX_APP_MODE=${APP_MODE}" )
fi

echo "==> idf.py build (${PROFILE:-canonical-board}, ${BUILD_DIR}, app=${APP_MODE:-canonical-app})"
idf.py -B "${BUILD_DIR}" "${CMAKE_ARGS[@]}" build
''')

# Runtime split guard protects behavior ownership rather than file size.
runtime_guard = ROOT / "scripts/check_runtime_boundaries.py"
runtime_guard.write_text('''#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
bootstrap = (root / "src/climate/ClimateV6RealInputRuntime.cpp").read_text()
coordinator = (root / "src/climate/runtime/RealInputRuntimeCoordinator.cpp").read_text()
composition = (root / "src/climate/runtime/RealInputRuntimeComposition.cpp").read_text()
errors = []

for token in (
    "buildStage27ScheduleIntent",
    "buildLampSafetyEnvelope",
    "syncFromStateStore",
    "buildOutputExecutionTelemetry",
    "setCycleContext",
    ".application.tick",
):
    if token in bootstrap:
        errors.append(f"cycle-logic-leaked-to-bootstrap:{token}")

for token in (
    "RealInputRuntimeCoordinator coordinator",
    "coordinator.tick(loop_started_us)",
    '"climate/runtime/RuntimeBuildConfig.h"',
):
    if token not in bootstrap:
        errors.append(f"bootstrap-boundary-missing:{token}")

for token in (
    "buildStage27ScheduleIntent",
    "buildLampSafetyEnvelope",
    "services_.runtime_lifecycle.tick",
    "services_.automation_control.tick",
    "services_.maintenance_control.tick",
    "services_.supervisor_sink.setCycleContext",
    "services_.application.tick",
    "services_.output_persistence.syncFromStateStore",
    "buildOutputExecutionTelemetry",
):
    if token not in coordinator:
        errors.append(f"coordinator-cycle-step-missing:{token}")

for token in (
    "RuntimeOutputOwner::RuntimeOutputOwner",
    "OutputSupervisorResolver",
    "OutputSupervisorExecutor",
    "ClimateOutputSupervisorSink",
):
    if token not in composition:
        errors.append(f"composition-owner-missing:{token}")

if errors:
    print("RUNTIME_BOUNDARY_FAIL " + ",".join(errors), file=sys.stderr)
    raise SystemExit(1)
print("RUNTIME_BOUNDARY_PASS")
''')

# Strengthen configuration SSOT across all production C++ and generic launch tooling.
ssot = ROOT / "scripts/check_runtime_config_ssot.py"
ssot.write_text('''#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "src/climate/ClimateV6RealInputRuntime.cpp"
CMAKE = ROOT / "src/CMakeLists.txt"
CROWPANEL = ROOT / "scripts/stage27c_crowpanel.sh"
IDF_GATE = ROOT / "scripts/idf_gate_build.sh"
BUILD_CONFIG = ROOT / "src/climate/runtime/RuntimeBuildConfig.h.in"


def fail(message: str) -> None:
    print(f"RUNTIME_CONFIG_SSOT_FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


runtime_text = RUNTIME.read_text(encoding="utf-8")
cmake_text = CMAKE.read_text(encoding="utf-8")
crowpanel_text = CROWPANEL.read_text(encoding="utf-8")
idf_gate_text = IDF_GATE.read_text(encoding="utf-8")
build_config_text = BUILD_CONFIG.read_text(encoding="utf-8")

for path in sorted((ROOT / "src").rglob("*")):
    if path.suffix not in {".cpp", ".cc", ".h", ".hpp"}:
        continue
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if line.lstrip().startswith("#ifndef GROWBOX_"):
            fail(f"{path.relative_to(ROOT)}:{line_number} contains a production fallback default")

if '"climate/runtime/RuntimeBuildConfig.h"' not in runtime_text:
    fail("real-input runtime does not consume the generated RuntimeBuildConfig")
for token in ("kBoardProfile", "kFirmwareGitSha"):
    if token not in build_config_text:
        fail(f"generated RuntimeBuildConfig is missing {token}")

if "config/runtime/GrowboxRuntimeConfig.cmake" not in cmake_text:
    fail("src/CMakeLists.txt does not include canonical GrowboxRuntimeConfig.cmake")
if "RuntimeBuildConfig.h.in" not in cmake_text or "configure_file" not in cmake_text:
    fail("src/CMakeLists.txt does not generate RuntimeBuildConfig.h")

# Generic gate forwards explicit overrides only. Defaults belong to canonical CMake.
if 'PROFILE="${IDF_GATE_PROFILE:-}"' not in idf_gate_text:
    fail("generic IDF gate does not defer the board default to canonical CMake")
if 'APP_MODE="${IDF_GATE_APP_MODE:-}"' not in idf_gate_text:
    fail("generic IDF gate does not defer the app-mode default to the project root")
if "esp32s3-devkitc1-n16r8" in idf_gate_text:
    fail("generic IDF gate duplicates the canonical board-profile default")

# The CrowPanel launcher may select profiles and forward explicit user overrides,
# but board pin values belong only to config/boards/*.cmake.
for forbidden in (
    "GROWBOX_I2C_SDA_GPIO=21",
    "GROWBOX_I2C_SCL_GPIO=38",
    "GROWBOX_SD_MOSI_GPIO=40",
    "GROWBOX_SD_MISO_GPIO=13",
    "GROWBOX_SD_SCLK_GPIO=39",
    "GROWBOX_SD_CS_GPIO=10",
    "GROWBOX_SD_POWER_GPIO=42",
    "GROWBOX_RF433_TX_GPIO:-8",
    "GROWBOX_RF433_RX_GPIO:-14",
):
    if forbidden in crowpanel_text:
        fail(f"CrowPanel launcher duplicates canonical hardware value: {forbidden}")

required_files = (
    ROOT / "config/boards/esp32s3-devkitc1-n16r8.cmake",
    ROOT / "config/boards/crowpanel-esp32s3-2_9-n8r8.cmake",
    ROOT / "config/runtime/profiles/generic.cmake",
    ROOT / "config/runtime/profiles/stage27c-crowpanel.cmake",
    BUILD_CONFIG,
)
for path in required_files:
    if not path.is_file():
        fail(f"missing canonical config input {path.relative_to(ROOT)}")

print("RUNTIME_CONFIG_SSOT_PASS")
''')

console_guard = ROOT / "scripts/check_service_console_boundaries.py"
console_guard_text = console_guard.read_text()
required_anchor = '''required = (
    "output_commands_.handle", "storage_commands_.handle", "system_commands_.handle",
    "uart_read_bytes", "uart_write_bytes",
)
'''
required_replacement = '''required = (
    "serviceConsoleCommandDomain(command.kind)",
    "output_commands_.handle", "storage_commands_.handle", "system_commands_.handle",
    "uart_read_bytes", "uart_write_bytes",
)
'''
if console_guard_text.count(required_anchor) != 1:
    raise SystemExit('service-console guard anchor mismatch')
console_guard.write_text(console_guard_text.replace(required_anchor, required_replacement, 1))

quality_gate = ROOT / "scripts/quality_gate_push.sh"
replace_once(
    quality_gate,
    'echo "==> runtime configuration SSOT"\n"$PY" "${ROOT}/scripts/check_runtime_config_ssot.py"\n',
    'echo "==> runtime configuration SSOT"\n"$PY" "${ROOT}/scripts/check_runtime_config_ssot.py"\n\necho "==> runtime composition boundaries"\n"$PY" "${ROOT}/scripts/check_runtime_boundaries.py"\n',
)
