#!/usr/bin/env python3
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
bootstrap = (root / "src/climate/ClimateV6RealInputRuntime.cpp").read_text(encoding="utf-8")
coordinator = (root / "src/climate/runtime/RealInputRuntimeCoordinator.cpp").read_text(encoding="utf-8")
coordinator_header = (root / "src/climate/runtime/RealInputRuntimeCoordinator.h").read_text(
    encoding="utf-8"
)
composition = (root / "src/climate/runtime/RealInputRuntimeComposition.cpp").read_text(
    encoding="utf-8"
)
composition += (root / "src/climate/runtime/RealInputRuntimeComposition.h").read_text(
    encoding="utf-8"
)
transport = (root / "src/climate/runtime/RuntimeOutputTransport.cpp").read_text(encoding="utf-8")
runtime_adapters = (root / "src/climate/runtime/Stage27RuntimeAdapters.h").read_text(
    encoding="utf-8"
)
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
    "services_.outputs.runtime_lifecycle.tick",
    "services_.outputs.automation_control.tick",
    "services_.outputs.maintenance_control.tick",
    "services_.outputs.supervisor_sink.setCycleContext",
    "services_.application.tick",
    "services_.outputs.persistence.syncFromStateStore",
    "buildOutputExecutionTelemetry",
    "logOutputExecutionTelemetry",
):
    if token not in coordinator:
        errors.append(f"coordinator-cycle-step-missing:{token}")

for token in (
    "RealInputRuntimeInputServices",
    "RealInputRuntimeOutputServices",
    "RealInputRuntimeSupportServices",
):
    if token not in coordinator_header:
        errors.append(f"coordinator-domain-boundary-missing:{token}")

if '"climate/runtime/RealInputRuntimeComposition.h"' in coordinator_header:
    errors.append("coordinator-depends-on-composition-owner")

for token in (
    "RuntimeOutputOwner::RuntimeOutputOwner",
    "OutputSupervisorResolver",
    "OutputSupervisorExecutor",
    "ClimateOutputSupervisorSink",
):
    if token not in composition:
        errors.append(f"composition-owner-missing:{token}")

if "RuntimeOutputTransport::send" in composition:
    errors.append("transport-implementation-leaked-to-composition")

for token in (
    "TransportStatus::NotAttempted",
    "TransportError::Unavailable",
    "!execution_status_.transport_available",
):
    if token not in transport:
        errors.append(f"locked-transport-truth-contract-missing:{token}")

locked_block = transport.split("if (!execution_status_.transport_available)", 1)
if len(locked_block) != 2:
    errors.append("locked-transport-guard-missing")
else:
    locked_body = locked_block[1].split("}", 1)[0]
    if "TransportStatus::Completed" in locked_body:
        errors.append("locked-transport-fabricates-completed")

for token in (
    "productionRuntimeConfig()",
    "ClimatePolicyMode::Rule",
    "allow_unqualified_ml_active = false",
    "static_assert(productionRuntimeConfig().mode",
):
    if token not in runtime_adapters:
        errors.append(f"production-rule-authority-fence-missing:{token}")

if errors:
    print("RUNTIME_BOUNDARY_FAIL " + ",".join(errors), file=sys.stderr)
    raise SystemExit(1)
print("RUNTIME_BOUNDARY_PASS")
