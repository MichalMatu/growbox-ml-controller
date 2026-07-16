from __future__ import annotations

import json
from copy import deepcopy

from tools.ml.contract import ACTIVE_CONTRACT_PATH, load_contract
from tools.ml.export_model import (
    DEFAULT_GENERATED_DIR,
    DEFAULT_GOLDEN_HEADER,
    DEFAULT_GOLDEN_JSON,
    render_golden_header,
)
from tools.ml.pipeline import (
    GOLDEN_EXPECTED_ATOL,
    GOLDEN_FEATURE_ATOL,
    _golden_mismatches,
)
from tools.ml.verify_export import verify_export


def test_committed_export_metadata_matches_contract():
    contract = load_contract(ACTIVE_CONTRACT_PATH)
    model_header = (DEFAULT_GENERATED_DIR / "EnvironmentModel.h").read_text(encoding="utf-8")
    manifest = (DEFAULT_GENERATED_DIR / "ModelManifest.h").read_text(encoding="utf-8")
    golden = json.loads(DEFAULT_GOLDEN_JSON.read_text(encoding="utf-8"))
    assert f'kSchemaHash[] = "{contract.short_hash}"' in model_header
    assert f'kSchemaHash[] = "{contract.short_hash}"' in manifest
    assert golden["schema_hash"] == contract.short_hash
    assert tuple(golden["feature_order"]) == contract.feature_names
    assert tuple(golden["output_order"]) == contract.outputs
    assert "eml_net_regress" in model_header
    assert "generated_model::" not in model_header  # declaration is a namespace member
    assert "inline bool infer(const float* features, float* outputs)" in model_header


def test_python_predictions_match_compiled_emlearn_c():
    result = verify_export()
    assert result.vector_count == 3
    assert result.max_abs_error <= result.tolerance


def test_cpp_fixture_is_the_json_fixture():
    golden = json.loads(DEFAULT_GOLDEN_JSON.read_text(encoding="utf-8"))
    header = DEFAULT_GOLDEN_HEADER.read_text(encoding="utf-8")
    assert header == render_golden_header(golden)
    assert f"kVectorCount = {len(golden['vectors'])}U" in header
    assert golden["model_version"] in header
    assert golden["schema_hash"] in header


def test_golden_reproducibility_allows_only_bounded_float_noise():
    committed = json.loads(DEFAULT_GOLDEN_JSON.read_text(encoding="utf-8"))
    close = deepcopy(committed)
    close["vectors"][0]["features"][0] += GOLDEN_FEATURE_ATOL * 0.5
    close["vectors"][0]["expected"][0] += GOLDEN_EXPECTED_ATOL * 0.5
    assert _golden_mismatches(close, committed) == []

    stale = deepcopy(committed)
    stale["vectors"][0]["expected"][0] += GOLDEN_EXPECTED_ATOL * 2.0
    assert "golden-vector predictions differ beyond tolerance" in _golden_mismatches(
        stale, committed
    )

    stale_feature = deepcopy(committed)
    stale_feature["vectors"][0]["features"][0] += GOLDEN_FEATURE_ATOL * 2.0
    assert "golden-vector features differ beyond tolerance" in _golden_mismatches(
        stale_feature, committed
    )

    non_finite = deepcopy(committed)
    non_finite["vectors"][0]["expected"][0] = float("inf")
    assert "golden vectors must contain only finite numbers" in _golden_mismatches(
        non_finite, committed
    )

    incompatible = deepcopy(committed)
    incompatible["schema_hash"] = "wrong"
    assert "golden-vector metadata or feature/output order differs" in _golden_mismatches(
        incompatible, committed
    )
