from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()

GENERATOR = dedent(r'''
"""Generate the canonical climate-v6 NDJSON replay regression fixture.

The fixture deliberately reuses the Stage18 Python/C++ parity case specs so the
serialized replay corpus and the host C++ golden header share one canonical set
of policy/safety scenarios.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from tools.ml.climate_input import CLIMATE_V6_CONTRACT_PATH
from tools.ml.climate_runtime import ClimateRuntimeConfig, ClimateRuntimeController
from tools.ml.climate_trace import (
    build_climate_runtime_trace_record,
    canonical_climate_runtime_trace_json,
)
from tools.ml.contract import load_contract
from tools.ml.generate_climate_runtime_parity import (
    _case_specs,
    _model,
    _profile,
    _scenario,
    _status_map,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = PROJECT_ROOT / "tests" / "fixtures" / "climate_runtime_replay.ndjson"


def replay_fixture_records() -> tuple[dict[str, object], ...]:
    contract_hash = load_contract(CLIMATE_V6_CONTRACT_PATH).hash_hex
    records: list[dict[str, object]] = []
    for spec in _case_specs():
        model = _model(spec)
        runtime = ClimateRuntimeController(
            model=model,
            config=ClimateRuntimeConfig(
                mode=spec.mode,
                sensor_timeout_ms=spec.sensor_timeout_ms,
                allow_unqualified_ml_active=spec.allow_ml_active,
            ),
        )
        scenario = _scenario(spec)
        profile = _profile(spec)
        status = _status_map(spec)
        decision = runtime.step(
            scenario,
            spec.state,
            profile,
            previous_command=spec.previous,
            monotonic_ms=spec.monotonic_ms,
            status=status,
            timestep_s=spec.timestep_s,
        )
        model_id = None if model is None else f"stage21:{spec.name}:{spec.model_behavior}"
        records.append(
            build_climate_runtime_trace_record(
                scenario,
                spec.state,
                profile,
                decision,
                previous_command=spec.previous,
                monotonic_ms=spec.monotonic_ms,
                status=status,
                sensor_timeout_ms=spec.sensor_timeout_ms,
                timestep_s=spec.timestep_s,
                model_id=model_id,
                model_contract_hash=contract_hash if model_id is not None else None,
            )
        )
    return tuple(records)


def render_ndjson() -> str:
    return "".join(
        f"{canonical_climate_runtime_trace_json(record)}\n" for record in replay_fixture_records()
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_ndjson(), encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
''').lstrip()

TEST = dedent(r'''
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
''').lstrip()

(ROOT / "tools/ml/generate_climate_replay_fixture.py").write_text(GENERATOR, encoding="utf-8")
(ROOT / "tests/test_climate_replay_fixture.py").write_text(TEST, encoding="utf-8")
