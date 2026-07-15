"""End-to-end panel API tests for v2 scenarios and presets."""

from __future__ import annotations

import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest
from tests.test_panel import _http_json

from tools.ml.contract import V2_CONTRACT_PATH, load_contract
from tools.panel.form_schema import SCENARIO_PRESETS, build_panel_schema, default_scenario
from tools.panel.server import PanelHandler


def test_schema_exposes_v2_metadata_and_presets():
    schema = build_panel_schema()
    contract = load_contract(V2_CONTRACT_PATH)
    assert schema["schema_version"] == 2
    assert schema["schema_hash"] == contract.short_hash
    assert schema["feature_count"] == 103
    assert len(schema["outputs"]) == 10
    preset_ids = {preset["id"] for preset in schema["presets"]}
    assert preset_ids == set(SCENARIO_PRESETS.keys())


@pytest.mark.parametrize("preset_id", list(SCENARIO_PRESETS.keys()))
def test_each_preset_produces_valid_v2_scenario(preset_id: str):
    scenario = default_scenario(seed=202, preset=preset_id)
    assert scenario["seed"] == 202
    assert isinstance(scenario.get("zones"), list)
    assert len(scenario["zones"]) == 4
    assert "actuators" in scenario
    assert "heater" in scenario["actuators"]
    assert "safety" in scenario
    assert "maximum_nutrient_soil_delta_c" in scenario["safety"]


def test_http_presets_and_defaults_with_preset(panel_http_server):
    _fake, base = panel_http_server
    status, payload = _http_json("GET", base, "/api/presets")
    assert status == 200
    assert len(payload["presets"]) == len(SCENARIO_PRESETS)

    status, payload = _http_json(
        "POST",
        base,
        "/api/defaults",
        {"seed": 404, "preset": "disabled_actuators"},
    )
    assert status == 200
    scenario = payload["scenario"]
    assert payload["preset"] == "disabled_actuators"
    assert scenario["actuators"]["heater"]["available"] is False
    assert scenario["actuators"]["fan"]["available"] is True


def test_e2e_load_scenario_all_presets(panel_http_server):
    fake, base = panel_http_server
    _http_json("POST", base, "/api/connect", {"port": "/dev/fake"})
    for preset_id in SCENARIO_PRESETS:
        scenario = default_scenario(seed=101, preset=preset_id)
        body = {key: scenario[key] for key in scenario if key != "seed"}
        status, payload = _http_json(
            "POST",
            base,
            "/api/load_scenario",
            {"seed": scenario["seed"], "scenario": body},
        )
        assert status == 200, preset_id
        assert payload == {"ok": True}
        sent = fake.commands[-1]
        assert sent["command"] == "load_scenario"
        assert len(sent["zones"]) == 4


def test_saturated_soil_preset_has_high_moisture():
    scenario = default_scenario(seed=1, preset="saturated_soil")
    zone0 = scenario["zones"][0]
    assert zone0["sensors"]["soil_moisture_pct"] >= zone0["targets"]["soil_moisture_pct"]


def test_panel_static_includes_v2_scripts():
    server = ThreadingHTTPServer(("127.0.0.1", 0), PanelHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        with urllib.request.urlopen(f"{base}/js/live.js") as response:
            body = response.read().decode("utf-8")
            assert "panelOutputNames" in body
            assert "OUTPUT_LABELS" in body
        with urllib.request.urlopen(f"{base}/index.html") as response:
            body = response.read().decode("utf-8")
            assert "scenario-preset" in body
            assert "panel v2" in body
    finally:
        server.shutdown()
        thread.join(timeout=2.0)
