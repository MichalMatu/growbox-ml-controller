# Current controller status

Updated: 2026-09-10
Development branch: `mvp/environment-controller`
Latest handoff: `docs/ARCHITECTURE_HANDOFF.md`
Execution architecture design: `docs/OUTPUT_EXECUTION_ARCHITECTURE.md`
Implementation plan: `docs/OUTPUT_EXECUTION_IMPLEMENTATION_PLAN.md`
Frozen Phase H evidence: `docs/STAGE28E_PHASE_H_HANDOFF.md`

## Current transition

**Stage27C FROZEN -> Stage28E A-G COMPLETE -> OUTPUT EXECUTION ARCHITECTURE A1-A12 COMPLETE -> A13 QUALIFICATION CONTRACT ACTIVE**

The OutputSupervisor architecture has completed its final software qualification. The old H v8 path remains historical and must not be executed.

## A12 software-qualified identity

Exact software-qualified production identity:

`02208d23f403bca3540dbbd652eb55703a044833`

Terminal Local Agent evidence:

`20260910-output-a12-2-final-full-software-gate-v9`

Final A12.2 result:

- exact clean SHA: PASS;
- Python software tests: PASS (`488 passed`, `3` optional Playwright visual tests skipped because Chromium was unavailable, `9` hardware tests deselected);
- host C++ tests: PASS (`49/49`);
- lint / format / schema / pre-push: PASS;
- fake-output firmware build: PASS;
- real-output firmware build, software-only: PASS;
- RF-enabled production build evidence: PASS;
- output/RF ownership invariant: PASS;
- configured main-task stack: `16384` bytes;
- measured runtime frame: `32` bytes;
- firmware binary: `771920` bytes;
- text: `617469` bytes;
- data: `154332` bytes;
- bss: `1356861` bytes;
- reported static DRAM metric: `1511193` bytes;
- `hardware_started=0`.

A12.2 initially exposed repository formatting and two stale standalone Stage28D linkage lists. Each source/build-graph defect was fixed with a bounded focused verification before the next full attempt. Failed full-gate attempts remain preserved as evidence. Only the final PASS SHA above is software-qualified.

## Architecture invariant

> `OutputSupervisor` is the only normal production owner allowed to execute configured physical outputs.

Standing ownership rules:

- climate produces `ControlIntent` and does not transmit;
- schedule/manual paths produce intents and do not directly transmit;
- safety produces a non-bypassable `SafetyEnvelope` and does not transmit;
- `OutputSupervisor` resolves mode, policy, intents and safety into execution;
- `BinaryActuatorPolicy` owns hysteresis/dwell, not transport;
- RF433 transport is narrow and policy-free;
- state distinguishes requested/resolved/commanded/transport result from physical observation;
- raw RF TX is allowed only through the explicit `MaintenanceLocked` path;
- the static ownership guard must continue to pass.

## Phase H state

Phase H is **not PASS**. An authorized hardware preflight started, failed safe in `FaultLocked`, and exposed a startup partial-command-truth defect that is now fixed and requalified in software.

Historical H v8 is frozen and must not be reused. Its software preflight identity `231eed28f64bdbdc4238fd8bce128264027702f2` predates the new production architecture and is historical evidence only.

The next sequence is:

1. retarget A13.1 tooling/docs to the replacement A12-qualified SHA;
2. rerun A13.2 software-only preflight with `hardware_started=0`;
3. rerun the bounded hardware preflight on `/dev/cu.usbserial-1130`;
4. only after that PASS, execute the natural Climate -> OutputSupervisor physical H proof.

The new H contract must prove the normal chain:

```text
natural climate ControlIntent
-> OutputSupervisor resolution
-> BinaryActuatorPolicy eligibility
-> OutputPlan command
-> RF433OutputTransport TxResult
-> independent physical evidence
-> environmental response evidence
```

It must distinguish request, selected/resolved command, transport completion and physical evidence. A successful one-way RF transmission must never be treated as physical acknowledgement.

## Hardware boundary

Operator hardware authorization was granted on 2026-09-10. Because production source changed after the first physical preflight, no further hardware access is allowed until the replacement A13.2 software preflight passes:

- no serial access;
- no USB probing;
- no flashing;
- no RF TX;
- no physical-output tests;
- `hardware_started=0`.

Correct Growbox serial device for a future explicitly authorized hardware task:

`/dev/cu.usbserial-1130`

Never touch:

`/dev/cu.usbserial-10`

Standing safety invariants:

- deterministic rule controller remains authoritative;
- ML remains shadow/research-only;
- thermal trip remains `>=28 C`;
- thermal recovery remains `<=26 C` continuously for 10 minutes;
- safety remains active when automation is disabled;
- Shelly master stays ON during any future bounded qualification;
- future hardware tasks must restore and prove the defined safe final state.

## Local Agent execution identity

- repository: `MichalMatu/growbox-ml-controller`;
- repository id: `growbox-ml-controller`;
- agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`;
- control branch: `agent-control`;
- work branch: `mvp/environment-controller`.

Every Local Agent task must use the exact binding, `work_branch: mvp/environment-controller`, and `resources: []`. Verify exact SHA in-task whenever source identity matters and read terminal `.agent/results/<task-id>.json` before reporting PASS.

## Immediate next work

1. Define A13.1 against OutputSupervisor telemetry v2 and the A12-qualified SHA.
2. Add software-testable parsing/replay fixtures for the new H observer contract.
3. Run A13.2 software-only preflight with no serial, flash, RF TX or hardware access.
4. Stop before hardware and require explicit operator authorization.
