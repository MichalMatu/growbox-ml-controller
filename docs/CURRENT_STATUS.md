# Current controller status

Updated: 2026-09-10
Development branch: `mvp/environment-controller`
Latest handoff: `docs/ARCHITECTURE_HANDOFF.md`
Execution architecture design: `docs/OUTPUT_EXECUTION_ARCHITECTURE.md`
Implementation plan: `docs/OUTPUT_EXECUTION_IMPLEMENTATION_PLAN.md`
Frozen Phase H evidence: `docs/STAGE28E_PHASE_H_HANDOFF.md`

## Current transition

**Stage27C FROZEN -> Stage28E A-G COMPLETE -> OUTPUT EXECUTION ARCHITECTURE A1-A12 COMPLETE -> A13 + PHYSICAL H COMPLETE**

The OutputSupervisor architecture has completed its final software qualification and the authorized physical Phase H qualification. The old H v8 path remains historical and must not be executed.

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

Phase H is **PASS** for exact production identity `02208d23f403bca3540dbbd652eb55703a044833` with tooling identity `2a19cd43646fe284a7ab41828178b2b8f17edea1`.

Terminal Local Agent evidence: `20260910-output-supervisor-physical-h-v3`.

The bounded single-open hardware run proved the normal production chain without manual fan commands or raw RF:

```text
natural climate ControlIntent
-> OutputSupervisor resolution
-> BinaryActuatorPolicy eligibility
-> OutputPlan command
-> RF433OutputTransport TxResult
-> independent Shelly aggregate-power support
-> environmental response support
```

Counted evidence:

- natural fan OFF baseline from uptime `651463 ms`;
- natural humidity-driven `ClimateDecision` fan ON at uptime `884293 ms`, requested level `0.111`;
- Shelly median power `22.0 W -> 24.8 W`, delta `+2.8 W` across exactly 8 + 8 samples;
- inside-minus-outside absolute-humidity gradient contracted by `0.381 g/m3` (frozen requirement `>=0.30 g/m3`);
- formal OutputSupervisor replay PASS on `02208d23f403bca3540dbbd652eb55703a044833`;
- final supervisor-owned `automation off` reached `Disabled`, fan OFF, humidifier OFF, transport clean;
- `raw_rf=0`; `/dev/cu.usbserial-10` remained untouched.

One-way RF transport completion is still not treated as physical acknowledgement; Shelly and the environmental response remain independent supporting evidence.

## Hardware boundary

The authorized Phase H hardware run is complete. No further hardware execution is required to establish this Phase H PASS.

Qualified Growbox serial device:

`/dev/cu.usbserial-1130`

Never touch:

`/dev/cu.usbserial-10`

Standing safety invariants remain unchanged:

- deterministic rule controller remains authoritative;
- ML remains shadow/research-only;
- thermal trip remains `>=28 C`;
- thermal recovery remains `<=26 C` continuously for 10 minutes;
- safety remains active when automation is disabled;
- one-way RF never implies physical acknowledgement;
- raw RF remains restricted to explicit `MaintenanceLocked` handling;
- `OutputSupervisor` remains the only normal production owner of configured physical outputs.

Any future production-source change invalidates the current A12/A13/physical-H executable qualification and requires requalification before further hardware claims.

## Local Agent execution identity

- repository: `MichalMatu/growbox-ml-controller`;
- repository id: `growbox-ml-controller`;
- agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`;
- control branch: `agent-control`;
- work branch: `mvp/environment-controller`.

Every Local Agent task must use the exact binding, `work_branch: mvp/environment-controller`, and `resources: []`. Verify exact SHA in-task whenever source identity matters and read terminal `.agent/results/<task-id>.json` before reporting PASS.

## Immediate next work

Phase H is complete. No further Phase H execution is required unless production source changes or a new hardware qualification target is intentionally introduced.

Preserve the terminal evidence above and the historical failed-safe attempts; do not rerun historical H v8.
