"""GrowboxProfile: load/save, Scenario + payload mapping."""

from __future__ import annotations

from pathlib import Path

from tools.ml.profile import (
    PROFILES_DIR,
    default_profile,
    load_profile,
    profile_from_dict,
    profile_to_payload,
    profile_to_scenario,
    save_profile,
)
from tools.ml.simulator import SequentialEnvironmentSimulator
from tools.ml.twin.config import (
    GrowboxConfig,
    apply_growbox_config,
    read_growbox_config,
)


def test_default_profile_to_scenario():
    profile = default_profile(profile_id="t1")
    scenario = profile_to_scenario(profile, seed=3)
    assert scenario.environment.growbox_volume_m3 == 0.8
    assert [p.available for p in scenario.pots] == [True, False, False, False]
    assert scenario.actuators.heater.available
    assert scenario.actuators.fan.available
    assert scenario.validity.air_temperature_c


def test_profile_roundtrip_json(tmp_path: Path):
    profile = default_profile(profile_id="round", title="Round trip")
    profile.chamber.growbox_volume_m3 = 1.1
    profile.pots[0].pot_volume_l = 15.0
    path = tmp_path / "p.json"
    save_profile(profile, path)
    loaded = load_profile(path)
    assert loaded.profile_id == "round"
    assert loaded.chamber.growbox_volume_m3 == 1.1
    assert loaded.pots[0].pot_volume_l == 15.0


def test_profile_to_payload_has_contract_shape():
    profile = default_profile()
    payload = profile_to_payload(profile, seed=7)
    assert payload["seed"] == 7
    assert "environment" in payload
    assert "validity" in payload
    assert "actuators" in payload
    assert len(payload["pots"]) == 4
    assert payload["pots"][0]["available"] is True
    assert payload["pots"][0]["cultivation"]["pot_volume_l"] == 12.0
    assert payload["actuators"]["heater"]["available"] is True


def test_example_profile_file_exists():
    path = PROFILES_DIR / "example-single-pot.json"
    assert path.is_file(), f"missing example profile: {path}"
    profile = load_profile(path)
    assert profile.profile_id == "example-single-pot"
    assert profile.active_pot_count() == 1


def test_apply_flat_via_profile_updates_sim():
    profile = default_profile()
    sim = SequentialEnvironmentSimulator(profile_to_scenario(profile, seed=0), seed=0)
    cfg = GrowboxConfig(
        growbox_volume_m3=1.4,
        thermal_mass_j_per_k=40_000.0,
        heat_loss_w_per_k=8.0,
        air_leak_rate_ach=0.4,
        active_pots=2,
        pot_volume_l=20.0,
        substrate_water_capacity_ml=5_000.0,
    )
    changed = apply_growbox_config(sim, cfg)
    assert "growbox_volume_m3" in changed
    assert "active_pots" in changed
    after = read_growbox_config(sim)
    assert after.growbox_volume_m3 == 1.4
    assert after.active_pots == 2
    assert after.pot_volume_l == 20.0
    assert sum(1 for p in sim.scenario.pots if p.available) == 2


def test_config_root_menu_and_sections():
    from tools.ml.twin.config import (
        MENU_SECTIONS,
        ConfigEditor,
        editor_panel,
        root_menu_table,
        toggle_flag_at_cursor,
    )

    assert [s for s, _ in MENU_SECTIONS] == ["chamber", "pots", "sensors", "outputs"]
    root = root_menu_table(0)
    assert "configurator" in root
    assert "Chamber" in root
    assert "Sensors" in root
    assert "Outputs" in root

    profile = default_profile()
    sim = SequentialEnvironmentSimulator(profile_to_scenario(profile, seed=0), seed=0)
    editor = ConfigEditor(values=None)
    editor.open_root(sim)
    assert editor.level == "root"
    assert "Chamber" in editor_panel(editor)
    editor.menu_cursor = 0
    editor.enter_section()
    assert editor.level == "section"
    assert editor.section == "chamber"
    assert "volume" in editor_panel(editor)
    assert editor.back() is False  # to root
    assert editor.level == "root"
    editor.menu_cursor = 2  # sensors
    editor.enter_section()
    assert editor.section == "sensors"
    assert "air T" in editor_panel(editor)
    before = editor.profile.sensors.co2_ppm
    # cursor on CO2 (index 2)
    editor.cursor = 2
    toggle_flag_at_cursor(editor)
    assert editor.profile.sensors.co2_ppm is (not before)
    editor.menu_cursor = 3
    editor.level = "root"
    editor.enter_section()
    assert editor.section == "outputs"
    assert "heater" in editor_panel(editor)


def test_config_editor_values_filled_when_profile_preset():
    """Regression: live started with profile set but values=None → j/k asserted."""
    from tools.ml.twin.config import ConfigEditor

    profile = default_profile()
    sim = SequentialEnvironmentSimulator(profile_to_scenario(profile, seed=0), seed=0)
    editor = ConfigEditor(active=True, section="chamber", cursor=0, profile=profile, values=None)
    vals = editor.ensure_values(sim)
    assert vals is not None
    assert vals.growbox_volume_m3 == profile.chamber.growbox_volume_m3
    editor2 = ConfigEditor(active=True, profile=profile, values=None)
    editor2.sync_from_simulator(sim)
    assert editor2.values is not None
    assert editor2.values.active_pots == 1


def test_profile_from_dict_partial():
    profile = profile_from_dict(
        {
            "profile_id": "partial",
            "chamber": {"growbox_volume_m3": 2.0},
            "pots": [{"available": True, "pot_volume_l": 10}],
            "sensors": {"co2_ppm": False},
            "actuators": {"heater": {"available": False}},
        }
    )
    assert profile.chamber.growbox_volume_m3 == 2.0
    assert profile.pots[0].available
    assert profile.sensors.co2_ppm is False
    assert profile.actuators["heater"].available is False
