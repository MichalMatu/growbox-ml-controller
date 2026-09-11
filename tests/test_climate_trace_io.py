from __future__ import annotations

import copy

import jsonschema
import numpy as np
import pytest

from tools.ml.climate_input import CLIMATE_V6_CONTRACT_PATH
from tools.ml.climate_runtime import (
    ClimatePolicyMode,
    ClimateRuntimeConfig,
    ClimateRuntimeController,
)
from tools.ml.climate_scenarios import build_training_episode
from tools.ml.climate_simulator import ClimateAction
from tools.ml.climate_trace import build_climate_runtime_trace_record
from tools.ml.climate_trace_io import (
    append_climate_trace_ndjson_record,
    decode_climate_trace_ndjson_record,
    encode_climate_trace_ndjson_record,
    iter_climate_trace_ndjson_records,
)
from tools.ml.contract import load_contract


class _FixedModel:
    def predict(self, features: np.ndarray) -> np.ndarray:
        assert features.shape == (44,)
        return np.asarray((0.2, 0.8, 0.7, 0.6, 0.4, 0.9), dtype=np.float32)


def _record(*, shadow: bool = False, monotonic_ms: int = 120_000):
    episode = build_training_episode("cold_heating", 0, 19_021 + int(shadow))
    runtime = ClimateRuntimeController(
        model=_FixedModel() if shadow else None,
        config=ClimateRuntimeConfig(
            mode=ClimatePolicyMode.ML_SHADOW if shadow else ClimatePolicyMode.RULE
        ),
    )
    previous = ClimateAction(heater=0.1, exhaust_fan=0.2)
    decision = runtime.step(
        episode.scenario,
        episode.scenario.initial_state,
        episode.first_profile,
        previous_command=previous,
        monotonic_ms=monotonic_ms,
    )
    contract_hash = load_contract(CLIMATE_V6_CONTRACT_PATH).hash_hex
    return build_climate_runtime_trace_record(
        episode.scenario,
        episode.scenario.initial_state,
        episode.first_profile,
        decision,
        previous_command=previous,
        monotonic_ms=monotonic_ms,
        model_id="stage13-compat" if shadow else None,
        model_contract_hash=contract_hash if shadow else None,
    )


def test_ndjson_encode_decode_round_trip_is_canonical() -> None:
    record = _record(shadow=True)
    line = encode_climate_trace_ndjson_record(record)
    assert "\n" not in line and "\r" not in line
    assert decode_climate_trace_ndjson_record(line) == record
    assert encode_climate_trace_ndjson_record(decode_climate_trace_ndjson_record(line)) == line


def test_append_and_stream_multiple_records(tmp_path) -> None:
    path = tmp_path / "nested" / "trace.ndjson"
    records = (_record(monotonic_ms=120_000), _record(shadow=True, monotonic_ms=130_000))
    append_climate_trace_ndjson_record(path, records[0])
    append_climate_trace_ndjson_record(path, records[1], fsync=True)

    raw = path.read_text(encoding="utf-8")
    assert raw.endswith("\n")
    assert len(raw.splitlines()) == 2

    iterator = iter_climate_trace_ndjson_records(path)
    assert iter(iterator) is iterator
    assert list(iterator) == list(records)


def test_invalid_record_is_rejected_before_file_mutation(tmp_path) -> None:
    path = tmp_path / "trace.ndjson"
    good = _record()
    append_climate_trace_ndjson_record(path, good)
    before = path.read_bytes()

    broken = copy.deepcopy(good)
    broken["hidden_simulator_truth"] = {"thermal_mass": 123.0}
    with pytest.raises(jsonschema.ValidationError):
        append_climate_trace_ndjson_record(path, broken)
    assert path.read_bytes() == before


def test_decoder_rejects_blank_malformed_multiline_and_non_finite_json() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        decode_climate_trace_ndjson_record("\n")
    with pytest.raises(ValueError, match="invalid trace JSON"):
        decode_climate_trace_ndjson_record("{not-json}")
    with pytest.raises(ValueError, match="exactly one line"):
        decode_climate_trace_ndjson_record("{}\n{}")
    with pytest.raises(ValueError, match="non-finite JSON constant"):
        decode_climate_trace_ndjson_record('{"value":NaN}')


def test_stream_reports_failing_line_number(tmp_path) -> None:
    path = tmp_path / "trace.ndjson"
    append_climate_trace_ndjson_record(path, _record())
    with path.open("a", encoding="utf-8") as stream:
        stream.write("\n")

    iterator = iter_climate_trace_ndjson_records(path)
    first = next(iterator)
    assert first["schema_id"] == "climate-runtime-trace"
    with pytest.raises(ValueError, match="line 2"):
        next(iterator)
