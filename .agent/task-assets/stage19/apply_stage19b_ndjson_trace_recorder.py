from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()

MODULE = dedent(r'''
"""Streaming NDJSON persistence for climate-v6 runtime trace records.

The runtime core remains filesystem-free. This module persists already-built
and validated climate runtime trace records as one canonical JSON object per
line so traces can be streamed, inspected, and replayed without loading an
entire session into memory.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import jsonschema

from .climate_trace import (
    canonical_climate_runtime_trace_json,
    validate_climate_runtime_trace_record,
)


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant {value!r} is not allowed")


def encode_climate_trace_ndjson_record(record: Mapping[str, Any]) -> str:
    """Return one canonical JSON object without a trailing newline."""

    return canonical_climate_runtime_trace_json(record)


def decode_climate_trace_ndjson_record(line: str) -> dict[str, Any]:
    """Decode and validate exactly one NDJSON record line."""

    if not isinstance(line, str):
        raise TypeError("trace NDJSON line must be a string")
    payload = line.rstrip("\r\n")
    if not payload.strip():
        raise ValueError("trace NDJSON record must not be empty")
    if "\n" in payload or "\r" in payload:
        raise ValueError("trace NDJSON decoder accepts exactly one line")
    try:
        value = json.loads(payload, parse_constant=_reject_json_constant)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid trace JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError("trace NDJSON record root must be an object")
    validate_climate_runtime_trace_record(value)
    return value


def append_climate_trace_ndjson_record(
    path: str | Path,
    record: Mapping[str, Any],
    *,
    fsync: bool = False,
) -> None:
    """Validate and append exactly one record to an NDJSON trace file."""

    line = encode_climate_trace_ndjson_record(record)
    trace_path = Path(path)
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(line)
        stream.write("\n")
        stream.flush()
        if fsync:
            os.fsync(stream.fileno())


def iter_climate_trace_ndjson_records(path: str | Path) -> Iterator[dict[str, Any]]:
    """Yield validated records one line at a time without buffering the file."""

    trace_path = Path(path)
    with trace_path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            try:
                yield decode_climate_trace_ndjson_record(line)
            except (TypeError, ValueError, jsonschema.ValidationError) as exc:
                raise ValueError(
                    f"invalid climate trace NDJSON at line {line_number}: {exc}"
                ) from exc


__all__ = [
    "append_climate_trace_ndjson_record",
    "decode_climate_trace_ndjson_record",
    "encode_climate_trace_ndjson_record",
    "iter_climate_trace_ndjson_records",
]
''').lstrip()

TESTS = dedent(r'''
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
''').lstrip()

files = {
    ROOT / "tools" / "ml" / "climate_trace_io.py": MODULE,
    ROOT / "tests" / "test_climate_trace_io.py": TESTS,
}

for path, content in files.items():
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
