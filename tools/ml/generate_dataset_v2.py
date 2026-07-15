"""Scenario-level randomized sequential dataset generation for contract v2."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path

import numpy as np

from .contract import V2_CONTRACT_PATH, Contract, load_contract
from .generate_dataset import Dataset, DatasetConfig, split_scenarios
from .simulator_v2 import (
    MAX_ZONES,
    Co2DoserCapabilities,
    ControlTargets,
    CoolerCapabilities,
    DehumidifierCapabilities,
    EnvironmentParameters,
    EnvironmentState,
    FanCapabilities,
    GlobalActuators,
    HeaterCapabilities,
    HumidifierCapabilities,
    LightsConfig,
    PumpCapabilities,
    ResponseLag,
    Scenario,
    SensorValidity,
    SequentialEnvironmentSimulatorV2,
    ZoneConfig,
    ZoneCultivation,
    ZoneState,
)
from .teacher_v2 import RolloutTeacherV2

GLOBAL_SENSOR_NAMES = (
    "air_temperature_c",
    "air_humidity_pct",
    "co2_ppm",
    "nutrient_solution_temperature_c",
    "outside_temperature_c",
    "outside_humidity_pct",
    "outside_co2_ppm",
)

ZONE_SENSOR_NAMES = ("soil_moisture_pct", "soil_temperature_c")


def _capability(rng: np.random.Generator, *, forced_missing: bool) -> bool:
    return not forced_missing and bool(rng.random() >= 0.14)


def _random_zone_config(
    rng: np.random.Generator,
    *,
    available: bool,
) -> ZoneConfig:
    if not available:
        return ZoneConfig()
    soil_moisture_valid = bool(rng.random() >= 0.10)
    soil_temperature_valid = bool(rng.random() >= 0.22)
    irrigation_available = bool(rng.random() >= 0.16)
    pot_volume = float(rng.uniform(2.0, 35.0))
    return ZoneConfig(
        available=True,
        soil_moisture_valid=soil_moisture_valid,
        soil_temperature_valid=soil_temperature_valid,
        cultivation=ZoneCultivation(
            pot_volume_l=pot_volume,
            substrate_water_capacity_ml=float(pot_volume * rng.uniform(140.0, 380.0)),
            transpiration_factor=float(rng.uniform(0.35, 2.0)),
        ),
        irrigation=PumpCapabilities(
            available=irrigation_available,
            flow_ml_s=float(rng.uniform(4.0, 55.0)) if irrigation_available else 0.0,
            maximum_pulse_s=float(rng.uniform(1.0, 12.0)) if irrigation_available else 0.0,
            minimum_interval_s=float(rng.uniform(120.0, 1800.0)) if irrigation_available else 300.0,
        ),
        target_soil_moisture_pct=float(rng.uniform(38.0, 70.0)),
    )


def random_scenario_v2(index: int, seed: int) -> Scenario:
    rng = np.random.default_rng(seed)

    if index % 12 == 8:
        active_count = 0
    else:
        active_count = int(rng.integers(0, MAX_ZONES + 1))
    if active_count == 0:
        active_indices: set[int] = set()
    else:
        active_indices = set(rng.choice(MAX_ZONES, size=active_count, replace=False))

    heater_available = _capability(rng, forced_missing=index % 12 == 1)
    fan_available = _capability(rng, forced_missing=index % 12 == 2)
    humidifier_available = _capability(rng, forced_missing=index % 12 == 3)
    dehumidifier_available = _capability(rng, forced_missing=index % 12 == 4)
    cooler_available = _capability(rng, forced_missing=index % 12 == 5)
    co2_doser_available = _capability(rng, forced_missing=index % 12 == 6)

    co2_valid = bool(rng.random() >= 0.12)
    outside_co2_valid = bool(rng.random() >= 0.18)
    nutrient_valid = bool(rng.random() >= 0.55)

    zones = tuple(
        _random_zone_config(rng, available=zone_index in active_indices)
        for zone_index in range(MAX_ZONES)
    )
    zone_states = []
    for zone_index, zone in enumerate(zones):
        if zone.available and zone.soil_moisture_valid:
            soil_moisture = float(rng.uniform(20.0, 75.0))
        else:
            soil_moisture = 44.0
        if zone.available and zone.soil_temperature_valid:
            soil_temperature = float(rng.uniform(12.0, 32.0))
        else:
            soil_temperature = 20.0
        zone_states.append(
            ZoneState(soil_moisture_pct=soil_moisture, soil_temperature_c=soil_temperature)
        )

    actuators = GlobalActuators(
        heater=HeaterCapabilities(
            available=heater_available,
            max_power_w=float(rng.uniform(60.0, 650.0)) if heater_available else 0.0,
            efficiency=float(rng.uniform(0.65, 1.0)),
        ),
        fan=FanCapabilities(
            available=fan_available,
            max_airflow_m3_h=float(rng.uniform(25.0, 450.0)) if fan_available else 0.0,
            minimum_command=float(rng.uniform(0.0, 0.35)),
        ),
        humidifier=HumidifierCapabilities(
            available=humidifier_available,
            max_output_g_h=float(rng.uniform(35.0, 500.0)) if humidifier_available else 0.0,
        ),
        dehumidifier=DehumidifierCapabilities(
            available=dehumidifier_available,
            max_removal_g_h=float(rng.uniform(30.0, 400.0)) if dehumidifier_available else 0.0,
        ),
        cooler=CoolerCapabilities(
            available=cooler_available,
            max_cooling_w=float(rng.uniform(80.0, 800.0)) if cooler_available else 0.0,
        ),
        co2_doser=Co2DoserCapabilities(
            available=co2_doser_available,
            dose_ppm_per_full_pulse=float(rng.uniform(60.0, 220.0)) if co2_doser_available else 0.0,
            maximum_pulse_s=float(rng.uniform(1.5, 6.0)) if co2_doser_available else 0.0,
        ),
        lights=LightsConfig(
            integrated=bool(rng.random() >= 0.08),
            max_heat_w=float(rng.uniform(40.0, 350.0)),
        ),
    )

    return Scenario(
        scenario_id=f"v2-scenario-{index:04d}-seed-{seed}",
        seed=int(seed),
        initial_state=EnvironmentState(
            air_temperature_c=float(rng.uniform(14.0, 33.0)),
            air_humidity_pct=float(rng.uniform(30.0, 85.0)),
            co2_ppm=float(rng.uniform(420.0, 1700.0)),
            outside_temperature_c=float(rng.uniform(-5.0, 34.0)),
            outside_humidity_pct=float(rng.uniform(20.0, 95.0)),
            outside_co2_ppm=float(rng.uniform(380.0, 520.0)),
            nutrient_solution_temperature_c=float(rng.uniform(10.0, 28.0)),
            lights_active=bool(rng.random() < 0.42),
            zones=zone_states,
        ),
        environment=EnvironmentParameters(
            growbox_volume_m3=float(rng.uniform(0.15, 4.0)),
            thermal_mass_j_per_k=float(rng.uniform(12_000.0, 180_000.0)),
            heat_loss_w_per_k=float(rng.uniform(2.0, 30.0)),
            air_leak_rate_ach=float(rng.uniform(0.05, 2.0)),
        ),
        actuators=actuators,
        zones=zones,
        targets=ControlTargets(
            target_air_temperature_c=float(rng.uniform(19.0, 30.0)),
            target_air_humidity_pct=float(rng.uniform(45.0, 80.0)),
            target_co2_ppm=float(rng.uniform(550.0, 1300.0)),
        ),
        validity=SensorValidity(
            air_temperature_c=True,
            air_humidity_pct=True,
            co2_ppm=co2_valid,
            outside_temperature_c=True,
            outside_humidity_pct=True,
            outside_co2_ppm=outside_co2_valid,
            nutrient_solution_temperature_c=nutrient_valid,
            zone_soil_moisture=tuple(zone.soil_moisture_valid for zone in zones),
            zone_soil_temperature=tuple(zone.soil_temperature_valid for zone in zones),
        ),
        timestep_s=10.0,
        response_lag=ResponseLag(
            heater_s=float(rng.uniform(15.0, 90.0)),
            fan_s=float(rng.uniform(2.0, 20.0)),
            humidifier_s=float(rng.uniform(8.0, 60.0)),
            dehumidifier_s=float(rng.uniform(8.0, 60.0)),
            cooler_s=float(rng.uniform(20.0, 90.0)),
        ),
    )


def randomized_scenarios_v2(config: DatasetConfig) -> tuple[Scenario, ...]:
    rng = np.random.default_rng(config.seed)
    seeds = rng.integers(1, np.iinfo(np.int32).max, size=config.scenario_count)
    return tuple(random_scenario_v2(index, int(seed)) for index, seed in enumerate(seeds))


def _zone_runtime_validity(
    scenario: Scenario,
    zone_index: int,
    *,
    corruption: Mapping[str, bool],
) -> dict[str, bool]:
    zone = scenario.zones[zone_index]
    installed = scenario.validity
    return {
        "soil_moisture_pct": (
            zone.available
            and zone.soil_moisture_valid
            and installed.zone_soil_moisture[zone_index]
            and not corruption.get(f"zone_{zone_index}_soil_moisture_pct", False)
        ),
        "soil_temperature_c": (
            zone.available
            and zone.soil_temperature_valid
            and installed.zone_soil_temperature[zone_index]
            and not corruption.get(f"zone_{zone_index}_soil_temperature_c", False)
        ),
    }


def controller_input_record_v2(
    scenario: Scenario,
    state: EnvironmentState,
    *,
    validity: Mapping[str, bool],
    zone_validity: Mapping[int, Mapping[str, bool]],
) -> dict[str, object]:
    sensors = {
        "air_temperature_c": state.air_temperature_c,
        "air_humidity_pct": state.air_humidity_pct,
        "co2_ppm": state.co2_ppm,
        "nutrient_solution_temperature_c": state.nutrient_solution_temperature_c,
        "outside_temperature_c": state.outside_temperature_c,
        "outside_humidity_pct": state.outside_humidity_pct,
        "outside_co2_ppm": state.outside_co2_ppm,
    }
    for name in GLOBAL_SENSOR_NAMES:
        if not validity.get(name, True):
            if name not in sensors:
                continue
            sensors.pop(name, None)

    zones_payload: list[dict[str, object]] = []
    for zone_index, zone in enumerate(scenario.zones):
        zone_state = state.zones[zone_index]
        zone_valid = zone_validity.get(zone_index, {})
        zone_sensors: dict[str, float] = {}
        if zone_valid.get("soil_moisture_pct", False):
            zone_sensors["soil_moisture_pct"] = zone_state.soil_moisture_pct
        if zone_valid.get("soil_temperature_c", False):
            zone_sensors["soil_temperature_c"] = zone_state.soil_temperature_c
        zones_payload.append(
            {
                "available": zone.available,
                "sensors": zone_sensors,
                "validity": {
                    "soil_moisture_pct": bool(zone_valid.get("soil_moisture_pct", False)),
                    "soil_temperature_c": bool(zone_valid.get("soil_temperature_c", False)),
                },
            }
        )

    return {
        "sensors": sensors,
        "validity": {
            "air_temperature_c": bool(validity.get("air_temperature_c", True)),
            "air_humidity_pct": bool(validity.get("air_humidity_pct", True)),
            "co2_ppm": bool(validity.get("co2_ppm", scenario.validity.co2_ppm)),
            "nutrient_solution_temperature_c": bool(
                validity.get(
                    "nutrient_solution_temperature_c",
                    scenario.validity.nutrient_solution_temperature_c,
                )
            ),
            "outside_temperature_c": bool(validity.get("outside_temperature_c", True)),
            "outside_humidity_pct": bool(validity.get("outside_humidity_pct", True)),
            "outside_co2_ppm": bool(
                validity.get("outside_co2_ppm", scenario.validity.outside_co2_ppm)
            ),
        },
        "zones": zones_payload,
        "pseudo": {"lights_active": state.lights_active},
    }


def _corrupt_sensor_values(
    sensors: dict[str, float],
    name: str,
    *,
    corruption_rng: np.random.Generator,
) -> None:
    if corruption_rng.random() < 0.5:
        sensors.pop(name, None)
    else:
        sign = -1.0 if corruption_rng.random() < 0.5 else 1.0
        sensors[name] = sign * 1.0e9


def generate_dataset_v2(
    config: DatasetConfig,
    *,
    contract: Contract | None = None,
    teacher: RolloutTeacherV2 | None = None,
) -> Dataset:
    contract = contract or load_contract(V2_CONTRACT_PATH)
    teacher = teacher or RolloutTeacherV2()
    scenarios = randomized_scenarios_v2(config)
    split_by_id = split_scenarios(
        (scenario.scenario_id for scenario in scenarios), seed=config.seed + 31
    )

    feature_rows: list[np.ndarray] = []
    label_rows: list[np.ndarray] = []
    scenario_ids: list[str] = []
    scenario_seeds: list[int] = []
    splits: list[str] = []

    for scenario_index, scenario in enumerate(scenarios):
        simulator = SequentialEnvironmentSimulatorV2(scenario)
        corruption_rng = np.random.default_rng(scenario.seed ^ 0x51A7)
        permanent_invalid: str | None = None
        if scenario_index % 7 == 5:
            permanent_invalid = GLOBAL_SENSOR_NAMES[scenario_index % len(GLOBAL_SENSOR_NAMES)]

        for _ in range(config.steps_per_scenario):
            observation = simulator.observe(add_sensor_noise=True)
            global_validity = {
                "air_temperature_c": scenario.validity.air_temperature_c,
                "air_humidity_pct": scenario.validity.air_humidity_pct,
                "co2_ppm": scenario.validity.co2_ppm,
                "nutrient_solution_temperature_c": scenario.validity.nutrient_solution_temperature_c,
                "outside_temperature_c": scenario.validity.outside_temperature_c,
                "outside_humidity_pct": scenario.validity.outside_humidity_pct,
                "outside_co2_ppm": scenario.validity.outside_co2_ppm,
            }
            corruption_flags: dict[str, bool] = {}
            for name in GLOBAL_SENSOR_NAMES:
                invalid = name == permanent_invalid or (
                    corruption_rng.random() < config.invalid_reading_probability
                )
                if invalid:
                    corruption_flags[name] = True
                    global_validity[name] = False

            zone_validity: dict[int, dict[str, bool]] = {}
            zone_corruption: dict[str, bool] = {}
            for zone_index in range(MAX_ZONES):
                for sensor_name in ZONE_SENSOR_NAMES:
                    key = f"zone_{zone_index}_{sensor_name}"
                    invalid = (
                        key == permanent_invalid
                        or corruption_rng.random() < config.invalid_reading_probability
                    )
                    if invalid:
                        zone_corruption[key] = True
                zone_validity[zone_index] = _zone_runtime_validity(
                    scenario, zone_index, corruption=zone_corruption
                )

            record = controller_input_record_v2(
                scenario,
                observation,
                validity=global_validity,
                zone_validity=zone_validity,
            )
            sensors = dict(record["sensors"])
            for name in GLOBAL_SENSOR_NAMES:
                if corruption_flags.get(name):
                    _corrupt_sensor_values(sensors, name, corruption_rng=corruption_rng)
            record["sensors"] = sensors

            for zone_index in range(MAX_ZONES):
                zone_record = record["zones"][zone_index]
                zone_sensors = dict(zone_record["sensors"])
                for sensor_name in ZONE_SENSOR_NAMES:
                    key = f"zone_{zone_index}_{sensor_name}"
                    if zone_corruption.get(key):
                        if sensor_name in zone_sensors:
                            _corrupt_sensor_values(
                                zone_sensors, sensor_name, corruption_rng=corruption_rng
                            )
                        zone_record["validity"][sensor_name] = False
                zone_record["sensors"] = zone_sensors

            feature_rows.append(contract.encode(record))
            teacher_result = teacher.choose(simulator, scenario.targets)
            label_rows.append(contract.output_vector(teacher_result.action.as_dict()))
            scenario_ids.append(scenario.scenario_id)
            scenario_seeds.append(scenario.seed)
            splits.append(split_by_id[scenario.scenario_id])
            simulator.step(teacher_result.action, add_sensor_noise=False)

    return Dataset(
        features=np.asarray(feature_rows, dtype=np.float32),
        labels=np.asarray(label_rows, dtype=np.float32),
        scenario_ids=np.asarray(scenario_ids),
        scenario_seeds=np.asarray(scenario_seeds, dtype=np.int64),
        splits=np.asarray(splits),
        feature_names=contract.feature_names,
        output_names=contract.outputs,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--quick", action="store_true")
    mode.add_argument("--full", action="store_true")
    parser.add_argument("--seed", type=int, default=1847)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = DatasetConfig.quick(args.seed) if args.quick else DatasetConfig.full(args.seed)
    horizon = 2 if args.quick else 4
    dataset = generate_dataset_v2(config, teacher=RolloutTeacherV2(horizon_steps=horizon))
    dataset.save(args.output)
    print(
        f"generated {len(dataset.features)} sequential rows from "
        f"{config.scenario_count} scenarios at {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
