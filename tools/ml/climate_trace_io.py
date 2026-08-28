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
