#!/usr/bin/env python3
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
router = (root / "src/climate/runtime/console/Stage28ServiceConsole.cpp").read_text()
forbidden = (
    "OutputAutomationControl.h",
    "OutputMaintenanceControl.h",
    "OutputManualControl.h",
    "Stage27TelemetryLogger.h",
    "Stage27FileDurability.h",
    "Rf433HardwareConfig.h",
    "printSdLogStatus",
    "handleSdLogRead",
    "handleManualOutput",
    "handleRtcSetUnix",
    "printSensors",
    "printRfList",
    "handleRfReceive",
)
errors = [item for item in forbidden if item in router]
required = (
    "serviceConsoleCommandDomain(command.kind)",
    "output_commands_.handle",
    "storage_commands_.handle",
    "system_commands_.handle",
    "uart_read_bytes",
    "uart_write_bytes",
)
errors += [f"missing:{item}" for item in required if item not in router]
if errors:
    print("SERVICE_CONSOLE_BOUNDARY_FAIL " + ",".join(errors), file=sys.stderr)
    raise SystemExit(1)
print("SERVICE_CONSOLE_BOUNDARY_PASS")
