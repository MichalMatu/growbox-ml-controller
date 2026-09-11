#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
bootstrap = (root / "src/climate/ClimateV6RealInputRuntime.cpp").read_text()
coordinator = (root / "src/climate/runtime/RealInputRuntimeCoordinator.cpp").read_text()
composition = (root / "src/climate/runtime/RealInputRuntimeComposition.cpp").read_text()
composition += (root / "src/climate/runtime/RealInputRuntimeComposition.h").read_text()
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
