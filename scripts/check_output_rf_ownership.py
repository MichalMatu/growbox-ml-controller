#!/usr/bin/env python3
"""Final configured-output RF ownership invariant.

Normal climate, schedule, safety, runtime and service-console code may compose
output execution, but must not own RF transmission calls. The only legal
production call sites are the dedicated RF transport layers plus the explicit
maintenance-only adapter.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LOW_LEVEL_RMT = {
    "rmt_new_tx_channel(": {"src/climate/rf433/Rf433RmtLoopback.cpp"},
    "rmt_transmit(": {"src/climate/rf433/Rf433RmtLoopback.cpp"},
    "rmt_tx_wait_all_done(": {"src/climate/rf433/Rf433RmtLoopback.cpp"},
}
RADIO_TX = {
    "transmitAndReceive(": {
        "src/climate/rf433/Rf433RmtLoopback.cpp",
        "src/climate/rf433/Rf433RmtFrameSender.cpp",
        "src/climate/runtime/diagnostics/Stage28RfDiagnostics.cpp",
    },
    "transmitFrame(": {
        "src/climate/rf433/Rf433RmtFrameSender.cpp",
        "src/climate/rf433/Rf433OutputTransport.cpp",
    },
    "manualTransmit(": {
        "src/climate/runtime/diagnostics/Stage28RfDiagnostics.cpp",
        "src/climate/runtime/Stage28MaintenanceRfTransport.cpp",
    },
}

AUTO_SMOKE_TOKENS = (
    "auto_smoke",
    "smoke_attempted_",
    "runSmoke",
    "GROWBOX_RF433_LOOPBACK_AUTO_SMOKE",
    "GROWBOX_RF433_LOOPBACK_SMOKE_",
)

RUNTIME_FORBIDDEN = (
    "Stage28dRfOutputEndpoint",
    "MappedClimateRoleDriver",
    "SwitchableRoleDriver",
    "ClimateActuatorAdapter",
    "writeScheduledLight(",
    "setSafetyForceExhaust(",
    "forceSafeStateWithRetries",
    "physical_endpoint",
    ".manualTransmit(",
    ".transmitFrame(",
    ".transmitAndReceive(",
    "rmt_transmit(",
)

SERVICE_CONSOLE_FORBIDDEN = (
    "manualTransmit(",
    "transmitFrame(",
    "transmitAndReceive(",
    "rmt_transmit(",
)

LEGACY_FIRMWARE_SOURCES = (
    '"climate/Stage28dBinaryRoleArbiter.cpp"',
    '"climate/Stage28dRfOutputEndpoint.cpp"',
)

RAW_SEND_RE = re.compile(r"(?<![A-Za-z0-9_])(transport_|raw_transport_)\.send\(")
RAW_SEND_ALLOW = {
    "src/climate/output/supervisor/OutputSupervisorExecutor.cpp",
    "src/climate/output/lifecycle/OutputLifecycleExecutor.cpp",
    "src/climate/output/control/OutputMaintenanceControl.cpp",
}

# These files remain only as host compatibility/parity evidence. A separate
# CMake invariant below forbids compiling them into production firmware again.
RETIRED_COMPAT_CPP = {
    "src/climate/Stage28dBinaryRoleArbiter.cpp",
    "src/climate/Stage28dRfOutputEndpoint.cpp",
}


def production_cpp(root: Path):
    return sorted(
        path
        for path in (root / "src").rglob("*.cpp")
        if path.relative_to(root).as_posix() not in RETIRED_COMPAT_CPP
    )


def relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def cpp_sites(root: Path, token: str) -> set[str]:
    sites: set[str] = set()
    for path in production_cpp(root):
        if token in path.read_text():
            sites.add(relative(root, path))
    return sites


def find_violations(root: Path = ROOT) -> list[str]:
    errors: list[str] = []

    required = (
        "src/climate/rf433/Rf433RmtLoopback.cpp",
        "src/climate/rf433/Rf433RmtFrameSender.cpp",
        "src/climate/rf433/Rf433OutputTransport.cpp",
        "src/climate/runtime/diagnostics/Stage28RfDiagnostics.cpp",
        "src/climate/runtime/Stage28MaintenanceRfTransport.cpp",
        "src/climate/output/supervisor/OutputSupervisorExecutor.cpp",
        "src/climate/output/lifecycle/OutputLifecycleExecutor.cpp",
        "src/climate/output/control/OutputMaintenanceControl.cpp",
        "src/climate/ClimateV6RealInputRuntime.cpp",
        "src/climate/runtime/console/Stage28ServiceConsole.cpp",
        "src/climate/runtime/console/Stage28ServiceConsoleCommand.cpp",
        "src/CMakeLists.txt",
        "scripts/stage27c_crowpanel.sh",
    )
    for rel in required:
        if not (root / rel).is_file():
            errors.append(f"{rel}: required ownership surface missing")

    if errors:
        return errors

    for token, allowed in {**LOW_LEVEL_RMT, **RADIO_TX}.items():
        actual = cpp_sites(root, token)
        unexpected = actual - allowed
        missing = allowed - actual
        for rel in sorted(unexpected):
            errors.append(f"{rel}: forbidden configured-output TX token {token!r}")
        for rel in sorted(missing):
            errors.append(f"{rel}: expected ownership token missing {token!r}")

    raw_send_sites: set[str] = set()
    for path in production_cpp(root):
        if RAW_SEND_RE.search(path.read_text()):
            raw_send_sites.add(relative(root, path))
    for rel in sorted(raw_send_sites - RAW_SEND_ALLOW):
        errors.append(
            f"{rel}: raw OutputTransport send call outside supervisor/maintenance boundary"
        )
    for rel in sorted(RAW_SEND_ALLOW - raw_send_sites):
        errors.append(f"{rel}: expected supervisor/maintenance transport send call missing")

    runtime_path = root / "src/climate/ClimateV6RealInputRuntime.cpp"
    runtime = runtime_path.read_text()
    for token in RUNTIME_FORBIDDEN:
        if token in runtime:
            errors.append(
                f"{relative(root, runtime_path)}: forbidden direct output owner token {token!r}"
            )

    for rel in (
        "src/climate/runtime/console/Stage28ServiceConsole.cpp",
        "src/climate/runtime/console/Stage28ServiceConsoleCommand.cpp",
    ):
        text = (root / rel).read_text()
        for token in SERVICE_CONSOLE_FORBIDDEN:
            if token in text:
                errors.append(f"{rel}: service console must not own TX token {token!r}")

    cmake = (root / "src/CMakeLists.txt").read_text()
    for token in LEGACY_FIRMWARE_SOURCES:
        if token in cmake:
            errors.append(f"src/CMakeLists.txt: legacy execution owner still compiled {token}")

    output_transport = (root / "src/climate/rf433/Rf433OutputTransport.cpp").read_text()
    for token in ("Stage28RfDiagnostics", "manualTransmit("):
        if token in output_transport:
            errors.append(
                f"src/climate/rf433/Rf433OutputTransport.cpp: normal transport depends on diagnostics {token!r}"
            )

    maintenance = (root / "src/climate/runtime/Stage28MaintenanceRfTransport.cpp").read_text()
    for required_token in (
        "OutputSource::Maintenance",
        "OutputReason::MaintenanceRequest",
        "diagnostics_.manualTransmit(",
    ):
        if required_token not in maintenance:
            errors.append(
                "src/climate/runtime/Stage28MaintenanceRfTransport.cpp: "
                f"maintenance-only guard missing {required_token!r}"
            )

    diagnostics = (root / "src/climate/runtime/diagnostics/Stage28RfDiagnostics.cpp").read_text()
    if "if (config_.passive_capture)" not in diagnostics or "capturePassive();" not in diagnostics:
        errors.append(
            "src/climate/runtime/diagnostics/Stage28RfDiagnostics.cpp: passive RX path missing"
        )
    if diagnostics.count("transmitAndReceive(") != 1:
        errors.append(
            "src/climate/runtime/diagnostics/Stage28RfDiagnostics.cpp: TX must remain only in explicit manualTransmit"
        )

    for rel in (
        "src/climate/runtime/diagnostics/Stage28RfDiagnostics.h",
        "src/climate/runtime/diagnostics/Stage28RfDiagnostics.cpp",
        "src/climate/ClimateV6RealInputRuntime.cpp",
        "src/CMakeLists.txt",
        "scripts/stage27c_crowpanel.sh",
    ):
        text = (root / rel).read_text()
        for token in AUTO_SMOKE_TOKENS:
            if token in text:
                errors.append(f"{rel}: forbidden production auto-smoke token {token!r}")

    return errors


def main() -> int:
    errors = find_violations(ROOT)
    if errors:
        for error in errors:
            print(f"OUTPUT_EXECUTION_OWNERSHIP_FAIL {error}", file=sys.stderr)
        return 1
    print("OUTPUT_EXECUTION_OWNERSHIP_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
