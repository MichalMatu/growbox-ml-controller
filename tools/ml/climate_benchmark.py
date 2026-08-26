"""Closed-loop climate-v6 benchmark for rule, teacher and persisted ML policy."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from typing import Literal

from .climate_input import (
    ClimateInputConfig,
    ClimateTrendEstimator,
    MeasurementStatus,
    air_vpd_kpa,
    encode_climate_input,
)
from .climate_model_artifact import ClimatePortableModel
from .climate_policy import (
    ClimateRulePolicy,
    apply_climate_safety,
    apply_ml_request_deadzone,
    arbitrate_climate_action,
    hard_limit_violations,
)
from .climate_scenarios import ClimateTrainingEpisode, structured_training_episodes
from .climate_simulator import CLIMATE_OUTPUT_NAMES, ClimateAction, ClimateSimulator
from .climate_teacher import ClimateRolloutTeacher

PolicyName = Literal["rule", "teacher", "ml"]
POLICY_NAMES: tuple[PolicyName, ...] = ("rule", "teacher", "ml")


@dataclass(frozen=True)
class ClimateBenchmarkConfig:
    seed: int = 91_273
    scenarios_per_family: int = 2
    steps_per_scenario: int = 60
    workers: int = 6
    sensor_timeout_ms: int = 30_000

    @classmethod
    def quick(cls, seed: int = 91_273) -> ClimateBenchmarkConfig:
        return cls(seed=seed, scenarios_per_family=1, steps_per_scenario=6, workers=1)

    @classmethod
    def full(cls, seed: int = 91_273, workers: int = 6) -> ClimateBenchmarkConfig:
        return cls(seed=seed, scenarios_per_family=2, steps_per_scenario=60, workers=workers)


@dataclass(frozen=True)
class EpisodeMetrics:
    policy: PolicyName
    family: str
    scenario_id: str
    steps: int
    tracking_cost: float
    outside_deadband_fraction: float
    temperature_mae_c: float
    rh_mae_pct: float
    rh_steps: int
    vpd_mae_kpa: float
    vpd_steps: int
    co2_mae_ppm: float
    co2_steps: int
    max_temperature_error_c: float
    max_rh_error_pct: float
    max_vpd_error_kpa: float
    max_co2_error_ppm: float
    switching_per_step: float
    actuator_effort_per_step: float
    co2_dose_command_seconds: float
    arbitration_intervention_fraction: float
    safety_intervention_fraction: float
    hard_limit_violation_fraction: float
    raw_opposition_fraction: float


@dataclass(frozen=True)
class AggregateMetrics:
    policy: PolicyName
    episodes: int
    steps: int
    tracking_cost: float
    outside_deadband_fraction: float
    temperature_mae_c: float
    rh_mae_pct: float
    vpd_mae_kpa: float
    co2_mae_ppm: float
    switching_per_step: float
    actuator_effort_per_step: float
    co2_dose_command_seconds_per_episode: float
    arbitration_intervention_fraction: float
    safety_intervention_fraction: float
    hard_limit_violation_fraction: float
    raw_opposition_fraction: float


@dataclass(frozen=True)
class BenchmarkVerdict:
    accepted: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ClimateBenchmarkReport:
    config: ClimateBenchmarkConfig
    aggregate: dict[str, AggregateMetrics]
    families: dict[str, dict[str, AggregateMetrics]]
    verdict: BenchmarkVerdict
    episodes: tuple[EpisodeMetrics, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "config": asdict(self.config),
            "aggregate": {name: asdict(metrics) for name, metrics in self.aggregate.items()},
            "families": {
                family: {name: asdict(metrics) for name, metrics in policies.items()}
                for family, policies in self.families.items()
            },
            "verdict": asdict(self.verdict),
            "episodes": [asdict(metrics) for metrics in self.episodes],
        }


@dataclass(frozen=True)
class _BenchmarkWork:
    policy: PolicyName
    episode: ClimateTrainingEpisode
    config: ClimateBenchmarkConfig
    model: ClimatePortableModel


def _status_for_step(
    episode: ClimateTrainingEpisode, step: int, total: int
) -> dict[str, MeasurementStatus]:
    return episode.forced_status_for_step(step, total)


def _raw_opposition(action: ClimateAction) -> bool:
    return (action.heater > 0.05 and action.cooler > 0.05) or (
        action.humidifier > 0.05 and action.dehumidifier > 0.05
    )


def _tracking_terms(
    state, profile, status: dict[str, MeasurementStatus], timeout_ms: int
) -> tuple[float, bool, float, float | None, float | None, float | None]:
    targets = profile.targets
    temperature_error = abs(state.air_temperature_c - targets.air_temperature_c)
    temp_excess = max(0.0, temperature_error - 0.3) / 5.0
    outside = temperature_error > 0.3

    rh_error: float | None = None
    vpd_error: float | None = None
    if profile.humidity_control_mode == "RH":
        rh_error = abs(state.relative_humidity_pct - targets.relative_humidity_pct)
        humidity_excess = max(0.0, rh_error - 2.0) / 20.0
        outside = outside or rh_error > 2.0
    else:
        vpd_error = abs(
            air_vpd_kpa(state.air_temperature_c, state.relative_humidity_pct) - targets.air_vpd_kpa
        )
        humidity_excess = max(0.0, vpd_error - 0.08) / 0.7
        outside = outside or vpd_error > 0.08

    co2_error: float | None = None
    co2_status = status.get("co2_ppm", MeasurementStatus())
    if targets.co2_enabled and co2_status.usable(state.co2_ppm, timeout_ms):
        co2_error = abs(state.co2_ppm - targets.co2_ppm)
        co2_excess = max(0.0, co2_error - 50.0) / 700.0
        outside = outside or co2_error > 50.0
    else:
        co2_excess = 0.0

    if profile.humidity_control_mode == "RH":
        humidity_weight = 3.0
    else:
        humidity_weight = 4.0
    tracking_cost = (
        6.0 * temp_excess * temp_excess
        + humidity_weight * humidity_excess * humidity_excess
        + 1.5 * co2_excess * co2_excess
    )
    return tracking_cost, outside, temperature_error, rh_error, vpd_error, co2_error


def _raw_action(
    policy: PolicyName,
    simulator: ClimateSimulator,
    episode: ClimateTrainingEpisode,
    step: int,
    config: ClimateBenchmarkConfig,
    model: ClimatePortableModel,
    trend_estimator: ClimateTrendEstimator,
) -> tuple[ClimateAction, dict[str, MeasurementStatus]]:
    profile = episode.profile_for_step(step, config.steps_per_scenario)
    simulator.set_light_level(profile.light_level)
    state = simulator.observe(add_sensor_noise=False)
    status = _status_for_step(episode, step, config.steps_per_scenario)

    if policy == "rule":
        action = ClimateRulePolicy().choose(
            simulator.scenario,
            state,
            profile,
            status=status,
            sensor_timeout_ms=config.sensor_timeout_ms,
        )
        return action, status

    if policy == "teacher":
        action = (
            ClimateRolloutTeacher()
            .choose(
                simulator,
                profile.targets,
                humidity_control_mode=profile.humidity_control_mode,
                status=status,
                sensor_timeout_ms=config.sensor_timeout_ms,
            )
            .action
        )
        return action, status

    if policy != "ml":
        raise ValueError(f"unsupported benchmark policy: {policy!r}")

    trends = trend_estimator.update(
        state,
        int(round(simulator.elapsed_s * 1000.0)),
        status=status,
        sensor_timeout_ms=config.sensor_timeout_ms,
    )
    input_config = ClimateInputConfig(
        targets=profile.targets,
        humidity_control_mode=profile.humidity_control_mode,
        sensor_timeout_ms=config.sensor_timeout_ms,
    )
    features = encode_climate_input(
        simulator.scenario,
        state,
        previous=simulator.previous_command,
        trends=trends,
        status=status,
        config=input_config,
    )
    prediction = model.predict(features)
    action = ClimateAction.from_mapping(
        dict(zip(CLIMATE_OUTPUT_NAMES, (float(value) for value in prediction), strict=True))
    )
    return apply_ml_request_deadzone(action), status


def _run_episode(work: _BenchmarkWork) -> EpisodeMetrics:
    policy = work.policy
    episode = work.episode
    config = work.config
    simulator = ClimateSimulator(episode.scenario)
    trend_estimator = ClimateTrendEstimator()
    previous_applied = ClimateAction()

    tracking_cost_sum = 0.0
    outside_steps = 0
    temp_abs_sum = 0.0
    rh_abs_sum = 0.0
    rh_steps = 0
    vpd_abs_sum = 0.0
    vpd_steps = 0
    co2_abs_sum = 0.0
    co2_steps = 0
    max_temp = 0.0
    max_rh = 0.0
    max_vpd = 0.0
    max_co2 = 0.0
    switching_sum = 0.0
    effort_sum = 0.0
    co2_seconds = 0.0
    arbitration_steps = 0
    safety_steps = 0
    hard_limit_steps = 0
    raw_opposition_steps = 0

    for step in range(config.steps_per_scenario):
        profile = episode.profile_for_step(step, config.steps_per_scenario)
        simulator.set_light_level(profile.light_level)
        state = simulator.observe(add_sensor_noise=False)
        status = _status_for_step(episode, step, config.steps_per_scenario)
        terms = _tracking_terms(state, profile, status, config.sensor_timeout_ms)
        tracking_cost, outside, temp_error, rh_error, vpd_error, co2_error = terms
        tracking_cost_sum += tracking_cost
        outside_steps += int(outside)
        temp_abs_sum += temp_error
        max_temp = max(max_temp, temp_error)
        if rh_error is not None:
            rh_abs_sum += rh_error
            rh_steps += 1
            max_rh = max(max_rh, rh_error)
        if vpd_error is not None:
            vpd_abs_sum += vpd_error
            vpd_steps += 1
            max_vpd = max(max_vpd, vpd_error)
        if co2_error is not None:
            co2_abs_sum += co2_error
            co2_steps += 1
            max_co2 = max(max_co2, co2_error)
        hard_limit_steps += int(bool(hard_limit_violations(state)))

        raw, status = _raw_action(
            policy,
            simulator,
            episode,
            step,
            config,
            work.model,
            trend_estimator,
        )
        raw_opposition_steps += int(_raw_opposition(raw))
        arbitration = arbitrate_climate_action(raw, simulator.scenario)
        arbitration_steps += int(bool(arbitration.interventions))
        safety = apply_climate_safety(
            arbitration.action,
            simulator.scenario,
            state,
            profile,
            status=status,
            sensor_timeout_ms=config.sensor_timeout_ms,
        )
        safety_steps += int(bool(safety.interventions))
        applied = safety.action
        switching_sum += sum(
            abs(a - b) for a, b in zip(applied.as_tuple(), previous_applied.as_tuple(), strict=True)
        ) / len(CLIMATE_OUTPUT_NAMES)
        effort_sum += sum(applied.as_tuple()) / len(CLIMATE_OUTPUT_NAMES)
        co2_seconds += applied.co2_doser * simulator.scenario.timestep_s
        simulator.step(applied, add_sensor_noise=False, light_level=profile.light_level)
        previous_applied = applied

    steps = config.steps_per_scenario
    return EpisodeMetrics(
        policy=policy,
        family=episode.family,
        scenario_id=episode.scenario.scenario_id,
        steps=steps,
        tracking_cost=tracking_cost_sum / steps,
        outside_deadband_fraction=outside_steps / steps,
        temperature_mae_c=temp_abs_sum / steps,
        rh_mae_pct=rh_abs_sum / rh_steps if rh_steps else 0.0,
        rh_steps=rh_steps,
        vpd_mae_kpa=vpd_abs_sum / vpd_steps if vpd_steps else 0.0,
        vpd_steps=vpd_steps,
        co2_mae_ppm=co2_abs_sum / co2_steps if co2_steps else 0.0,
        co2_steps=co2_steps,
        max_temperature_error_c=max_temp,
        max_rh_error_pct=max_rh,
        max_vpd_error_kpa=max_vpd,
        max_co2_error_ppm=max_co2,
        switching_per_step=switching_sum / steps,
        actuator_effort_per_step=effort_sum / steps,
        co2_dose_command_seconds=co2_seconds,
        arbitration_intervention_fraction=arbitration_steps / steps,
        safety_intervention_fraction=safety_steps / steps,
        hard_limit_violation_fraction=hard_limit_steps / steps,
        raw_opposition_fraction=raw_opposition_steps / steps,
    )


def _aggregate(policy: PolicyName, episodes: list[EpisodeMetrics]) -> AggregateMetrics:
    if not episodes:
        raise ValueError("cannot aggregate empty benchmark result")
    total_steps = sum(item.steps for item in episodes)
    rh_steps = sum(item.rh_steps for item in episodes)
    vpd_steps = sum(item.vpd_steps for item in episodes)
    co2_steps = sum(item.co2_steps for item in episodes)

    def weighted(name: str) -> float:
        return sum(getattr(item, name) * item.steps for item in episodes) / total_steps

    rh_mae = (
        sum(item.rh_mae_pct * item.rh_steps for item in episodes) / rh_steps if rh_steps else 0.0
    )
    vpd_mae = (
        sum(item.vpd_mae_kpa * item.vpd_steps for item in episodes) / vpd_steps
        if vpd_steps
        else 0.0
    )
    co2_mae = (
        sum(item.co2_mae_ppm * item.co2_steps for item in episodes) / co2_steps
        if co2_steps
        else 0.0
    )
    return AggregateMetrics(
        policy=policy,
        episodes=len(episodes),
        steps=total_steps,
        tracking_cost=weighted("tracking_cost"),
        outside_deadband_fraction=weighted("outside_deadband_fraction"),
        temperature_mae_c=weighted("temperature_mae_c"),
        rh_mae_pct=rh_mae,
        vpd_mae_kpa=vpd_mae,
        co2_mae_ppm=co2_mae,
        switching_per_step=weighted("switching_per_step"),
        actuator_effort_per_step=weighted("actuator_effort_per_step"),
        co2_dose_command_seconds_per_episode=sum(item.co2_dose_command_seconds for item in episodes)
        / len(episodes),
        arbitration_intervention_fraction=weighted("arbitration_intervention_fraction"),
        safety_intervention_fraction=weighted("safety_intervention_fraction"),
        hard_limit_violation_fraction=weighted("hard_limit_violation_fraction"),
        raw_opposition_fraction=weighted("raw_opposition_fraction"),
    )


def _verdict(aggregate: dict[str, AggregateMetrics]) -> BenchmarkVerdict:
    rule = aggregate["rule"]
    ml = aggregate["ml"]
    reasons: list[str] = []
    if ml.hard_limit_violation_fraction > 0.0:
        reasons.append("ML produced hard-limit violations")
    if ml.tracking_cost > rule.tracking_cost * 0.98:
        reasons.append("ML did not improve tracking cost by at least 2% versus rule baseline")
    if ml.outside_deadband_fraction > rule.outside_deadband_fraction + 0.03:
        reasons.append("ML spends materially more time outside target deadbands than rule baseline")
    if ml.switching_per_step > rule.switching_per_step * 1.75 + 0.02:
        reasons.append("ML switching is materially higher than rule baseline")
    if ml.safety_intervention_fraction > rule.safety_intervention_fraction + 0.02:
        reasons.append("ML needs materially more safety intervention than rule baseline")
    return BenchmarkVerdict(accepted=not reasons, reasons=tuple(reasons))


def run_closed_loop_benchmark(
    model: ClimatePortableModel,
    *,
    config: ClimateBenchmarkConfig | None = None,
) -> ClimateBenchmarkReport:
    config = config or ClimateBenchmarkConfig.full()
    if model.metadata.schema_version != 6:
        raise ValueError("closed-loop benchmark requires climate-v6 model")
    if model.metadata.output_names != CLIMATE_OUTPUT_NAMES:
        raise ValueError("portable model outputs do not match climate simulator")
    episodes = structured_training_episodes(
        scenarios_per_family=config.scenarios_per_family,
        seed=config.seed,
    )
    work = tuple(
        _BenchmarkWork(policy=policy, episode=episode, config=config, model=model)
        for episode in episodes
        for policy in POLICY_NAMES
    )
    if config.workers <= 1:
        results = tuple(_run_episode(item) for item in work)
    else:
        workers = min(config.workers, len(work))
        with ProcessPoolExecutor(max_workers=workers) as executor:
            results = tuple(executor.map(_run_episode, work, chunksize=1))

    aggregate = {
        policy: _aggregate(policy, [item for item in results if item.policy == policy])
        for policy in POLICY_NAMES
    }
    families: dict[str, dict[str, AggregateMetrics]] = {}
    for family in sorted({item.family for item in results}):
        families[family] = {
            policy: _aggregate(
                policy,
                [item for item in results if item.policy == policy and item.family == family],
            )
            for policy in POLICY_NAMES
        }
    return ClimateBenchmarkReport(
        config=config,
        aggregate=aggregate,
        families=families,
        verdict=_verdict(aggregate),
        episodes=results,
    )


def benchmark_summary(report: ClimateBenchmarkReport) -> tuple[str, ...]:
    lines: list[str] = []
    for policy in POLICY_NAMES:
        metrics = report.aggregate[policy]
        lines.append(
            f"{policy}: tracking={metrics.tracking_cost:.6f} outside={metrics.outside_deadband_fraction:.4f} "
            f"temp_mae={metrics.temperature_mae_c:.4f} rh_mae={metrics.rh_mae_pct:.4f} "
            f"vpd_mae={metrics.vpd_mae_kpa:.4f} co2_mae={metrics.co2_mae_ppm:.2f} "
            f"switching={metrics.switching_per_step:.5f} safety={metrics.safety_intervention_fraction:.4f} "
            f"hard_limits={metrics.hard_limit_violation_fraction:.4f}"
        )
    lines.append("CLOSED_LOOP_VERDICT=" + ("PASS" if report.verdict.accepted else "NO_GO"))
    for reason in report.verdict.reasons:
        lines.append("reason=" + reason)
    return tuple(lines)


__all__ = [
    "AggregateMetrics",
    "BenchmarkVerdict",
    "ClimateBenchmarkConfig",
    "ClimateBenchmarkReport",
    "EpisodeMetrics",
    "POLICY_NAMES",
    "benchmark_summary",
    "run_closed_loop_benchmark",
]
