from pathlib import Path

QUALIFIED_SHA = "02208d23f403bca3540dbbd652eb55703a044833"
TOOLING_SHA = "2a19cd43646fe284a7ab41828178b2b8f17edea1"
H_TASK = "20260910-output-supervisor-physical-h-v3"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"{label}: expected exactly one anchor, found {text.count(old)}")
    return text.replace(old, new, 1)


qualification = Path("docs/STAGE28E_OUTPUT_SUPERVISOR_H_QUALIFICATION.md")
text = qualification.read_text()
text = replace_once(text, "Status: A13.1 SOFTWARE CONTRACT", "Status: PHYSICAL H PASS", "qualification status")
anchor = "Hardware authorization: GRANTED by operator on 2026-09-10\n"
addition = f"""Hardware authorization: GRANTED by operator on 2026-09-10
Terminal physical H evidence: `{H_TASK}` PASS
Physical H tooling SHA: `{TOOLING_SHA}`

### Terminal physical H result

The authorized bounded hardware qualification passed on 2026-09-10 against exact production identity `{QUALIFIED_SHA}`.

Observed terminal evidence:

- startup recovery reached `Automatic` with `safety_latched=0` at uptime `630113 ms`;
- active SD session `3F6B0A11.JL` matched `growbox-log-v3` and output telemetry v2;
- clean natural fan-OFF baseline began at uptime `651463 ms`;
- natural `Climate` / `ClimateDecision` fan ON was captured at uptime `884293 ms` with requested level `0.111`;
- the active trigger was humidity (`AH gap 2.513 g/m3` at transition); temperature trigger was not counted;
- Shelly RPC produced exactly eight pre and eight post samples with median power `22.0 W -> 24.8 W`, delta `+2.8 W`;
- the humidity environmental gradient contracted by `0.381 g/m3`, exceeding the frozen `0.30 g/m3` threshold;
- formal OutputSupervisor replay passed for the exact qualified SHA;
- no raw RF command path was used and `/dev/cu.usbserial-10` remained untouched;
- final supervisor-owned `automation off` reached `Disabled` with fan OFF, humidifier OFF and transport clean.

Terminal marker:

`OUTPUT_SUPERVISOR_H_PHYSICAL_PASS sha={QUALIFIED_SHA} tooling_sha={TOOLING_SHA} port=/dev/cu.usbserial-1130 shelly=192.168.0.16 raw_rf=0 forbidden_port_untouched=/dev/cu.usbserial-10 hardware_started=1`
"""
text = replace_once(text, anchor, addition, "qualification evidence insertion")
text = replace_once(
    text,
    "The future bounded hardware observer must collect independent evidence around the counted fan transition.",
    "The successful bounded hardware observer collected independent evidence around the counted fan transition.",
    "qualification observer tense",
)
text = replace_once(
    text,
    "The eventual physical H task must make recovery/final-state execution supervisor-owned.",
    "The successful physical H task made recovery/final-state execution supervisor-owned.",
    "qualification recovery tense",
)
qualification.write_text(text)

status = Path("docs/CURRENT_STATUS.md")
text = status.read_text()
text = replace_once(
    text,
    "**Stage27C FROZEN -> Stage28E A-G COMPLETE -> OUTPUT EXECUTION ARCHITECTURE A1-A12 COMPLETE -> A13 QUALIFICATION CONTRACT ACTIVE**",
    "**Stage27C FROZEN -> Stage28E A-G COMPLETE -> OUTPUT EXECUTION ARCHITECTURE A1-A12 COMPLETE -> A13 + PHYSICAL H COMPLETE**",
    "current status transition",
)
text = replace_once(
    text,
    "The OutputSupervisor architecture has completed its final software qualification. The old H v8 path remains historical and must not be executed.",
    "The OutputSupervisor architecture has completed its final software qualification and the authorized physical Phase H qualification. The old H v8 path remains historical and must not be executed.",
    "current status intro",
)
start = text.index("## Phase H state\n")
end = text.index("## Hardware boundary\n")
phase_h = f"""## Phase H state

Phase H is **PASS** for exact production identity `{QUALIFIED_SHA}` with tooling identity `{TOOLING_SHA}`.

Terminal Local Agent evidence: `{H_TASK}`.

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
- formal OutputSupervisor replay PASS on `{QUALIFIED_SHA}`;
- final supervisor-owned `automation off` reached `Disabled`, fan OFF, humidifier OFF, transport clean;
- `raw_rf=0`; `/dev/cu.usbserial-10` remained untouched.

One-way RF transport completion is still not treated as physical acknowledgement; Shelly and the environmental response remain independent supporting evidence.

"""
text = text[:start] + phase_h + text[end:]
start = text.index("## Hardware boundary\n")
end = text.index("## Local Agent execution identity\n")
hardware = """## Hardware boundary

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

"""
text = text[:start] + hardware + text[end:]
start = text.index("## Immediate next work\n")
text = text[:start] + """## Immediate next work

Phase H is complete. No further Phase H execution is required unless production source changes or a new hardware qualification target is intentionally introduced.

Preserve the terminal evidence above and the historical failed-safe attempts; do not rerun historical H v8.
"""
status.write_text(text)

handoff = Path("docs/ARCHITECTURE_HANDOFF.md")
text = handoff.read_text()
text = replace_once(
    text,
    "The OutputSupervisor migration is software-stabilized through A12.2.",
    "The OutputSupervisor migration is software-stabilized through A12.2 and the authorized physical Phase H qualification is PASS.",
    "handoff current state",
)
insert_anchor = "The current branch may contain later documentation/tooling commits. Those later commits do not replace the exact A12-qualified executable identity unless production source is changed and requalified.\n\n"
insert = f"""The current branch may contain later documentation/tooling commits. Those later commits do not replace the exact A12-qualified executable identity unless production source is changed and requalified.

### Physical H terminal evidence

Terminal Local Agent task `{H_TASK}` passed against production SHA `{QUALIFIED_SHA}` and tooling SHA `{TOOLING_SHA}`.

It proved a natural humidity-driven `ClimateDecision` fan OFF->ON transition, Shelly power delta `+2.8 W` (`22.0 W -> 24.8 W`, 8 + 8 samples), absolute-humidity gradient contraction `0.381 g/m3`, formal OutputSupervisor replay PASS, and supervisor-owned final `Disabled` state with fan/humidifier OFF and clean transport. No raw RF command path was used; `/dev/cu.usbserial-10` remained untouched.

"""
text = replace_once(text, insert_anchor, insert, "handoff physical H insertion")
text = replace_once(
    text,
    "A13.1 retargeting is the active task after the hardware preflight exposed and software requalification fixed the startup partial-command-truth defect. The H contract itself remains unchanged in ownership semantics and must not reuse the historical H v8 observer as-is.",
    "A13.1 retargeting and the sampling-robust replay update are complete. The physical H run is also complete; the H contract remains unchanged in ownership semantics and the historical H v8 observer must not be reused.",
    "handoff A13.1 state",
)
text = replace_once(
    text,
    "After A13.1 is committed, run a new software-only preflight against the exact A12-qualified executable identity and the new H tooling.",
    "A13.2 software-only preflight completed successfully against the exact A12-qualified executable identity and the final H tooling before hardware execution.",
    "handoff A13.2 state",
)
start = text.index("## Hardware gate after A13.2\n")
end = text.index("## Safety invariants\n")
hardware_result = f"""## Hardware qualification result

The operator-authorized bounded hardware qualification completed successfully on 2026-09-10 after A13.2 PASS.

Qualified hardware path:

`/dev/cu.usbserial-1130`

Never touch:

`/dev/cu.usbserial-10`

Terminal evidence is `{H_TASK}`. The final run preserved all safety invariants, used only high-level supervisor-owned automation lifecycle commands, used no raw RF path, and restored/proved the safe final state.

Any future production-source change invalidates the current executable qualification and requires A12/A13 requalification before a new hardware claim.

"""
text = text[:start] + hardware_result + text[end:]
handoff.write_text(text)

print(f"H_DOCS_PATCH_READY qualified_sha={QUALIFIED_SHA} tooling_sha={TOOLING_SHA} source_task={H_TASK}")
