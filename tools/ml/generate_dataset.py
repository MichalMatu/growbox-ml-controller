"""Scenario-level randomized sequential dataset generation for active contract."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path

import numpy as np

from .alignment import assert_outputs_match_contract
from .contract import ACTIVE_CONTRACT_PATH, Contract, load_contract
from .controller_input import (
    GLOBAL_SENSOR_NAMES,
    POT_SENSOR_NAMES,
    controller_input_record,
)

# Public re-exports for tests and older call sites.
__all__ = (
    "GLOBAL_SENSOR_NAMES",
    "POT_SENSOR_NAMES",
    "controller_input_record",
    "generate_dataset",
    "random_scenario",
    "randomized_scenarios",
)
from .dataset import Dataset, DatasetConfig, split_scenarios
from .simulator import (
    MAX_POTS,
    OUTPUT_NAMES,
    Co2DoserCapabilities,
    ControlTargets,
    CoolerCapabilities,
    DehumidifierCapabilities,
    EnvironmentParameters,
    EnvironmentState,
    FanCapabilities,
    GlobalActuators,
    HeaterCapabilities,
    HeatMatCapabilities,
    HumidifierCapabilities,
    LightsConfig,
    NutrientHeaterCapabilities,
    PotConfig,
    PotCultivation,
    PotState,
    PumpCapabilities,
    ResponseLag,
    Scenario,
    SensorValidity,
    SequentialEnvironmentSimulator,
)
from .teacher import RolloutTeacher


def _capability(rng: np.random.Generator, *, forced_missing: bool) -> bool:
    return not forced_missing and bool(rng.random() >= 0.14)


def _random_pot_config(
    rng: np.random.Generator,
    *,
    available: bool,
) -> PotConfig:
    if not available:
        return PotConfig()
    soil_moisture_valid = bool(rng.random() >= 0.10)
    soil_temperature_valid = bool(rng.random() >= 0.22)
    irrigation_available = bool(rng.random() >= 0.16)
    heat_mat_available = soil_temperature_valid and bool(rng.random() >= 0.72)
    pot_volume = float(rng.uniform(2.0, 35.0))
    return PotConfig(
        available=True,
        soil_moisture_valid=soil_moisture_valid,
        soil_temperature_valid=soil_temperature_valid,
        cultivation=PotCultivation(
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
        heat_mat=HeatMatCapabilities(
            available=heat_mat_available,
            max_power_w=float(rng.uniform(8.0, 45.0)) if heat_mat_available else 0.0,
        ),
        target_soil_moisture_pct=float(rng.uniform(38.0, 70.0)),
        target_soil_temperature_c=float(rng.uniform(16.0, 28.0)),
    )


def random_scenario(index: int, seed: int) -> Scenario:
    rng = np.random.default_rng(seed)

    if index % 12 == 8:
        active_count = 0
    else:
        active_count = int(rng.integers(0, MAX_POTS + 1))
    if active_count == 0:
        active_indices: set[int] = set()
    else:
        active_indices = set(rng.choice(MAX_POTS, size=active_count, replace=False))

    heater_available = _capability(rng, forced_missing=index % 12 == 1)
    fan_available = _capability(rng, forced_missing=index % 12 == 2)
    humidifier_available = _capability(rng, forced_missing=index % 12 == 3)
    dehumidifier_available = _capability(rng, forced_missing=index % 12 == 4)
    cooler_available = _capability(rng, forced_missing=index % 12 == 5)
    co2_doser_available = _capability(rng, forced_missing=index % 12 == 6)

    co2_valid = bool(rng.random() >= 0.12)
    outside_co2_valid = bool(rng.random() >= 0.18)
    nutrient_valid = bool(rng.random() >= 0.55)
    nutrient_heater_available = nutrient_valid and bool(rng.random() >= 0.78)

    pots = tuple(
        _random_pot_config(rng, available=pot_index in active_indices)
        for pot_index in range(MAX_POTS)
    )
    pot_states = []
    for pot_index, pot in enumerate(pots):
        if pot.available and pot.soil_moisture_valid:
            soil_moisture = float(rng.uniform(20.0, 75.0))
        else:
            soil_moisture = 44.0
        if pot.available and pot.soil_temperature_valid:
            soil_temperature = float(rng.uniform(12.0, 32.0))
        else:
            soil_temperature = 20.0
        pot_states.append(
            PotState(soil_moisture_pct=soil_moisture, soil_temperature_c=soil_temperature)
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
        nutrient_heater=NutrientHeaterCapabilities(
            available=nutrient_heater_available,
            max_power_w=float(rng.uniform(40.0, 250.0)) if nutrient_heater_available else 0.0,
            efficiency=float(rng.uniform(0.75, 1.0)),
        ),
        lights=LightsConfig(
            integrated=bool(rng.random() >= 0.08),
            max_heat_w=float(rng.uniform(40.0, 350.0)),
        ),
    )

    return Scenario(
        scenario_id=f"scenario-{index:04d}-seed-{seed}",
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
            pots=pot_states,
        ),
        environment=EnvironmentParameters(
            growbox_volume_m3=float(rng.uniform(0.15, 4.0)),
            thermal_mass_j_per_k=float(rng.uniform(12_000.0, 180_000.0)),
            heat_loss_w_per_k=float(rng.uniform(2.0, 30.0)),
            air_leak_rate_ach=float(rng.uniform(0.05, 2.0)),
        ),
        actuators=actuators,
        pots=pots,
        targets=ControlTargets(
            target_air_temperature_c=float(rng.uniform(19.0, 30.0)),
            target_air_humidity_pct=float(rng.uniform(45.0, 80.0)),
            target_co2_ppm=float(rng.uniform(550.0, 1300.0)),
            target_nutrient_solution_temperature_c=float(rng.uniform(16.0, 26.0)),
        ),
        validity=SensorValidity(
            air_temperature_c=True,
            air_humidity_pct=True,
            co2_ppm=co2_valid,
            outside_temperature_c=True,
            outside_humidity_pct=True,
            outside_co2_ppm=outside_co2_valid,
            nutrient_solution_temperature_c=nutrient_valid,
            pot_soil_moisture=tuple(pot.soil_moisture_valid for pot in pots),
            pot_soil_temperature=tuple(pot.soil_temperature_valid for pot in pots),
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


def randomized_scenarios(config: DatasetConfig) -> tuple[Scenario, ...]:
    rng = np.random.default_rng(config.seed)
    seeds = rng.integers(1, np.iinfo(np.int32).max, size=config.scenario_count)
    return tuple(random_scenario(index, int(seed)) for index, seed in enumerate(seeds))


def _pot_runtime_validity(
    scenario: Scenario,
    pot_index: int,
    *,
    corruption: Mapping[str, bool],
) -> dict[str, bool]:
    pot = scenario.pots[pot_index]
    installed = scenario.validity
    return {
        "soil_moisture_pct": (
            pot.available
            and pot.soil_moisture_valid
            and installed.pot_soil_moisture[pot_index]
            and not corruption.get(f"pot_{pot_index}_soil_moisture_pct", False)
        ),
        "soil_temperature_c": (
            pot.available
            and pot.soil_temperature_valid
            and installed.pot_soil_temperature[pot_index]
            and not corruption.get(f"pot_{pot_index}_soil_temperature_c", False)
        ),
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


def generate_dataset(
    config: DatasetConfig,
    *,
    contract: Contract | None = None,
    teacher: RolloutTeacher | None = None,
) -> Dataset:
    contract = contract or load_contract(ACTIVE_CONTRACT_PATH)
    assert_outputs_match_contract(contract, OUTPUT_NAMES, context="simulator")
    teacher = teacher or RolloutTeacher()
    scenarios = randomized_scenarios(config)
    split_by_id = split_scenarios(
        (scenario.scenario_id for scenario in scenarios), seed=config.seed + 31
    )

    feature_rows: list[np.ndarray] = []
    label_rows: list[np.ndarray] = []
    scenario_ids: list[str] = []
    scenario_seeds: list[int] = []
    splits: list[str] = []

    for scenario_index, scenario in enumerate(scenarios):
        simulator = SequentialEnvironmentSimulator(scenario)
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

            pot_validity: dict[int, dict[str, bool]] = {}
            pot_corruption: dict[str, bool] = {}
            for pot_index in range(MAX_POTS):
                for sensor_name in POT_SENSOR_NAMES:
                    key = f"pot_{pot_index}_{sensor_name}"
                    invalid = (
                        key == permanent_invalid
                        or corruption_rng.random() < config.invalid_reading_probability
                    )
                    if invalid:
                        pot_corruption[key] = True
                pot_validity[pot_index] = _pot_runtime_validity(
                    scenario, pot_index, corruption=pot_corruption
                )

            record = controller_input_record(
                scenario,
                observation,
                validity=global_validity,
                pot_validity=pot_validity,
                previous=simulator.previous_command,
            )
            sensors = dict(record["sensors"])
            for name in GLOBAL_SENSOR_NAMES:
                if corruption_flags.get(name):
                    _corrupt_sensor_values(sensors, name, corruption_rng=corruption_rng)
            record["sensors"] = sensors

            for pot_index in range(MAX_POTS):
                pot_record = record["pots"][pot_index]
                pot_sensors = dict(pot_record["sensors"])
                for sensor_name in POT_SENSOR_NAMES:
                    key = f"pot_{pot_index}_{sensor_name}"
                    if pot_corruption.get(key):
                        if sensor_name in pot_sensors:
                            _corrupt_sensor_values(
                                pot_sensors, sensor_name, corruption_rng=corruption_rng
                            )
                        pot_record["validity"][sensor_name] = False
                pot_record["sensors"] = pot_sensors

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
    dataset = generate_dataset(config, teacher=RolloutTeacher(horizon_steps=horizon))
    dataset.save(args.output)
    print(
        f"generated {len(dataset.features)} sequential rows from "
        f"{config.scenario_count} scenarios at {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
