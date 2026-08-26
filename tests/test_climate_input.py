from __future__ import annotations

import json
import math

import numpy as np

from tools.ml.climate_input import (
    CLIMATE_V6_CONTRACT_PATH,
    DEFAULT_SENSOR_TIMEOUT_MS,
    ClimateInputConfig,
    ClimateTargets,
    ClimateTrendEstimator,
    ClimateTrends,
    MeasurementStatus,
    TrendValue,
    air_vpd_kpa,
    climate_controller_record,
    encode_climate_input,
)
from tools.ml.climate_simulator import (
    ClimateAction,
    ClimateScenario,
    ClimateState,
)
from tools.ml.contract import load_contract


def feature_value(vector: np.ndarray, name: str) -> float:
    contract = load_contract(CLIMATE_V6_CONTRACT_PATH)
    return float(vector[contract.feature_names.index(name)])


def test_python_encoder_matches_cpp_reference_case() -> None:
    scenario = ClimateScenario()
    state = ClimateState(
        air_temperature_c=24.0,
        relative_humidity_pct=60.0,
        co2_ppm=999.0,
        outside_temperature_c=18.0,
        outside_humidity_pct=45.0,
        light_level=0.75,
    )
    status = {
        "air_temperature_c": MeasurementStatus(valid=True, age_ms=0),
        "relative_humidity_pct": MeasurementStatus(valid=True, age_ms=0),
        "co2_ppm": MeasurementStatus(valid=False, age_ms=0),
        "outside_temperature_c": MeasurementStatus(valid=True, age_ms=40_000),
        "outside_humidity_pct": MeasurementStatus(valid=True, age_ms=0),
    }
    trends = ClimateTrends(
        temperature=TrendValue(1.0, True),
        humidity=TrendValue(-2.0, True),
        co2=TrendValue(100.0, True),
    )
    config = ClimateInputConfig(humidity_control_mode="VPD")
    vector = encode_climate_input(
        scenario,
        state,
        previous=ClimateAction(heater=2.0),
        trends=trends,
        status=status,
        config=config,
    )
    assert vector.shape == (38,)
    assert math.isclose(feature_value(vector, "air_temperature_c"), 0.55, abs_tol=1e-6)
    assert feature_value(vector, "co2_valid") == 0.0
    assert feature_value(vector, "co2_fresh") == 1.0
    assert feature_value(vector, "outside_temperature_fresh") == 0.0
    assert feature_value(vector, "humidity_control_mode") == 1.0
    assert math.isclose(feature_value(vector, "light_level"), 0.75, abs_tol=1e-6)
    assert feature_value(vector, "previous_heater") == 1.0

    contract = load_contract(CLIMATE_V6_CONTRACT_PATH)
    defaults = {feature.name: feature for feature in contract.features}
    expected_co2_default = defaults["co2_ppm"].normalize(defaults["co2_ppm"].default)
    expected_outside_default = defaults["outside_temperature_c"].normalize(
        defaults["outside_temperature_c"].default
    )
    assert math.isclose(feature_value(vector, "co2_ppm"), expected_co2_default, abs_tol=1e-7)
    assert math.isclose(
        feature_value(vector, "outside_temperature_c"), expected_outside_default, abs_tol=1e-7
    )


def test_vpd_math_matches_firmware_reference() -> None:
    assert math.isclose(air_vpd_kpa(25.0, 60.0), 1.264, abs_tol=0.015)


def test_trend_estimator_matches_cpp_reference_rates() -> None:
    estimator = ClimateTrendEstimator()
    trends = ClimateTrends()
    for ms in range(0, 60_001, 5_000):
        minute = ms / 60_000.0
        state = ClimateState(
            air_temperature_c=20.0 + minute,
            relative_humidity_pct=60.0 - 2.0 * minute,
            co2_ppm=500.0 + 100.0 * minute,
        )
        trends = estimator.update(state, ms)
        if ms < 10_000:
            assert not trends.temperature.available

    assert trends.temperature.available
    assert trends.humidity.available
    assert trends.co2.available
    assert math.isclose(trends.temperature.rate_per_min, 1.0, abs_tol=0.01)
    assert math.isclose(trends.humidity.rate_per_min, -2.0, abs_tol=0.01)
    assert math.isclose(trends.co2.rate_per_min, 100.0, abs_tol=0.05)


def test_trend_stale_sensor_and_clock_rollback_match_firmware_semantics() -> None:
    estimator = ClimateTrendEstimator()
    state = ClimateState(air_temperature_c=20.0, relative_humidity_pct=60.0, co2_ppm=500.0)
    for ms in range(0, 60_001, 5_000):
        minute = ms / 60_000.0
        state = ClimateState(
            air_temperature_c=20.0 + minute,
            relative_humidity_pct=60.0,
            co2_ppm=500.0 + 100.0 * minute,
        )
        estimator.update(state, ms)

    stale = {"co2_ppm": MeasurementStatus(True, DEFAULT_SENSOR_TIMEOUT_MS + 1)}
    trends = estimator.update(state, 65_000, status=stale)
    assert not trends.co2.available

    rollback = estimator.update(state, 1_000)
    assert not rollback.temperature.available
    assert not rollback.humidity.available
    assert not rollback.co2.available


def test_one_hz_input_is_thinned_without_losing_linear_trend() -> None:
    estimator = ClimateTrendEstimator()
    trends = ClimateTrends()
    for ms in range(0, 60_001, 1_000):
        minute = ms / 60_000.0
        trends = estimator.update(
            ClimateState(
                air_temperature_c=20.0 + minute,
                relative_humidity_pct=60.0,
                co2_ppm=500.0,
            ),
            ms,
        )
    assert trends.temperature.available
    assert math.isclose(trends.temperature.rate_per_min, 1.0, abs_tol=0.02)


def test_controller_record_contains_no_hidden_or_future_plant_inputs() -> None:
    record = climate_controller_record(ClimateScenario(), ClimateState())
    serialized = json.dumps(record, sort_keys=True)
    for forbidden in (
        "pot_",
        "soil_",
        "irrigation",
        "nutrient",
        "heat_mat",
        "outside_co2",
        "thermal_mass",
        "heat_loss",
        "air_leak",
    ):
        assert forbidden not in serialized


def test_freshness_is_independent_from_validity() -> None:
    status = {"co2_ppm": MeasurementStatus(valid=False, age_ms=0)}
    record = climate_controller_record(
        ClimateScenario(), ClimateState(co2_ppm=1_200.0), status=status
    )
    measurement = record["measurements"]["co2_ppm"]
    assert measurement["valid"] is False
    assert measurement["fresh"] is True
    assert measurement["value"] != 1_200.0


def test_vpd_falls_back_when_required_measurement_is_stale() -> None:
    contract = load_contract(CLIMATE_V6_CONTRACT_PATH)
    status = {
        "air_temperature_c": MeasurementStatus(valid=True, age_ms=DEFAULT_SENSOR_TIMEOUT_MS + 1)
    }
    record = climate_controller_record(
        ClimateScenario(),
        ClimateState(air_temperature_c=30.0, relative_humidity_pct=30.0),
        status=status,
        contract=contract,
    )
    default_vpd = next(
        feature.default for feature in contract.features if feature.name == "air_vpd_kpa"
    )
    assert record["derived"]["air_vpd_kpa"] == default_vpd


def test_output_order_matches_climate_action_and_contract() -> None:
    contract = load_contract(CLIMATE_V6_CONTRACT_PATH)
    action = ClimateAction(
        heater=0.1,
        cooler=0.2,
        exhaust_fan=0.3,
        humidifier=0.4,
        dehumidifier=0.5,
        co2_doser=0.6,
    )
    vector = contract.output_vector(action.as_dict())
    assert contract.outputs == (
        "heater",
        "cooler",
        "exhaust_fan",
        "humidifier",
        "dehumidifier",
        "co2_doser",
    )
    assert np.allclose(vector, np.asarray(action.as_tuple(), dtype=np.float32))


def test_active_targets_and_mode_are_encoded_without_wall_clock() -> None:
    config = ClimateInputConfig(
        targets=ClimateTargets(
            air_temperature_c=26.0,
            relative_humidity_pct=65.0,
            air_vpd_kpa=1.4,
            co2_enabled=True,
            co2_ppm=1_100.0,
        ),
        humidity_control_mode="VPD",
    )
    record = climate_controller_record(
        ClimateScenario(), ClimateState(light_level=0.8), config=config
    )
    assert record["control"]["humidity_control_mode"] == "VPD"
    assert record["targets"]["air_temperature_c"] == 26.0
    assert record["targets"]["co2_enabled"] is True
    assert record["schedule"]["light_level"] == 0.8
    assert "current_time" not in record
