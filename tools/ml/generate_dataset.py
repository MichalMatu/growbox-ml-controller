"""Scenario-level randomized sequential dataset generation."""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .contract import Contract, load_contract
from .simulator import (
    SENSOR_NAMES,
    ActuatorCapabilities,
    ControlAction,
    ControlTargets,
    CultivationParameters,
    EnvironmentParameters,
    EnvironmentState,
    FanCapabilities,
    HeaterCapabilities,
    HumidifierCapabilities,
    PumpCapabilities,
    ResponseLag,
    Scenario,
    SensorNoise,
    SequentialEnvironmentSimulator,
)
from .teacher import RolloutTeacher


@dataclass(frozen=True)
class DatasetConfig:
    scenario_count: int
    steps_per_scenario: int
    seed: int = 1847
    invalid_reading_probability: float = 0.025

    @classmethod
    def quick(cls, seed: int = 1847) -> DatasetConfig:
        return cls(scenario_count=12, steps_per_scenario=20, seed=seed)

    @classmethod
    def full(cls, seed: int = 1847) -> DatasetConfig:
        return cls(scenario_count=72, steps_per_scenario=120, seed=seed)


@dataclass(frozen=True)
class Dataset:
    features: np.ndarray
    labels: np.ndarray
    scenario_ids: np.ndarray
    scenario_seeds: np.ndarray
    splits: np.ndarray
    feature_names: tuple[str, ...]
    output_names: tuple[str, ...]

    def __post_init__(self) -> None:
        rows = self.features.shape[0]
        if self.features.ndim != 2 or self.labels.ndim != 2:
            raise ValueError("features and labels must be matrices")
        if not all(
            len(values) == rows
            for values in (
                self.labels,
                self.scenario_ids,
                self.scenario_seeds,
                self.splits,
            )
        ):
            raise ValueError("dataset columns have inconsistent row counts")

    def select(self, split: str) -> tuple[np.ndarray, np.ndarray]:
        mask = self.splits == split
        return self.features[mask], self.labels[mask]

    def save(self, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            destination,
            features=self.features,
            labels=self.labels,
            scenario_ids=self.scenario_ids,
            scenario_seeds=self.scenario_seeds,
            splits=self.splits,
            feature_names=np.asarray(self.feature_names),
            output_names=np.asarray(self.output_names),
        )

    @classmethod
    def load(cls, path: str | Path) -> Dataset:
        with np.load(path, allow_pickle=False) as data:
            return cls(
                features=data["features"],
                labels=data["labels"],
                scenario_ids=data["scenario_ids"],
                scenario_seeds=data["scenario_seeds"],
                splits=data["splits"],
                feature_names=tuple(str(value) for value in data["feature_names"]),
                output_names=tuple(str(value) for value in data["output_names"]),
            )


def split_scenarios(
    scenario_ids: Iterable[str],
    *,
    seed: int,
    train_fraction: float = 0.70,
    validation_fraction: float = 0.15,
) -> dict[str, str]:
    unique = sorted(set(str(value) for value in scenario_ids))
    if len(unique) < 3:
        raise ValueError("at least three scenarios are needed for leakage-free splits")
    if not 0.0 < train_fraction < 1.0 or not 0.0 < validation_fraction < 1.0:
        raise ValueError("split fractions must be between zero and one")
    if train_fraction + validation_fraction >= 1.0:
        raise ValueError("train and validation fractions leave no test split")

    order = np.random.default_rng(seed).permutation(len(unique))
    shuffled = [unique[int(index)] for index in order]
    train_count = max(1, int(round(len(unique) * train_fraction)))
    validation_count = max(1, int(round(len(unique) * validation_fraction)))
    if train_count + validation_count >= len(unique):
        train_count = len(unique) - 2
        validation_count = 1
    mapping: dict[str, str] = {}
    for index, scenario_id in enumerate(shuffled):
        if index < train_count:
            mapping[scenario_id] = "train"
        elif index < train_count + validation_count:
            mapping[scenario_id] = "validation"
        else:
            mapping[scenario_id] = "test"
    return mapping


def _capability(rng: np.random.Generator, *, forced_missing: bool) -> bool:
    return not forced_missing and bool(rng.random() >= 0.14)


def random_scenario(index: int, seed: int) -> Scenario:
    rng = np.random.default_rng(seed)
    heater_available = _capability(rng, forced_missing=index % 12 == 1)
    fan_available = _capability(rng, forced_missing=index % 12 == 2)
    humidifier_available = _capability(rng, forced_missing=index % 12 == 3)
    pump_available = _capability(rng, forced_missing=index % 12 == 4)

    pot_volume = float(rng.uniform(2.0, 35.0))
    state = EnvironmentState(
        air_temperature_c=float(rng.uniform(14.0, 33.0)),
        air_humidity_pct=float(rng.uniform(30.0, 85.0)),
        co2_ppm=float(rng.uniform(420.0, 1700.0)),
        soil_moisture_pct=float(rng.uniform(20.0, 75.0)),
        outside_temperature_c=float(rng.uniform(-5.0, 34.0)),
        outside_humidity_pct=float(rng.uniform(20.0, 95.0)),
    )
    environment = EnvironmentParameters(
        growbox_volume_m3=float(rng.uniform(0.15, 4.0)),
        thermal_mass_j_per_k=float(rng.uniform(12_000.0, 180_000.0)),
        heat_loss_w_per_k=float(rng.uniform(2.0, 30.0)),
        air_leak_rate_ach=float(rng.uniform(0.05, 2.0)),
    )
    cultivation = CultivationParameters(
        pot_volume_l=pot_volume,
        substrate_water_capacity_ml=float(pot_volume * rng.uniform(140.0, 380.0)),
        transpiration_factor=float(rng.uniform(0.35, 2.0)),
    )

    heater_power = float(rng.uniform(60.0, 650.0)) if heater_available else 0.0
    fan_airflow = float(rng.uniform(25.0, 450.0)) if fan_available else 0.0
    humidifier_output = float(rng.uniform(35.0, 500.0)) if humidifier_available else 0.0
    pump_flow = float(rng.uniform(4.0, 55.0)) if pump_available else 0.0
    pulse = float(rng.uniform(1.0, 12.0)) if pump_available else 0.0
    actuators = ActuatorCapabilities(
        heater=HeaterCapabilities(
            available=heater_available,
            max_power_w=heater_power,
            efficiency=float(rng.uniform(0.65, 1.0)),
            control_type="binary" if rng.random() < 0.65 else "pwm",
        ),
        fan=FanCapabilities(
            available=fan_available,
            max_airflow_m3_h=fan_airflow,
            minimum_command=float(rng.uniform(0.1, 0.35)),
            control_type="pwm" if rng.random() < 0.8 else "binary",
        ),
        humidifier=HumidifierCapabilities(
            available=humidifier_available,
            max_output_g_h=humidifier_output,
            control_type="binary" if rng.random() < 0.85 else "pwm",
        ),
        irrigation_pump=PumpCapabilities(
            available=pump_available,
            flow_ml_s=pump_flow,
            maximum_pulse_s=pulse,
            minimum_interval_s=float(rng.uniform(120.0, 1800.0)),
            control_type="binary" if rng.random() < 0.9 else "pwm",
        ),
    )
    targets = ControlTargets(
        target_air_temperature_c=float(rng.uniform(19.0, 30.0)),
        target_air_humidity_pct=float(rng.uniform(45.0, 80.0)),
        target_co2_ppm=float(rng.uniform(550.0, 1300.0)),
        target_soil_moisture_pct=float(rng.uniform(38.0, 70.0)),
    )
    return Scenario(
        scenario_id=f"scenario-{index:04d}-seed-{seed}",
        seed=int(seed),
        initial_state=state,
        environment=environment,
        cultivation=cultivation,
        actuators=actuators,
        targets=targets,
        timestep_s=10.0,
        noise=SensorNoise(
            air_temperature_c=float(rng.uniform(0.02, 0.20)),
            air_humidity_pct=float(rng.uniform(0.08, 0.60)),
            co2_ppm=float(rng.uniform(1.0, 12.0)),
            soil_moisture_pct=float(rng.uniform(0.02, 0.30)),
            outside_temperature_c=float(rng.uniform(0.01, 0.15)),
            outside_humidity_pct=float(rng.uniform(0.05, 0.40)),
        ),
        response_lag=ResponseLag(
            heater_s=float(rng.uniform(15.0, 90.0)),
            fan_s=float(rng.uniform(2.0, 20.0)),
            humidifier_s=float(rng.uniform(8.0, 60.0)),
        ),
    )


def randomized_scenarios(config: DatasetConfig) -> tuple[Scenario, ...]:
    rng = np.random.default_rng(config.seed)
    seeds = rng.integers(1, np.iinfo(np.int32).max, size=config.scenario_count)
    return tuple(random_scenario(index, int(seed)) for index, seed in enumerate(seeds))


def controller_input_record(
    scenario: Scenario,
    sensor_values: Mapping[str, float],
    validity: Mapping[str, bool],
    previous: ControlAction,
) -> dict[str, object]:
    heater = scenario.actuators.heater
    fan = scenario.actuators.fan
    humidifier = scenario.actuators.humidifier
    pump = scenario.actuators.irrigation_pump
    return {
        "sensors": dict(sensor_values),
        "validity": {name: bool(validity[name]) for name in SENSOR_NAMES},
        "environment": asdict(scenario.environment),
        "cultivation": asdict(scenario.cultivation),
        "actuators": {
            "heater": {
                "available": heater.available,
                "max_power_w": heater.max_power_w,
                "efficiency": heater.efficiency,
                "control_type": heater.control_type,
            },
            "fan": {
                "available": fan.available,
                "max_airflow_m3_h": fan.max_airflow_m3_h,
                "minimum_command": fan.minimum_command,
                "control_type": fan.control_type,
            },
            "humidifier": {
                "available": humidifier.available,
                "max_output_g_h": humidifier.max_output_g_h,
                "control_type": humidifier.control_type,
            },
            "irrigation": {
                "available": pump.available,
                "flow_ml_s": pump.flow_ml_s,
                "maximum_pulse_s": pump.maximum_pulse_s,
                "control_type": pump.control_type,
                "minimum_interval_s": pump.minimum_interval_s,
            },
        },
        "targets": {
            "air_temperature_c": scenario.targets.target_air_temperature_c,
            "air_humidity_pct": scenario.targets.target_air_humidity_pct,
            "co2_ppm": scenario.targets.target_co2_ppm,
            "soil_moisture_pct": scenario.targets.target_soil_moisture_pct,
        },
        "previous": {
            "heater": previous.heater,
            "fan": previous.fan,
            "humidifier": previous.humidifier,
            "irrigation": previous.irrigation,
        },
    }


def generate_dataset(
    config: DatasetConfig,
    *,
    contract: Contract | None = None,
    teacher: RolloutTeacher | None = None,
) -> Dataset:
    contract = contract or load_contract()
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
            permanent_invalid = SENSOR_NAMES[scenario_index % len(SENSOR_NAMES)]

        for _ in range(config.steps_per_scenario):
            observation = simulator.observe(add_sensor_noise=True)
            sensor_values = observation.as_dict()
            validity = {name: True for name in SENSOR_NAMES}
            for name in SENSOR_NAMES:
                invalid = name == permanent_invalid or (
                    corruption_rng.random() < config.invalid_reading_probability
                )
                if invalid:
                    validity[name] = False
                    # Exercise both omitted readings and finite-but-obviously
                    # corrupt readings. NaN/Inf are intentionally not used as
                    # missing-value sentinels because firmware treats them as
                    # fail-safe input errors even when the validity mask is false.
                    if corruption_rng.random() < 0.5:
                        sensor_values.pop(name, None)
                    else:
                        sign = -1.0 if corruption_rng.random() < 0.5 else 1.0
                        sensor_values[name] = sign * 1.0e9

            feature_rows.append(
                contract.encode(
                    controller_input_record(
                        scenario, sensor_values, validity, simulator.previous_command
                    )
                )
            )
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
