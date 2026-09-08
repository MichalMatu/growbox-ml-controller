# Output Execution Architecture R5 Audit

Status: PASS
Updated: 2026-09-09
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Audited production source HEAD: `5d56478a24738e54136fd554cbccc0cb05fcd5d1`

## Purpose

This is the final architecture re-audit after A1-A11. It verifies the implemented
output-execution architecture before A12 stabilization and the single final full
software gate. The audit does not change production C++ and does not use hardware,
serial, flashing, or RF transmission.

## Final production invariant

`OutputSupervisor` is the only normal production owner allowed to execute configured
physical outputs. The explicit `MaintenanceLocked` raw-RF path is a separate,
guarded maintenance capability and is not a normal production output owner.

## Evidence verified

- `scripts/check_output_rf_ownership.py` passes on the audited source SHA.
- The focused supervisor, lifecycle, runtime-lifecycle, automation, manual,
  maintenance, state-store, telemetry, persistence and climate-supervisor host tests pass.
- `runClimateV6RealInputRuntime()` composes a static `RuntimeOutputOwner`; climate,
  schedule and hard-safety data enter the supervisor rather than writing RF directly.
- Boot, recovery and fault containment are supervisor lifecycle operations.
- Normal manual commands are intents; raw RF is reachable only through the
  maintenance adapter and `MaintenanceLocked` control path.
- The low-level RMT transmitter remains singular; diagnostics keeps passive RX and
  its explicit manual TX entry is isolated behind the maintenance adapter.
- Retired `Stage28dRfOutputEndpoint` and `Stage28dBinaryRoleArbiter` compatibility
  sources are not part of production firmware CMake composition.
- `OutputStateStore` keeps command truth separate from independent physical
  observation; RF TX completion does not fabricate physical acknowledgement.
- Execution reports keep physical state `Unknown` without independent feedback.
- Honest output telemetry v2 reports requested/resolved/attempted/transport/last-command
  truth separately from physical observation.
- The initial implementation remains synchronous in the existing main task; no new
  supervisor FreeRTOS task or queue ownership was introduced.
- RF-enabled main-task stack remains `16384` bytes. A11.5 measured the runtime entry
  frame at 32 bytes before and after composition cleanup; long-lived output objects
  moved to static storage, adding 2472 bytes of `.bss` rather than permanent main-stack use.

## Normative amendment closure

R-A1 through R-A13 from `OUTPUT_EXECUTION_IMPLEMENTATION_PLAN_REAUDIT.md` are satisfied:
endpoint identity is unified; one RMT owner remains; RF success is local TX completion;
climate injection and previous-state migration were split; legacy safety copies are
inactive in production; propose/commit semantics are preserved; state store and binary
policy remain distinct; main-loop serialization is retained; NVS ownership is bounded;
maintenance shares the radio only under its lifecycle lock; and the final ownership
guard uses a narrow explicit allowlist.

## Result

No architecture blocker was found. A11 exit criteria are satisfied and the codebase is
ready for A12.1 focused stabilization. Hardware remains deferred until A13.3 explicit
authorization.

**R5 FINAL ARCHITECTURE RE-AUDIT: PASS.**
