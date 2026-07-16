"""Exhaustive on-device audit: CONFIG_MATRIX × sensor grid × previous grid.

For each of the 59 CONFIG_MATRIX profiles, runs the full cartesian product of:
  - every valid sensor at 3 contract points (min / default / max),
  - every active pot sensor at 3 points,
  - every available global actuator previous at {0, 1},
  - every active pot irrigation/heat_mat previous at {0, 1},
  - plus sensor×previous combined (full cross within profile).

59 profiles = complete discrete I/O catalog (not 2^43, but curated full coverage).

Checkpoint/resume: build/audit/exhaustive_checkpoint.jsonl
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
import time
from collections.abc import Iterator
from dataclasses import asdict
from datetime import UTC, datetime
from itertools import product
from pathlib import Path
from typing import Any

from tools.ml.board_engine_audit import (
    BoardSession,
    Finding,
    evaluate_decision,
    load_scenario_command,
    summarize,
)
from tools.ml.config_matrix import (
    DEFAULT_MATRIX,
    GLOBAL_ACTUATORS,
    GLOBAL_SENSORS,
    build_controller_input,
    csv_list,
    load_matrix_rows,
)
from tools.ml.contract import load_contract
from tools.ml.run_config_matrix import continuous_points, feature_by_path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT = PROJECT_ROOT / "build" / "audit" / "exhaustive_board_audit.json"
DEFAULT_CHECKPOINT = PROJECT_ROOT / "build" / "audit" / "exhaustive_checkpoint.jsonl"

PREV_LEVELS = (0.0, 1.0)


def _set_path(scenario: dict[str, Any], path: str, value: float) -> None:
    parts = path.split(".")
    if parts[0] == "pots":
        node: Any = scenario["pots"][int(parts[1])]
        for part in parts[2:-1]:
            node = node[part]
        node[parts[-1]] = value
        return
    node = scenario
    for part in parts[:-1]:
        node = node[part]
    node[parts[-1]] = value


def _sensor_paths(scenario: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    validity = scenario.get("validity") or {}
    for sensor in GLOBAL_SENSORS:
        if validity.get(sensor):
            paths.append(f"sensors.{sensor}")
    for index, pot in enumerate(scenario.get("pots") or []):
        if not pot.get("available"):
            continue
        pot_validity = pot.get("validity") or {}
        for sensor in ("soil_moisture_pct", "soil_temperature_c"):
            if pot_validity.get(sensor):
                paths.append(f"pots.{index}.sensors.{sensor}")
    return paths


def _previous_axes(scenario: dict[str, Any]) -> list[tuple[str, int | None, str]]:
    axes: list[tuple[str, int | None, str]] = []
    actuators = scenario.get("actuators") or {}
    for name in GLOBAL_ACTUATORS:
        if (actuators.get(name) or {}).get("available"):
            axes.append(("global", None, name))
    for index, pot in enumerate(scenario.get("pots") or []):
        if not pot.get("available"):
            continue
        if (pot.get("irrigation") or {}).get("available"):
            axes.append(("pot", index, "irrigation"))
        if (pot.get("heat_mat") or {}).get("available"):
            axes.append(("pot", index, "heat_mat"))
    return axes


def _grid_for_path(contract, path: str) -> list[float]:
    feature = feature_by_path(contract, path)
    if feature is None:
        return [0.0]
    if feature.encoding is not None:
        return [float(feature.default)]
    return continuous_points(feature)


def count_profile_cases(row: dict[str, str], contract) -> int:
    base = build_controller_input(row, contract)
    sensor_paths = _sensor_paths(base)
    prev_axes = _previous_axes(base)
    n_sensor = (
        math.prod(len(_grid_for_path(contract, path)) for path in sensor_paths)
        if sensor_paths
        else 0
    )
    n_prev = (len(PREV_LEVELS) ** len(prev_axes)) if prev_axes else 0
    total = 1
    if sensor_paths:
        total += n_sensor
    if prev_axes:
        total += n_prev
    if sensor_paths and prev_axes:
        total += n_sensor * n_prev
    return total


def iter_profile_cases(
    row: dict[str, str],
    contract,
) -> Iterator[tuple[str, dict[str, Any], list[str]]]:
    base = build_controller_input(row, contract)
    expected = csv_list(row.get("expected_safe_zero_outputs", ""))
    profile_id = row["id"]

    yield (f"{profile_id}/base", copy.deepcopy(base), expected)

    sensor_paths = _sensor_paths(base)
    sensor_grids = [_grid_for_path(contract, path) for path in sensor_paths]
    prev_axes = _previous_axes(base)

    if sensor_paths:
        for combo in product(*sensor_grids):
            scenario = copy.deepcopy(base)
            tag_parts: list[str] = []
            for path, value in zip(sensor_paths, combo, strict=True):
                _set_path(scenario, path, float(value))
                short = path.replace("sensors.", "").replace(".", "_")
                tag_parts.append(f"{short}={value:g}")
            yield (f"{profile_id}/S[{'|'.join(tag_parts)}]", scenario, expected)

    if prev_axes:
        for combo in product(*([PREV_LEVELS] * len(prev_axes))):
            scenario = copy.deepcopy(base)
            tag_parts = []
            for (kind, pot_index, field), value in zip(prev_axes, combo, strict=True):
                if kind == "global":
                    scenario["previous"][field] = float(value)
                    tag_parts.append(f"p_{field}={int(value)}")
                else:
                    scenario["pots"][pot_index]["previous"][field] = float(value)
                    tag_parts.append(f"p{pot_index + 1}_{field}={int(value)}")
            yield (f"{profile_id}/P[{'|'.join(tag_parts)}]", scenario, expected)

    if sensor_paths and prev_axes:
        for s_combo in product(*sensor_grids):
            for p_combo in product(*([PREV_LEVELS] * len(prev_axes))):
                scenario = copy.deepcopy(base)
                s_tag: list[str] = []
                for path, value in zip(sensor_paths, s_combo, strict=True):
                    _set_path(scenario, path, float(value))
                    s_tag.append(f"{path.split('.')[-1]}={value:g}")
                p_tag: list[str] = []
                for (kind, pot_index, field), value in zip(prev_axes, p_combo, strict=True):
                    if kind == "global":
                        scenario["previous"][field] = float(value)
                        p_tag.append(f"{field}={int(value)}")
                    else:
                        scenario["pots"][pot_index]["previous"][field] = float(value)
                        p_tag.append(f"pot{pot_index + 1}_{field}={int(value)}")
                yield (
                    f"{profile_id}/X[S:{'+'.join(s_tag)}][P:{'+'.join(p_tag)}]",
                    scenario,
                    expected,
                )


def iter_all_cases(
    rows: list[dict[str, str]],
    contract,
    *,
    skip_heavy_over: int | None = None,
) -> Iterator[tuple[str, dict[str, Any], list[str]]]:
    for row in rows:
        count = count_profile_cases(row, contract)
        if skip_heavy_over is not None and count > skip_heavy_over:
            continue
        yield from iter_profile_cases(row, contract)


def _load_done(checkpoint: Path) -> set[str]:
    if not checkpoint.is_file():
        return set()
    done: set[str] = set()
    for line in checkpoint.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("status") == "ok":
            done.add(str(record["case"]))
    return done


def _append_checkpoint(checkpoint: Path, record: dict[str, Any]) -> None:
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    with checkpoint.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, separators=(",", ":")) + "\n")


def run_case(
    session: BoardSession,
    case_id: str,
    scenario: dict[str, Any],
    expected_safe_zeros: list[str],
) -> list[Finding]:
    session.send({"command": "pause"}, expect="ack", expect_cmd="pause")
    session.send({"command": "mode", "value": "replay"}, expect="ack", expect_cmd="mode")
    session.send(load_scenario_command(scenario), expect="ack", expect_cmd="load_scenario")
    decision = session.send({"command": "step"}, expect="decision")
    return evaluate_decision(case_id, scenario, decision, expected_safe_zeros=expected_safe_zeros)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--port", default="/dev/cu.usbmodem1101")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--skip-heavy-over",
        type=int,
        default=None,
        help="Skip profiles with more than N cartesian cases",
    )
    parser.add_argument("--max-cases", type=int, default=None)
    args = parser.parse_args(argv)

    if not args.matrix.is_file():
        print(f"matrix missing: {args.matrix}", file=sys.stderr)
        return 2

    contract = load_contract()
    rows = load_matrix_rows(args.matrix)
    plan = [{"id": row["id"], "cases": count_profile_cases(row, contract)} for row in rows]
    total = sum(row["cases"] for row in plan)
    runnable = sum(
        row["cases"]
        for row in plan
        if args.skip_heavy_over is None or row["cases"] <= args.skip_heavy_over
    )
    print(f"CONFIG_MATRIX profiles: {len(plan)}")
    print(f"cartesian cases total (all profiles): {total}")
    print(f"cartesian cases runnable: {runnable}")
    for row in sorted(plan, key=lambda r: -r["cases"])[:20]:
        flag = " SKIP" if args.skip_heavy_over and row["cases"] > args.skip_heavy_over else ""
        print(f"  {row['id']}: {row['cases']}{flag}")

    if args.dry_run:
        return 0

    if not Path(args.port).exists():
        print(f"board port missing: {args.port}", file=sys.stderr)
        return 2

    done = _load_done(args.checkpoint)
    case_iter = iter_all_cases(rows, contract, skip_heavy_over=args.skip_heavy_over)

    all_findings: list[Finding] = []
    case_rows: list[dict[str, Any]] = []
    ran = 0
    skipped_done = 0

    with BoardSession(args.port, timeout=args.timeout) as session:
        for case_id, scenario, expected in case_iter:
            if case_id in done:
                skipped_done += 1
                continue
            if args.max_cases is not None and ran >= args.max_cases:
                print(f"stopped at --max-cases={args.max_cases}", flush=True)
                break
            t0 = time.monotonic()
            try:
                findings = run_case(session, case_id, scenario, expected)
                status = "ok" if not any(f.severity == "error" for f in findings) else "fail"
            except Exception as exc:  # noqa: BLE001
                findings = [Finding("error", case_id, "session_exception", str(exc))]
                status = "error"
            errs = [f for f in findings if f.severity == "error"]
            warns = [f for f in findings if f.severity == "warn"]
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            _append_checkpoint(
                args.checkpoint,
                {
                    "case": case_id,
                    "status": status,
                    "errors": len(errs),
                    "warns": len(warns),
                    "elapsed_ms": elapsed_ms,
                    "ts": datetime.now(UTC).isoformat(),
                },
            )
            all_findings.extend(findings)
            if errs or warns:
                case_rows.append(
                    {
                        "case": case_id,
                        "errors": [asdict(f) for f in errs],
                        "warns": [asdict(f) for f in warns],
                    }
                )
            ran += 1
            if ran % 50 == 0 or errs:
                print(
                    f"  [{ran}] {case_id} e={len(errs)} w={len(warns)} {elapsed_ms}ms",
                    flush=True,
                )

    summary = summarize(all_findings)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "port": args.port,
        "matrix": str(args.matrix),
        "planned_runnable": runnable,
        "executed_cases": ran,
        "skipped_already_done": skipped_done,
        "checkpoint": str(args.checkpoint),
        "summary": summary,
        "failures": case_rows,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"executed={ran} report={args.report}")
    return 1 if summary["error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
