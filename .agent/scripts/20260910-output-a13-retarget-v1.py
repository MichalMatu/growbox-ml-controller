from pathlib import Path
import subprocess

OLD = "1c59f3cfa239abbfbae721247d01d65a39d4bdfc"
NEW = "02208d23f403bca3540dbbd652eb55703a044833"


def replace_exact(path: str, old: str, new: str, expected: int | None = None) -> None:
    file_path = Path(path)
    text = file_path.read_text()
    count = text.count(old)
    if expected is not None and count != expected:
        raise SystemExit(f"A13_RETARGET_FAIL path={path} expected_count={expected} actual_count={count} token={old!r}")
    if count == 0:
        raise SystemExit(f"A13_RETARGET_FAIL path={path} missing={old!r}")
    file_path.write_text(text.replace(old, new))


head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
if head != NEW:
    raise SystemExit(f"A13_RETARGET_FAIL head={head} expected={NEW}")
if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
    raise SystemExit("A13_RETARGET_FAIL dirty worktree")

replace_exact("tools/output_supervisor_h.py", OLD, NEW, 1)

replace_exact("docs/STAGE28E_OUTPUT_SUPERVISOR_H_QUALIFICATION.md", "Updated: 2026-09-09", "Updated: 2026-09-10", 1)
replace_exact("docs/STAGE28E_OUTPUT_SUPERVISOR_H_QUALIFICATION.md", OLD, NEW)
replace_exact(
    "docs/STAGE28E_OUTPUT_SUPERVISOR_H_QUALIFICATION.md",
    "`20260909-output-a12-2-final-full-software-gate-v8`",
    "`20260910-output-a12-2-final-full-software-gate-v9`",
    1,
)
replace_exact(
    "docs/STAGE28E_OUTPUT_SUPERVISOR_H_QUALIFICATION.md",
    "Hardware authorization: NOT GRANTED",
    "Hardware authorization: GRANTED by operator on 2026-09-10",
    1,
)
replace_exact(
    "docs/STAGE28E_OUTPUT_SUPERVISOR_H_QUALIFICATION.md",
    "- at least three stable power samples exist before the counted transition;\n- at least three power samples exist after the counted transition;\n- lamp state does not change across the proof window;\n- humidifier state does not change across the proof window;\n- post-transition median power minus pre-transition median power meets a reviewed positive minimum threshold.\n\nThe threshold is an explicit qualification parameter, not a hidden constant. It must be reviewed before hardware authorization.",
    "- exactly eight stable power samples are collected before the counted transition at 2 s cadence;\n- exactly eight power samples are collected after the counted transition at 2 s cadence;\n- lamp state does not change across the proof window;\n- humidifier state does not change across the proof window;\n- post-transition median power minus pre-transition median power is at least `+1.0 W`.\n\nThe `+1.0 W` minimum delta is frozen for the authorized hardware qualification and must not be weakened during execution.",
    1,
)
replace_exact(
    "docs/STAGE28E_OUTPUT_SUPERVISOR_H_QUALIFICATION.md",
    "A bounded post-transition environmental window must provide supporting evidence consistent with increased exhaust airflow. The exact acceptance metric/window must be frozen before the hardware task is authorized and must not weaken thermal safety.\n\nEnvironmental response is supporting physical evidence, not a substitute for the supervisor/transport telemetry chain.",
    "The authorized hardware qualification uses a 180 s pre-transition observation, ignores the first 30 s after the counted fan ON transition, and observes the post-transition response for up to 600 s. Supporting environmental response is accepted when the active trigger's gradient measurably contracts: for a temperature-driven transition, median `|TP357_T - Xiaomi_T|` decreases by at least `0.20 C`; for a humidity-driven transition, the inside-minus-outside absolute-humidity gap decreases by at least `0.30 g/m3`. If both triggers are active, satisfying either actually active mechanism is sufficient.\n\nThe operator thermal guard is `27.5 C`; the firmware hard-safety policy remains authoritative. Environmental response is supporting physical evidence, not a substitute for the supervisor/transport telemetry chain.",
    1,
)
replace_exact(
    "docs/STAGE28E_OUTPUT_SUPERVISOR_H_QUALIFICATION.md",
    "## 10. Mandatory stop\n\nAfter A13.2 PASS, stop and wait for explicit operator authorization.\n\nDo not tell the operator to connect the ESP32 before that explicit authorization step.\n\nWhen hardware is later explicitly authorized, only this Growbox serial port may be used:",
    "## 10. Hardware authorization gate\n\nThe operator explicitly authorized physical qualification on 2026-09-10. That authorization remains subordinate to software qualification: after any production-source change, hardware must stop until the replacement executable passes A12.2 and the retargeted A13.1/A13.2 gates.\n\nFor the currently authorized hardware qualification, only this Growbox serial port may be used:",
    1,
)

replace_exact("docs/CURRENT_STATUS.md", "Updated: 2026-09-09", "Updated: 2026-09-10", 1)
replace_exact("docs/CURRENT_STATUS.md", OLD, NEW)
replace_exact("docs/CURRENT_STATUS.md", "`20260909-output-a12-2-final-full-software-gate-v8`", "`20260910-output-a12-2-final-full-software-gate-v9`", 1)
replace_exact("docs/CURRENT_STATUS.md", "firmware binary: `771888` bytes", "firmware binary: `771920` bytes", 1)
replace_exact("docs/CURRENT_STATUS.md", "text: `617445` bytes", "text: `617469` bytes", 1)
replace_exact(
    "docs/CURRENT_STATUS.md",
    "Phase H is **not PASS** and hardware qualification has **not started** for the OutputSupervisor architecture.",
    "Phase H is **not PASS**. An authorized hardware preflight started, failed safe in `FaultLocked`, and exposed a startup partial-command-truth defect that is now fixed and requalified in software.",
    1,
)
replace_exact(
    "docs/CURRENT_STATUS.md",
    "The next authorized sequence is:\n\n1. A13.1 — define a new OutputSupervisor H qualification contract and observer/tooling against telemetry v2;\n2. A13.2 — run a software-only H preflight for the exact A12-qualified identity with `hardware_started=0`;\n3. A13.3 — mandatory stop for explicit operator authorization before any hardware access.",
    "The next sequence is:\n\n1. retarget A13.1 tooling/docs to the replacement A12-qualified SHA;\n2. rerun A13.2 software-only preflight with `hardware_started=0`;\n3. rerun the bounded hardware preflight on `/dev/cu.usbserial-1130`;\n4. only after that PASS, execute the natural Climate -> OutputSupervisor physical H proof.",
    1,
)
replace_exact(
    "docs/CURRENT_STATUS.md",
    "Until A13.2 passes and the operator explicitly authorizes hardware qualification:",
    "Operator hardware authorization was granted on 2026-09-10. Because production source changed after the first physical preflight, no further hardware access is allowed until the replacement A13.2 software preflight passes:",
    1,
)

replace_exact("docs/ARCHITECTURE_HANDOFF.md", "Updated: 2026-09-09", "Updated: 2026-09-10", 1)
replace_exact("docs/ARCHITECTURE_HANDOFF.md", OLD, NEW)
replace_exact("docs/ARCHITECTURE_HANDOFF.md", "`20260909-output-a12-2-final-full-software-gate-v8`", "`20260910-output-a12-2-final-full-software-gate-v9`", 1)
replace_exact("docs/ARCHITECTURE_HANDOFF.md", "`firmware_bin=771888`", "`firmware_bin=771920`", 1)
replace_exact(
    "docs/ARCHITECTURE_HANDOFF.md",
    "A13.1 is the active task.\n\nCreate a new qualification plan/tool contract for the A12-qualified identity. It must not reuse the historical H v8 observer as-is.",
    "A13.1 retargeting is the active task after the hardware preflight exposed and software requalification fixed the startup partial-command-truth defect. The H contract itself remains unchanged in ownership semantics and must not reuse the historical H v8 observer as-is.",
    1,
)
replace_exact(
    "docs/ARCHITECTURE_HANDOFF.md",
    "## Mandatory stop after A13.2\n\nAfter A13.2 PASS, stop before hardware.\n\nDo not begin physical H until the operator explicitly authorizes it.\n\nOnly after that explicit authorization may a future hardware task use:",
    "## Hardware gate after A13.2\n\nThe operator explicitly authorized hardware qualification on 2026-09-10. Because production source changed after the initial hardware preflight, that authorization may be exercised again only after the replacement executable passes the retargeted A13.2 software preflight.\n\nOnly then may the bounded hardware task use:",
    1,
)

subprocess.run(["git", "diff", "--check"], check=True)
print(f"A13_RETARGET_EDIT_PASS qualified_sha={NEW} hardware_started=0", flush=True)
