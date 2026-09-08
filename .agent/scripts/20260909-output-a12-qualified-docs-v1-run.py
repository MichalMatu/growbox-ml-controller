import subprocess
from pathlib import Path

BASE = '1c59f3cfa239abbfbae721247d01d65a39d4bdfc'
BRANCH = 'mvp/environment-controller'


def run(cmd):
    print('+', ' '.join(str(x) for x in cmd), flush=True)
    subprocess.run([str(x) for x in cmd], check=True)


def out(cmd):
    return subprocess.check_output([str(x) for x in cmd], text=True).strip()


run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'HEAD']) != BASE or out(['git', 'rev-parse', 'FETCH_HEAD']) != BASE:
    raise SystemExit('A12_DOCS_IDENTITY_FAIL')
if out(['git', 'status', '--porcelain']):
    raise SystemExit('A12_DOCS_DIRTY_START')

qualification = '''# OutputSupervisor A12 Software Qualification

Updated: 2026-09-09
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Qualified executable SHA: `1c59f3cfa239abbfbae721247d01d65a39d4bdfc`
Final gate: `20260909-output-a12-2-final-full-software-gate-v8`
Status: PASS
Hardware started: `0`

## Qualified identity

`1c59f3cfa239abbfbae721247d01d65a39d4bdfc` is the software-qualified OutputSupervisor architecture identity.

Later documentation/tooling-only commits do not replace this executable identity unless production firmware source changes and a new full qualification is run.

## Final A12.2 evidence

The final full software gate passed on an exact clean local/remote SHA and ended with the same clean identity.

- pre-commit / lint / format / schema: PASS;
- canonical pre-push software quality gate: PASS;
- output/RF ownership invariant: PASS;
- Python software tests: `488 passed`, `3 skipped`, `9 hardware deselected`;
- the three skipped tests are the repository's optional environment-dependent Playwright panel visual regressions;
- host C++ CTest: `49/49` PASS;
- Stage28D standalone bounded-output regressions: PASS;
- host clang-tidy: PASS;
- fake-output firmware build: PASS;
- real-output RF-enabled firmware build, software-only: PASS;
- RF auto-smoke TX disabled;
- remote RF capture disabled;
- no serial, flash, USB probing, RF TX, or physical output execution;
- `hardware_started=0`.

## Static build evidence

RF-enabled real-output build:

- `main_stack=16384`;
- `runtime_frame=32`;
- `text=617445`;
- `data=154332`;
- `bss=1356861`;
- `static_dram=1511193`;
- `firmware_bin=771888` bytes.

These are static/software build metrics, not runtime hardware measurements.

## Failed-attempt evidence retained

A12.2 intentionally retained failed attempts rather than overwriting them:

- v1/v2: task-schema validation failures; no commands started;
- v3: real repository formatting/lint defect found before the full gate could continue;
- focused formatting repair produced `f1b185b6240f3bd1264d8295b988be2a9d39caea` and passed focused verification;
- v4/v5: worker memory-limit failures caused by unbounded host build parallelism; source identity unchanged;
- v6: full gate exposed stale standalone Stage28D output-link dependencies;
- focused linkage repair produced `b5e03a5e73d42579e2cce47f74f9071472981827` and passed focused verification;
- v7: full gate exposed the analogous stale standalone arbiter dependency;
- focused linkage repair produced `1c59f3cfa239abbfbae721247d01d65a39d4bdfc` and passed focused verification;
- v8: final full PASS on `1c59f3cfa239abbfbae721247d01d65a39d4bdfc`.

The full-gate runner bounded CMake/Ninja build concurrency only to stay within the Local Agent RSS watchdog. It did not reduce test scope.

## Architecture invariant qualified

`OutputSupervisor` is the only normal production owner that can execute configured physical outputs.

Raw RF transmission remains a maintenance-only capability guarded by `MaintenanceLocked`. Safety, schedule, climate, and normal service-console paths do not become independent transport owners.

## Next stage

A13 replaces the frozen historical H v8 path.

1. A13.1 — define a new OutputSupervisor H qualification contract and observer semantics around honest output telemetry v2.
2. A13.2 — run a software-only preflight for the exact A12 executable identity and the new H tooling, with `hardware_started=0`.
3. Stop before hardware and require explicit operator authorization.

Do not execute historical H v8.
'''

current_status = '''# Current controller status

Updated: 2026-09-09
Development branch: `mvp/environment-controller`
Architecture: `docs/OUTPUT_EXECUTION_ARCHITECTURE.md`
Implementation plan: `docs/OUTPUT_EXECUTION_IMPLEMENTATION_PLAN.md`
Final architecture audit: `docs/OUTPUT_EXECUTION_ARCHITECTURE_AUDIT.md`
A12 qualification: `docs/OUTPUT_SUPERVISOR_A12_SOFTWARE_QUALIFICATION.md`
Continuation: `docs/CONTINUATION_PLAN.md`
Handoff: `docs/ARCHITECTURE_HANDOFF.md`
Frozen historical H evidence: `docs/STAGE28E_PHASE_H_HANDOFF.md`

## Current state

**OUTPUTSUPERVISOR ARCHITECTURE SOFTWARE-QUALIFIED -> A13 NEW H CONTRACT/PREFLIGHT -> HARDWARE STOP**

Qualified executable identity:

`1c59f3cfa239abbfbae721247d01d65a39d4bdfc`

A12.2 final full gate `20260909-output-a12-2-final-full-software-gate-v8`: PASS.

Key evidence:

- canonical Python software suite PASS (`488 passed`, `3 optional visual skipped`, `9 hardware deselected`);
- host C++ `49/49` PASS;
- lint/format/schema/pre-push PASS;
- fake-output firmware PASS;
- real-output RF-enabled software build PASS;
- output/RF ownership invariant PASS;
- `main_stack=16384`, `runtime_frame=32`;
- firmware binary `771888` bytes;
- `hardware_started=0`.

## Production invariant

`OutputSupervisor` is the only normal production owner allowed to execute configured physical outputs.

- climate produces control intent;
- schedule produces schedule intent;
- normal manual control produces manual intent;
- safety produces a non-bypassable envelope;
- binary hysteresis/dwell is policy, not transport ownership;
- RF433 transport transmits validated plans only;
- command state does not claim one-way RF physical acknowledgement;
- raw RF TX is restricted to explicit `MaintenanceLocked` maintenance flow.

## Active work

A13.1 is next: define a new OutputSupervisor H qualification contract. Do not reuse historical H v8.

A13.2 then runs a software-only preflight for the exact A12 executable identity and new H tooling. It must not open serial, flash, transmit RF, probe USB, or touch hardware, and must record `hardware_started=0`.

After A13.2 PASS, stop for explicit operator authorization before any physical qualification.

## Hardware boundary

No hardware is authorized now.

Future authorized Growbox serial port: `/dev/cu.usbserial-1130`.

Never touch: `/dev/cu.usbserial-10`.

Standing safety constraints remain unchanged: deterministic controller authoritative, ML shadow/research-only, thermal trip `>=28 C`, recovery `<=26 C` continuously for 10 minutes, and future hardware work must restore/prove its defined safe final state.

## Local Agent identity

- repository: `MichalMatu/growbox-ml-controller`;
- repository id: `growbox-ml-controller`;
- agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`;
- control branch: `agent-control`;
- work branch: `mvp/environment-controller`;
- every task uses `resources: []`.
'''

continuation = '''# Fresh-context continuation plan

Updated: 2026-09-09
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Local Agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`
Qualified executable SHA: `1c59f3cfa239abbfbae721247d01d65a39d4bdfc`
A12 evidence: `docs/OUTPUT_SUPERVISOR_A12_SOFTWARE_QUALIFICATION.md`

## Read first

1. `AGENTS.md`
2. `docs/OUTPUT_SUPERVISOR_A12_SOFTWARE_QUALIFICATION.md`
3. `docs/OUTPUT_EXECUTION_ARCHITECTURE.md`
4. `docs/OUTPUT_EXECUTION_ARCHITECTURE_AUDIT.md`
5. `docs/OUTPUT_EXECUTION_IMPLEMENTATION_PLAN.md`
6. `docs/CURRENT_STATUS.md`
7. `docs/ARCHITECTURE_HANDOFF.md`
8. `docs/STAGE28E_PHASE_H_HANDOFF.md` only as frozen historical evidence

Then fetch fresh branch HEAD, fresh `agent-control:.agent/status/daemon.json`, and relevant terminal `.agent/results/...` evidence. Never continue from remembered state alone.

## Completed

- R5 final architecture re-audit: PASS;
- A12.1 focused stabilization: PASS;
- A12.2 final full software qualification: PASS;
- qualified executable identity: `1c59f3cfa239abbfbae721247d01d65a39d4bdfc`;
- hardware started: `0`.

## Next sequence

### A13.1 — new OutputSupervisor H qualification contract

Define a new contract/tooling path. It must prove:

```text
natural climate ControlIntent
-> OutputSupervisor resolution
-> BinaryActuatorPolicy eligibility
-> OutputPlan fan OFF->ON command
-> RF433OutputTransport TxResult
-> independent Shelly power support
-> environmental response evidence
```

The observer contract must consume honest output telemetry v2 and distinguish requested, selected/resolved, command-attempt, transport-result, last-command, and independent physical evidence.

It must verify correct supervisor mode, no maintenance mode, no hard-safety cause for the counted normal transition, exact A12 qualified executable identity, zero unexpected transport errors, and supervisor-owned recovery/final state.

Historical H v8 is not authorized and must not be executed.

### A13.2 — software-only H preflight

Run against the exact A12 executable identity plus the new H tooling.

Allowed: software builds, static checks, fixture replay, parser/contract tests.

Forbidden: serial, flash, RF TX, USB probing, hardware access, physical-output execution.

Required marker: `hardware_started=0`.

### A13.3 — mandatory stop

After A13.2 PASS, stop. Physical H requires explicit operator authorization.

## Binding and hardware constraints

Every Local Agent task must contain the exact binding, `work_branch: mvp/environment-controller`, and `resources: []`.

No hardware task is authorized now. If authorization is later granted, only `/dev/cu.usbserial-1130` is the Growbox port and `/dev/cu.usbserial-10` must be explicitly rejected.
'''

handoff = '''# Execution Architecture Handoff

Updated: 2026-09-09
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Local Agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`
Qualified executable SHA: `1c59f3cfa239abbfbae721247d01d65a39d4bdfc`
A12 qualification: `docs/OUTPUT_SUPERVISOR_A12_SOFTWARE_QUALIFICATION.md`

## Handoff state

The OutputSupervisor architecture migration and final software qualification are complete.

A12.2 final full software gate passed on exact clean SHA `1c59f3cfa239abbfbae721247d01d65a39d4bdfc`. No hardware was started.

The next work is A13.1 and A13.2 only. Stop before hardware.

## Qualified architecture invariant

`OutputSupervisor` is the only normal production component allowed to execute configured physical outputs.

Safety produces constraints, schedule/manual/climate produce intents, binary policy owns hysteresis/dwell, transport performs validated transmission, and state records command truth without fabricating physical acknowledgement.

Raw RF transmission is retained only as explicitly guarded `MaintenanceLocked` maintenance behavior.

## New Phase H direction

Do not run historical H v8.

A13.1 must define a new hardware qualification contract against the supervisor architecture and output telemetry v2. The counted natural fan transition must establish the chain from climate intent through supervisor resolution, binary eligibility, output plan, transport completion, independent Shelly power evidence, and environmental response.

A13.2 must be software-only and must validate the exact A12 executable identity plus new H tooling without serial, flash, USB probing, RF TX, or hardware access. Record `hardware_started=0`.

After A13.2 PASS, stop for explicit operator authorization.

## Frozen historical H evidence

The previous Stage28E H material remains historical evidence only:

- old production identity `5a4830db9d10e8cb73d4c617b09122f0844ad899`;
- old H v8 preflight identity `231eed28f64bdbdc4238fd8bce128264027702f2`;
- old H v8 hardware execution was never started.

Do not reinterpret those artifacts as qualification of the OutputSupervisor firmware.

## Software evidence summary

Final A12.2 gate: `20260909-output-a12-2-final-full-software-gate-v8`.

- Python software tests PASS: `488 passed`, `3 optional visual skipped`, `9 hardware deselected`;
- host C++: `49/49` PASS;
- ownership invariant: PASS;
- lint/format/schema/pre-push: PASS;
- fake-output firmware: PASS;
- RF-enabled real-output firmware software build: PASS;
- `main_stack=16384`;
- `runtime_frame=32`;
- `text=617445`, `data=154332`, `bss=1356861`;
- `static_dram=1511193`;
- `firmware_bin=771888` bytes;
- `hardware_started=0`.

## Safety boundary

No physical work is authorized at this handoff.

Future authorized Growbox port: `/dev/cu.usbserial-1130`.

Never use `/dev/cu.usbserial-10`.

Thermal and controller safety invariants remain unchanged.

## Local Agent contract

Every task uses:

```json
{
  "agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5",
  "work_branch": "mvp/environment-controller",
  "resources": []
}
```

Terminal `.agent/results/<task-id>.json` evidence is required before reporting PASS.
'''

Path('docs/OUTPUT_SUPERVISOR_A12_SOFTWARE_QUALIFICATION.md').write_text(qualification)
Path('docs/CURRENT_STATUS.md').write_text(current_status)
Path('docs/CONTINUATION_PLAN.md').write_text(continuation)
Path('docs/ARCHITECTURE_HANDOFF.md').write_text(handoff)

run(['git', 'diff', '--check'])
run(['.venv/bin/pre-commit', 'run', '--files',
     'docs/OUTPUT_SUPERVISOR_A12_SOFTWARE_QUALIFICATION.md',
     'docs/CURRENT_STATUS.md', 'docs/CONTINUATION_PLAN.md', 'docs/ARCHITECTURE_HANDOFF.md'])
run(['git', 'add', 'docs/OUTPUT_SUPERVISOR_A12_SOFTWARE_QUALIFICATION.md',
     'docs/CURRENT_STATUS.md', 'docs/CONTINUATION_PLAN.md', 'docs/ARCHITECTURE_HANDOFF.md'])
run(['git', 'commit', '-m', 'Record OutputSupervisor software qualification'])
new_sha = out(['git', 'rev-parse', 'HEAD'])
run(['git', 'push', 'origin', f'HEAD:{BRANCH}'])
run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'FETCH_HEAD']) != new_sha or out(['git', 'status', '--porcelain']):
    raise SystemExit('A12_DOCS_PUSH_VERIFY_FAIL')
print(f'A12_QUALIFICATION_DOCS_PASS executable_sha={BASE} docs_sha={new_sha} hardware_started=0')
