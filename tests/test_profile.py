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
    base = read_growbox_config(sim)
    cfg = (
        base.with_value("growbox_volume_m3", 1.4)
        .with_value("thermal_mass_j_per_k", 40_000.0)
        .with_value("heat_loss_w_per_k", 8.0)
        .with_value("air_leak_rate_ach", 0.4)
        .with_value("active_pots", 2)
        .with_value("pot_volume_l", 20.0)
        .with_value("substrate_water_capacity_ml", 5_000.0)
        .with_value("heater_max_power_w", 220.0)
        .with_value("fan_max_airflow_m3_h", 150.0)
        .with_value("irrigation_flow_ml_s", 25.0)
    )
    changed = apply_growbox_config(sim, cfg)
    assert "growbox_volume_m3" in changed
    assert "active_pots" in changed
    after = read_growbox_config(sim)
    assert after.growbox_volume_m3 == 1.4
    assert after.active_pots == 2
    assert after.pot_volume_l == 20.0
    assert after.get("heater_max_power_w") == 220.0
    assert after.get("fan_max_airflow_m3_h") == 150.0
    assert sim.scenario.actuators.heater.max_power_w == 220.0
    assert sim.scenario.actuators.fan.max_airflow_m3_h == 150.0
    assert sim.scenario.pots[0].irrigation.flow_ml_s == 25.0
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


def test_toggle_irrigation_pot2_applies_to_simulator():
    """Outputs irr pot 2 must expand active pots and survive apply_editor."""
    from tools.ml.twin.config import (
        OUTPUT_ROWS,
        ConfigEditor,
        apply_editor_to_simulator,
        bump_growbox_config,
        read_output_flag,
        toggle_flag_at_cursor,
    )

    profile = default_profile()
    sim = SequentialEnvironmentSimulator(profile_to_scenario(profile, seed=0), seed=0)
    editor = ConfigEditor()
    editor.open_root(sim)
    editor.menu_cursor = 3
    editor.enter_section()
    keys = [r.key for r in OUTPUT_ROWS]
    editor.cursor = keys.index("irrigation_pot_2")
    assert read_output_flag(editor.profile, "irrigation_pot_2") is False
    toggle_flag_at_cursor(editor)
    apply_editor_to_simulator(sim, editor)
    assert sim.scenario.pots[1].available is True
    assert sim.scenario.pots[1].irrigation.available is True
    assert read_output_flag(editor.profile, "irrigation_pot_2") is True
    assert editor.values.active_pots == 2
    # Shrink via Pots → active pots must still work
    editor.section = "pots"
    editor.cursor = 0
    editor.values = bump_growbox_config(editor.values, 0, direction=-1, section="pots")
    apply_editor_to_simulator(sim, editor)
    assert [p.available for p in sim.scenario.pots] == [True, False, False, False]


def test_lights_active_profile_sets_initial_state():
    profile = default_profile()
    profile.sensors.lights_active = True
    scenario = profile_to_scenario(profile, seed=0)
    assert scenario.initial_state.lights_active is True
    assert scenario.actuators.lights.integrated is True


def test_lights_integrated_false_no_lamp_heat():
    from tools.ml.profile import ActuatorSlotProfile
    from tools.ml.simulator import ControlAction

    def run(integrated: bool) -> float:
        p = default_profile()
        p.sensors.lights_active = True
        p.actuators["lights"] = ActuatorSlotProfile(available=integrated, max_power_w=200.0)
        p.actuators["heater"] = ActuatorSlotProfile(available=False, max_power_w=0.0)
        sim = SequentialEnvironmentSimulator(profile_to_scenario(p, seed=0), seed=0)
        t0 = sim.state.air_temperature_c
        for _ in range(30):
            sim.step(ControlAction(), add_sensor_noise=False)
        return sim.state.air_temperature_c - t0

    assert run(True) > run(False) + 0.05


def test_profile_to_payload_no_ml_lights_actuator():
    profile = default_profile()
    profile.sensors.lights_active = True
    payload = profile_to_payload(profile, seed=9)
    assert "lights" not in payload["actuators"]
    assert payload["pseudo"]["lights_active"] is True
    assert "heater" in payload["actuators"]


def test_zero_active_pots_roundtrip():
    from tools.ml.profile import PotProfile
    from tools.ml.twin.config import flat_from_profile, profile_apply_flat

    profile = default_profile()
    profile.pots = [PotProfile() for _ in range(4)]
    assert profile.active_pot_count() == 0
    flat = flat_from_profile(profile)
    assert flat.active_pots == 0
    applied = profile_apply_flat(profile, flat)
    assert applied.active_pot_count() == 0
    scenario = profile_to_scenario(applied, seed=0)
    assert all(not p.available for p in scenario.pots)
    payload = profile_to_payload(applied)
    assert all(not p["available"] for p in payload["pots"])


def test_heater_unavailable_masks_and_zeros_lag():
    from tools.ml.profile import ActuatorSlotProfile, apply_profile_to_simulator
    from tools.ml.simulator import ControlAction

    profile = default_profile()
    sim = SequentialEnvironmentSimulator(profile_to_scenario(profile, seed=0), seed=0)
    sim.step(ControlAction(heater=1.0), add_sensor_noise=False)
    assert sim.effective_action.heater > 0.0
    profile.actuators["heater"] = ActuatorSlotProfile(available=False, max_power_w=180.0)
    apply_profile_to_simulator(sim, profile, preserve_state=True)
    assert sim.scenario.actuators.heater.available is False
    assert sim.effective_action.heater == 0.0
    sim.step(ControlAction(heater=1.0), add_sensor_noise=False)
    assert sim.previous_command.heater == 0.0


def test_actuator_limits_affect_van_henten():
    from tools.ml.profile import ActuatorSlotProfile
    from tools.ml.simulator import ControlAction

    def heat(w: float) -> float:
        p = default_profile()
        p.actuators["heater"] = ActuatorSlotProfile(available=True, max_power_w=w, efficiency=1.0)
        sim = SequentialEnvironmentSimulator(profile_to_scenario(p, seed=0), seed=0)
        for _ in range(25):
            sim.step(ControlAction(heater=1.0), add_sensor_noise=False)
        return sim.state.air_temperature_c

    def fan_cool(m3h: float) -> float:
        p = default_profile()
        p.actuators["fan"] = ActuatorSlotProfile(
            available=True, max_airflow_m3_h=m3h, minimum_command=0.0
        )
        sim = SequentialEnvironmentSimulator(profile_to_scenario(p, seed=0), seed=0)
        sim.state.outside_temperature_c = 5.0
        sim.state.air_temperature_c = 30.0
        for _ in range(40):
            sim.step(ControlAction(fan=1.0), add_sensor_noise=False)
        return sim.state.air_temperature_c

    def heat_loss(w_per_k: float) -> float:
        p = default_profile()
        p.chamber.heat_loss_w_per_k = w_per_k
        sim = SequentialEnvironmentSimulator(profile_to_scenario(p, seed=0), seed=0)
        sim.state.outside_temperature_c = 5.0
        sim.state.air_temperature_c = 30.0
        for _ in range(50):
            sim.step(ControlAction(), add_sensor_noise=False)
        return sim.state.air_temperature_c

    assert heat(500.0) > heat(50.0) + 0.3
    assert fan_cool(500.0) < fan_cool(10.0) - 0.2
    assert heat_loss(40.0) < heat_loss(1.0) - 0.2


def test_payload_disabled_actuator_zero_max():
    from tools.ml.profile import ActuatorSlotProfile

    profile = default_profile()
    profile.actuators["heater"] = ActuatorSlotProfile(
        available=False, max_power_w=180.0, efficiency=0.9, control_type="binary"
    )
    payload = profile_to_payload(profile)
    assert payload["actuators"]["heater"]["available"] is False
    assert payload["actuators"]["heater"]["max_power_w"] == 0.0


def test_sensor_validity_inactive_pot_false():
    from tools.ml.profile import PotProfile

    profile = default_profile()
    profile.pots[2] = PotProfile(
        available=False, soil_moisture_valid=True, soil_temperature_valid=True
    )
    scenario = profile_to_scenario(profile, seed=0)
    assert scenario.validity.pot_soil_moisture[2] is False
    assert scenario.validity.pot_soil_temperature[2] is False


def test_editor_esc_stack():
    from tools.ml.twin.config import ConfigEditor

    profile = default_profile()
    sim = SequentialEnvironmentSimulator(profile_to_scenario(profile, seed=0), seed=0)
    editor = ConfigEditor()
    editor.open_root(sim)
    assert editor.active and editor.level == "root"
    editor.enter_section()
    assert editor.level == "section"
    assert editor.back() is False
    assert editor.level == "root"
    assert editor.back() is True
    assert editor.active is False


def test_apply_preserves_live_air_temp():
    from tools.ml.profile import apply_profile_to_simulator

    profile = default_profile()
    sim = SequentialEnvironmentSimulator(profile_to_scenario(profile, seed=0), seed=0)
    sim.state.air_temperature_c = 33.3
    profile.chamber.growbox_volume_m3 = 1.5
    apply_profile_to_simulator(sim, profile, preserve_state=True)
    assert sim.state.air_temperature_c == 33.3
    assert sim.scenario.environment.growbox_volume_m3 == 1.5


def test_fan_minimum_command_dead_zone():
    from tools.ml.profile import ActuatorSlotProfile
    from tools.ml.simulator import ControlAction

    profile = default_profile()
    profile.actuators["fan"] = ActuatorSlotProfile(
        available=True, max_airflow_m3_h=90.0, minimum_command=0.3
    )
    sim = SequentialEnvironmentSimulator(profile_to_scenario(profile, seed=0), seed=0)
    sim.step(ControlAction(fan=0.2), add_sensor_noise=False)
    assert sim.previous_command.fan == 0.0
    sim.step(ControlAction(fan=0.5), add_sensor_noise=False)
    assert sim.previous_command.fan == 0.5


def test_cooler_alone_lowers_temperature():
    from tools.ml.profile import ActuatorSlotProfile
    from tools.ml.simulator import ControlAction

    profile = default_profile()
    profile.actuators["cooler"] = ActuatorSlotProfile(available=True, max_cooling_w=400.0)
    profile.actuators["heater"] = ActuatorSlotProfile(available=False, max_power_w=0.0)
    sim = SequentialEnvironmentSimulator(profile_to_scenario(profile, seed=0), seed=0)
    sim.state.air_temperature_c = 28.0
    t0 = sim.state.air_temperature_c
    for _ in range(40):
        sim.step(ControlAction(cooler=1.0), add_sensor_noise=False)
    assert sim.state.air_temperature_c < t0 - 0.3
