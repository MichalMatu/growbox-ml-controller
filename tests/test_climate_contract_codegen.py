from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.schema.generate_climate_contract import render, validate

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/environment-controller.v6.json"
HEADER = ROOT / "lib/environment_control/src/climate/ClimateContract.h"


def document():
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def test_generated_climate_header_is_fresh():
    assert HEADER.read_text(encoding="utf-8") == render(document())


def test_generator_rejects_pot_feature_leak():
    d = document()
    d["model"]["features"][0]["name"] = "soil_temperature_c"
    with pytest.raises(ValueError, match="non-climate feature"):
        validate(d)


def test_generator_rejects_output_reordering():
    d = document()
    o = d["model"]["outputs"]
    o[0], o[1] = o[1], o[0]
    with pytest.raises(ValueError, match="unexpected output order"):
        validate(d)
