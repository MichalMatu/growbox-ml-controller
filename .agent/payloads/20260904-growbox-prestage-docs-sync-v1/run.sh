#!/usr/bin/env bash
set -euo pipefail
EXPECTED=60da0a4d2a99f3045596b6a8a8bf362a0c6e1aca
BRANCH=mvp/environment-controller

test "$(git rev-parse HEAD)" = "$EXPECTED"
git fetch -q origin "$BRANCH"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
test -z "$(git status --porcelain)"

python3 - <<'PY'
from pathlib import Path

Path('continuation.md').write_text(r'''# Growbox continuation handoff

Date: 2026-09-04
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Control branch: `agent-control`

This is the primary bootstrap for a fresh conversation. Read it first, then verify the fresh work-branch HEAD and `agent-control:.agent/status/daemon.json` before doing work.

## Frozen baseline

Stage27C real-input qualification is complete and remains frozen.

- validated tag: `stage27c-validated-2026-09-03`
- Stage27C closure commit: `b418520090d0feadc005701092c1b7ed3384afbf`
- physically soaked Stage27C firmware: `a5726b89e94b9ac628249b780d6548a692c3fd2c`
- Rule authoritative
- ML shadow-only
- physical outputs remain fake/locked unless a later explicit gate says otherwise

Do not restart Stage27A/B/C without new evidence that later code invalidated them.

## Stage28 status

**Stage28A DONE -> Stage28B DONE -> Stage28C DONE -> pre-Stage28D golden hardening active**

### Stage28A

Native RF433 codec and temporal classification are complete. Milestone: `ac29122cbcf9d155fd08baa0df1014d71f04c135`.

### Stage28B

Native ESP-IDF RMT TX/RX local loopback is complete. Historical Stage28B qualified milestone: `a87169748ee2bd42bc4d35cfe3b2964b90f40eb8`.

### Stage28C

One remote/socket pair is frozen under the neutral hardware label `remote_socket_1`:

- ON: decimal `906118656`, hex `0x36024600`
- OFF: decimal `1040336384`, hex `0x3E024600`
- bit length: `32`
- protocol: `2`
- pulse: `575 us`
- validated transmit repeat: `10`

`repeat=10` is a physically proven reliable TX setting. It is not claimed to be the exact measured repeat count of the original handheld remote.

The final known-pair hardware recheck was performed on source `2cb4b8dffb0835460a9e9ba920d9bd888c99d992` and required exact ON/OFF decode, TX lifecycle completion, RX capture, no RX timeout, `SelfTx` classification and `outputs=fake-locked`. The board was restored to passive RX-only afterwards.

The identity/config freeze commit is `b3e90c92dd39c50c23ed618aba47e9fe8ddf26ec`.

Detailed closure: `docs/STAGE28C_FINAL_EVIDENCE.md`.

## Current RF implementation after golden hardening

Post-Stage28C software hardening has advanced the source beyond the physical recheck SHA without changing the frozen RF identity:

- `a215cae35bbdee155a40fce0c7481a87191a3716` — split real-input runtime responsibilities into Stage27 runtime adapters, telemetry reporter and Stage28 RF diagnostics; `ClimateV6RealInputRuntime.cpp` reduced to orchestration.
- `60da0a4d2a99f3045596b6a8a8bf362a0c6e1aca` — deduplicated the RMT receive path and moved the hardware-qualified receive envelope into a host-testable contract.

Current Stage28C receive contract:

- RMT TX/codec resolution: `100 kHz`
- RMT RX resolution: `100 kHz`
- RX minimum signal / glitch threshold: `10 us` (`10,000 ns`)
- RX maximum signal / idle threshold: `20 ms` (`20,000,000 ns`)
- TX GPIO8, RX GPIO14
- raw RX capacity remains 256 symbols
- a 32-bit protocol-2 frame occupies 33 symbols; seven complete repeats fit, ten complete repeats exceed one raw capture buffer

The 20 ms idle threshold was physically qualified because 300 ms did not terminate one-shot capture reliably in the same receiver environment. Do not revert to the old Stage28B `1 MHz / 1.25 us / 12 ms` settings.

## Evidence boundaries

Keep these distinct:

1. TX request accepted/completed.
2. Local RF receiver captured and decoded the expected frame (`SelfTx`).
3. Real remote socket/load state changed.

Stages 28B/28C prove levels 1 and 2 for the qualified path and record a reliable TX setting. They do not turn local self-RX into physical socket-state acknowledgement.

## Next gate

Before Stage28D semantic integration, finish the pre-stage golden gate:

1. documentation/source consistency;
2. complete host regression and ESP-IDF build;
3. static/format checks available in the repository;
4. bounded real-hardware regression/soak with outputs fake-locked;
5. record one clean checkpoint SHA.

Only after that may Stage28D map the frozen hardware identity to a semantic actuator role. `exhaust_fan` remains the intended first semantic role, but it is not part of Stage28C hardware config.

No unattended mains-load control is authorized by this handoff.

## Local Agent binding

Every task must contain exactly:

`"agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5"`

Use `resources: []` for software-only work and `resources: ["board:growbox-s3"]` for USB/flash/serial/hardware work. Work only on this repository and `mvp/environment-controller` unless the operator explicitly changes scope.
''', encoding='utf-8')

Path('docs/CURRENT_STATUS.md').write_text(r'''# Current controller status

Date: 2026-09-04
Development branch: `mvp/environment-controller`
Primary bootstrap: `/continuation.md`

## Current transition

**Stage28A DONE -> Stage28B DONE -> Stage28C DONE -> pre-Stage28D golden hardening active**

Stage27C remains frozen and is not being reopened.

## Stage28C frozen identity

Neutral hardware label: `remote_socket_1`.

| command | decimal | hex | bits | protocol | pulse | validated TX repeat |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| ON | 906118656 | `0x36024600` | 32 | 2 | 575 us | 10 |
| OFF | 1040336384 | `0x3E024600` | 32 | 2 | 575 us | 10 |

The repeat count above is a physically validated transmit setting, not a claim about the exact repeat count generated by the original handheld remote.

Final known-pair hardware recheck source: `2cb4b8dffb0835460a9e9ba920d9bd888c99d992`.

Identity/config freeze commit: `b3e90c92dd39c50c23ed618aba47e9fe8ddf26ec`.

See `docs/STAGE28C_FINAL_EVIDENCE.md`.

## Current hardened implementation

Current pre-stage source after software hardening:

`60da0a4d2a99f3045596b6a8a8bf362a0c6e1aca`

Notable post-freeze changes:

- `a215cae35bbdee155a40fce0c7481a87191a3716`: real-input runtime orchestration split from Stage27 adapters, telemetry reporting and Stage28 RF diagnostics.
- `60da0a4d2a99f3045596b6a8a8bf362a0c6e1aca`: RMT receive arm/collect path deduplicated; qualified tuning moved to `Rf433RmtTuning.h`; RF host tests lock the receive envelope and frozen socket contract.

Current RF RX contract:

- resolution `100 kHz`;
- minimum signal `10 us`;
- idle/max signal `20 ms`;
- TX GPIO8 / RX GPIO14;
- 256-symbol raw capture capacity.

Do not use the older Stage28B `1 MHz / 1.25 us / 12 ms` receive settings as the current configuration.

## Safety and evidence boundary

Rule remains authoritative and ML remains shadow-only. Physical outputs are still fake/locked for unattended work.

Local `SelfTx` proves the local RF path only; it does not confirm the physical state of a mains socket or load.

## Next work

Finish the golden pre-Stage28D gate: broad regressions, ESP-IDF build, documentation consistency and a bounded hardware soak with no semantic mains actuation. Only then begin Stage28D semantic integration.
''', encoding='utf-8')

Path('docs/CONTINUATION_PLAN.md').write_text(r'''# Fresh-context continuation plan

Updated: 2026-09-04
Work branch: `mvp/environment-controller`
Control branch: `agent-control`

The authoritative handoff is `/continuation.md`.

Current transition:

**Stage28A DONE -> Stage28B DONE -> Stage28C DONE -> pre-Stage28D golden hardening active**

Stage28C has frozen exactly one neutral RF433 remote/socket identity. Detailed evidence is in `docs/STAGE28C_FINAL_EVIDENCE.md`.

Current hardened source at this checkpoint: `60da0a4d2a99f3045596b6a8a8bf362a0c6e1aca`.

Current receive settings are `100 kHz`, `10 us` minimum signal and `20 ms` idle/max signal. Do not reconstruct the active implementation from historical Stage28B receive values.

Before Stage28D, complete one clean golden gate consisting of full software regressions, firmware build, documentation consistency and a bounded real-board soak with outputs fake-locked.

Do not introduce semantic role mapping, unattended 230 V control or physical-state acknowledgement semantics as part of this pre-stage cleanup.
''', encoding='utf-8')

arch = Path('docs/ARCHITECTURE.md')
text = arch.read_text(encoding='utf-8')
anchor = '## Verification layers\n'
section = r'''## Real-input runtime composition and RF433 boundary

The ESP32-S3 real-input application is deliberately split so the top-level runtime remains orchestration rather than a god object:

- `ClimateV6RealInputRuntime.cpp` wires lifecycle and the one-second application tick;
- `runtime/Stage27RuntimeAdapters.*` owns Stage27 physical-source adapters and the locked fake role driver;
- `runtime/Stage27TelemetryReporter.*` owns diagnostic snapshot construction/logging/storage enqueue;
- `runtime/Stage28RfDiagnostics.*` owns passive RF capture and bounded self-loopback diagnostics;
- `rf433/Rf433ProtocolCodec.*` owns portable protocol encode/decode;
- `rf433/Rf433RmtLoopback.*` owns ESP-IDF RMT transport;
- `rf433/Rf433HardwareConfig.h` owns frozen neutral remote/socket identities;
- `rf433/Rf433RmtTuning.h` owns the hardware-qualified receive envelope that host tests lock.

The current qualified RX envelope is 100 kHz resolution, 10 us minimum signal and 20 ms idle/max signal. Hardware identity remains below semantic role mapping. A local `SelfTx` classification is transport evidence, not physical socket-state acknowledgement.

'''
if section not in text:
    if anchor not in text:
        raise SystemExit('ARCHITECTURE verification anchor missing')
    text = text.replace(anchor, section + anchor, 1)
arch.write_text(text, encoding='utf-8')

evidence = Path('docs/STAGE28C_FINAL_EVIDENCE.md')
et = evidence.read_text(encoding='utf-8')
append = r'''

## Post-freeze golden hardening

The physical known-pair recheck evidence above remains tied to source `2cb4b8dffb0835460a9e9ba920d9bd888c99d992`; later software-only refactors must not rewrite that historical fact.

After the identity freeze, the implementation was cleaned up without changing the frozen pair:

- `a215cae35bbdee155a40fce0c7481a87191a3716` split real-input runtime responsibilities into dedicated Stage27 adapter, telemetry reporter and Stage28 RF diagnostic components.
- `60da0a4d2a99f3045596b6a8a8bf362a0c6e1aca` deduplicated RMT receive arm/collect logic and moved the hardware-qualified receive contract into `Rf433RmtTuning.h` so host tests can guard it.

The current guarded receive contract is `100 kHz`, `10 us` minimum signal and `20 ms` idle/max signal. The RF protocol host suite also locks the neutral label, exact ON/OFF identities and the distinction between a reliable TX repeat setting and the unknown exact handheld repeat count.
'''
if '## Post-freeze golden hardening' not in et:
    evidence.write_text(et.rstrip() + append + '\n', encoding='utf-8')

readme = Path('README.md')
rt = readme.read_text(encoding='utf-8')
needle = '> **Current controller status:** climate-v6 runtime work continues on `mvp/environment-controller`. Rule is authoritative, ML is shadow/research-only, and the hardware-neutral I/O seam is now being integrated. See [docs/CURRENT_STATUS.md](docs/CURRENT_STATUS.md).'
replacement = '> **Current controller status:** Stage28C has frozen one neutral RF433 remote/socket pair and the branch is in a pre-Stage28D golden-hardening gate. Rule is authoritative, ML is shadow/research-only, and physical outputs remain fake/locked for unattended work. See [docs/CURRENT_STATUS.md](docs/CURRENT_STATUS.md) and [docs/STAGE28C_FINAL_EVIDENCE.md](docs/STAGE28C_FINAL_EVIDENCE.md).'
if needle in rt:
    rt = rt.replace(needle, replacement, 1)
readme.write_text(rt, encoding='utf-8')
PY

git diff --check

# Active handoff/status docs must no longer advertise Stage28C as next or the old
# Stage28B receive envelope as current.
if grep -nE 'Stage28C: NEXT|Stage28C NEXT|Stage28C is the exact next|Stage28C: NEXT' continuation.md docs/CURRENT_STATUS.md docs/CONTINUATION_PLAN.md; then
  echo 'stale Stage28C NEXT text remains' >&2
  exit 1
fi
if grep -nE 'RX resolution `1 MHz`|RX minimum signal/glitch filter `1,250 ns`|RX maximum signal/idle threshold `12 ms`' continuation.md docs/CURRENT_STATUS.md docs/CONTINUATION_PLAN.md; then
  echo 'stale current RX envelope remains' >&2
  exit 1
fi

grep -q '60da0a4d2a99f3045596b6a8a8bf362a0c6e1aca' continuation.md
grep -q 'Stage28C DONE' docs/CURRENT_STATUS.md
grep -q 'Rf433RmtTuning.h' docs/ARCHITECTURE.md
grep -q 'Post-freeze golden hardening' docs/STAGE28C_FINAL_EVIDENCE.md

git add continuation.md README.md docs/CURRENT_STATUS.md docs/CONTINUATION_PLAN.md docs/ARCHITECTURE.md docs/STAGE28C_FINAL_EVIDENCE.md
git commit -m "Synchronize Stage28C golden handoff documentation"
git push origin HEAD:"$BRANCH"
NEW=$(git rev-parse HEAD)
test "$(git rev-parse origin/$BRANCH)" = "$NEW"
test -z "$(git status --porcelain)"
printf 'PRESTAGE_DOCS_SYNC_READY commit=%s source_before_docs=%s\n' "$NEW" "$EXPECTED"
