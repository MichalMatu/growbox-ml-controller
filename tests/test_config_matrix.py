"""CONFIG_MATRIX.csv consistency and host harness smoke."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.ml.config_matrix import (
    OUTPUTS,
    build_controller_input,
    load_matrix_rows,
    matrix_cases,
    write_replay_scripts,
)
from tools.ml.contract import load_contract
from tools.ml.run_config_matrix import apply_safety_python
from tools.ml.run_config_matrix import test_profile as run_matrix_profile

MATRIX_DOC = Path(__file__).resolve().parents[1] / "docs" / "CONFIG_MATRIX.md"


def _doc_profile_ids() -> set[str]:
    ids: set[str] = set()
    for line in MATRIX_DOC.read_text(encoding="utf-8").splitlines():
        if line.startswith("| `"):
            ids.add(line.split("|")[1].strip().strip("`"))
    return ids


def test_matrix_file_exists_and_matches_doc():
    rows = load_matrix_rows()
    assert len(rows) == 59
    assert {row["id"] for row in rows} == _doc_profile_ids()


@pytest.mark.parametrize("profile_id", [row["id"] for row in load_matrix_rows()])
def test_each_matrix_profile_passes_host_harness(profile_id: str):
    contract = load_contract()
    row = next(row for row in load_matrix_rows() if row["id"] == profile_id)
    ok, reason = run_matrix_profile(row, contract)
    assert ok, reason


def test_safety_intent_profiles_list_forced_zeros():
    contract = load_contract()
    checks = {
        "P09": "co2_doser",
        "P10": "irrigation_pot_1",
        "P11": "nutrient_heater",
        "P12": "heater",
        "P20": "heater",
    }
    rows = {row["id"]: row for row in load_matrix_rows()}
    for profile_id, output_name in checks.items():
        row = rows[profile_id]
        expected = {
            part.strip() for part in row["expected_safe_zero_outputs"].split(",") if part.strip()
        }
        assert output_name in expected
        record = build_controller_input(row, contract)
        safe = apply_safety_python(record, {name: 1.0 for name in expected})
        assert safe[output_name] == 0.0


def test_co2_doser_not_target_blocked_when_available():
    contract = load_contract()
    for profile_id in ("P04", "P06", "A_OFF_heater"):
        row = next(row for row in load_matrix_rows() if row["id"] == profile_id)
        if row["avail_co2_doser"].lower() != "true" or row["valid_co2_ppm"].lower() != "true":
            continue
        record = build_controller_input(row, contract)
        assert record["sensors"]["co2_ppm"] < record["targets"]["co2_ppm"]
        raw = {name: 1.0 for name in OUTPUTS}
        safe = apply_safety_python(record, raw)
        assert safe["co2_doser"] > 0.0


def test_write_replay_scripts_bundle(tmp_path: Path):
    out_dir = tmp_path / "replay"
    written = write_replay_scripts(out_dir)
    assert len(written) == 60  # 59 profiles + manifest
    assert (out_dir / "manifest.json").exists()
    assert (out_dir / "P01.jsonl").exists()
    cases = matrix_cases()
    assert len(cases) == 59
