from __future__ import annotations

from tools.ml.climate_replay import replay_climate_trace_record
from tools.ml.climate_trace_io import iter_climate_trace_ndjson_records
from tools.ml.generate_climate_replay_fixture import (
    DEFAULT_OUTPUT,
    render_ndjson,
    replay_fixture_records,
)
from tools.ml.generate_climate_runtime_parity import (
    DEFAULT_OUTPUT as CPP_PARITY_OUTPUT,
)
from tools.ml.generate_climate_runtime_parity import (
    _case_specs,
    _model,
    render_header,
)


def test_committed_replay_fixture_matches_canonical_generator() -> None:
    assert DEFAULT_OUTPUT.read_text(encoding="utf-8") == render_ndjson()


def test_replay_fixture_reuses_all_cpp_parity_cases_in_order() -> None:
    specs = _case_specs()
    records = replay_fixture_records()
    assert len(records) == len(specs) == 12
    for spec, record in zip(specs, records, strict=True):
        assert record["policy"]["mode"] == spec.mode.value


def test_every_canonical_record_replays_without_policy_divergence() -> None:
    specs = _case_specs()
    records = tuple(iter_climate_trace_ndjson_records(DEFAULT_OUTPUT))
    assert len(records) == len(specs)
    for spec, record in zip(specs, records, strict=True):
        # A failing model cannot be re-invoked as a deterministic candidate; its
        # recorded Rule fallback is replayed without a model. Fixed models are
        # supplied so shadow/active ML outputs are checked as well.
        model = _model(spec) if spec.model_behavior == "fixed" else None
        divergence = replay_climate_trace_record(record, model=model)
        assert divergence is None, f"{spec.name}: {divergence}"


def test_cpp_golden_header_still_comes_from_same_case_specs() -> None:
    assert CPP_PARITY_OUTPUT.read_text(encoding="utf-8") == render_header()
