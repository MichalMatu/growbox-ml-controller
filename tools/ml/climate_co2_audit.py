"""Diagnostic closed-loop audit for CO2 dosing and exhaust interaction.

This is deliberately separate from the official acceptance benchmark. It compares
Rule, Teacher, the Stage 10 DAgger model and the Stage 11 distributed model on a
fresh diagnostic seed, and records how CO2 errors interact with exhaust commands.
"""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .climate_input import (
    ClimateInputConfig,
    ClimateTrendEstimator,
    MeasurementStatus,
    encode_climate_input,
)
from .climate_model_artifact import ClimatePortableModel, load_portable_model
from .climate_policy import (
    ClimateRulePolicy,
    apply_climate_safety,
    apply_ml_request_deadzone,
    arbitrate_climate_action,
)
from .climate_scenarios import ClimateTrainingEpisode, structured_training_episodes
from .climate_simulator import CLIMATE_OUTPUT_NAMES, ClimateAction, ClimateSimulator
from .climate_teacher import ClimateRolloutTeacher

AUDIT_POLICIES = ("rule", "teacher", "ml_stage10", "ml_stage11")
DEADZONE = 0.05


@dataclass(frozen=True)
class Co2AuditConfig:
    seed: int = 424_242
    scenarios_per_family: int = 4
    steps_per_scenario: int = 60
    workers: int = 4
    sensor_timeout_ms: int = 30_000


@dataclass(frozen=True)
class Co2EpisodeMetrics:
    policy: str
    family: str
    scenario_id: str
    cooler_available: bool
    co2_doser_available: bool
    co2_steps: int
    co2_mae_ppm: float
    co2_mae_exhaust_on_ppm: float
    co2_mae_exhaust_off_ppm: float
    exhaust_on_steps: int
    exhaust_off_steps: int
    exhaust_active_fraction: float
    raw_co2_above_deadzone_fraction: float
    requested_co2_active_fraction: float
    applied_co2_active_fraction: float
    exhaust_co2_overlap_fraction: float
    raw_co2_mean: float
    requested_co2_mean: float
    applied_co2_mean: float
    co2_dose_command_seconds: float
    exhaust_co2_product_mean: float
    co2_delta_exhaust_on_ppm: float
    co2_delta_exhaust_off_ppm: float


@dataclass(frozen=True)
class _AuditWork:
    episode: ClimateTrainingEpisode
    config: Co2AuditConfig
    stage10: ClimatePortableModel
    stage11: ClimatePortableModel


def _co2_enabled_episode(episode: ClimateTrainingEpisode) -> bool:
    return episode.first_profile.targets.co2_enabled or bool(
        episode.second_profile is not None and episode.second_profile.targets.co2_enabled
    )


def _ml_actions(
    simulator: ClimateSimulator,
    episode: ClimateTrainingEpisode,
    step: int,
    config: Co2AuditConfig,
    model: ClimatePortableModel,
    trends: ClimateTrendEstimator,
) -> tuple[ClimateAction, ClimateAction, dict[str, MeasurementStatus]]:
    profile = episode.profile_for_step(step, config.steps_per_scenario)
    simulator.set_light_level(profile.light_level)
    state = simulator.observe(add_sensor_noise=False)
    status = episode.forced_status_for_step(step, config.steps_per_scenario)
    trend_values = trends.update(
        state,
        int(round(simulator.elapsed_s * 1000.0)),
        status=status,
        sensor_timeout_ms=config.sensor_timeout_ms,
    )
    features = encode_climate_input(
        simulator.scenario,
        state,
        previous=simulator.previous_command,
        trends=trend_values,
        status=status,
        config=ClimateInputConfig(
            targets=profile.targets,
            humidity_control_mode=profile.humidity_control_mode,
            sensor_timeout_ms=config.sensor_timeout_ms,
        ),
    )
    prediction = model.predict(features)
    raw = ClimateAction.from_mapping(
        dict(zip(CLIMATE_OUTPUT_NAMES, (float(value) for value in prediction), strict=True))
    )
    return raw, apply_ml_request_deadzone(raw), status


def _policy_actions(
    policy: str,
    simulator: ClimateSimulator,
    episode: ClimateTrainingEpisode,
    step: int,
    config: Co2AuditConfig,
    model: ClimatePortableModel | None,
    trends: ClimateTrendEstimator,
) -> tuple[ClimateAction, ClimateAction, dict[str, MeasurementStatus]]:
    if policy.startswith("ml_"):
        if model is None:
            raise ValueError("ML audit policy requires a model")
        return _ml_actions(simulator, episode, step, config, model, trends)

    profile = episode.profile_for_step(step, config.steps_per_scenario)
    simulator.set_light_level(profile.light_level)
    state = simulator.observe(add_sensor_noise=False)
    status = episode.forced_status_for_step(step, config.steps_per_scenario)
    if policy == "rule":
        action = ClimateRulePolicy().choose(
            simulator.scenario,
            state,
            profile,
            status=status,
            sensor_timeout_ms=config.sensor_timeout_ms,
        )
    elif policy == "teacher":
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
    else:
        raise ValueError(f"unsupported CO2 audit policy: {policy!r}")
    return action, action, status


def _run_policy_episode(
    policy: str,
    episode: ClimateTrainingEpisode,
    config: Co2AuditConfig,
    model: ClimatePortableModel | None,
) -> Co2EpisodeMetrics:
    simulator = ClimateSimulator(episode.scenario)
    trends = ClimateTrendEstimator()
    co2_abs_sum = 0.0
    exhaust_on_error_sum = 0.0
    exhaust_off_error_sum = 0.0
    exhaust_on_steps = 0
    exhaust_off_steps = 0
    raw_active_steps = 0
    requested_active_steps = 0
    applied_active_steps = 0
    overlap_steps = 0
    raw_sum = 0.0
    requested_sum = 0.0
    applied_sum = 0.0
    dose_seconds = 0.0
    product_sum = 0.0
    delta_exhaust_on_sum = 0.0
    delta_exhaust_off_sum = 0.0
    co2_steps = 0

    for step in range(config.steps_per_scenario):
        profile = episode.profile_for_step(step, config.steps_per_scenario)
        simulator.set_light_level(profile.light_level)
        state = simulator.observe(add_sensor_noise=False)
        raw, requested, status = _policy_actions(
            policy,
            simulator,
            episode,
            step,
            config,
            model,
            trends,
        )
        arbitration = arbitrate_climate_action(requested, simulator.scenario)
        safety = apply_climate_safety(
            arbitration.action,
            simulator.scenario,
            state,
            profile,
            status=status,
            sensor_timeout_ms=config.sensor_timeout_ms,
        )
        applied = safety.action
        next_state = simulator.step(
            applied,
            add_sensor_noise=False,
            light_level=profile.light_level,
        )

        co2_status = status.get("co2_ppm", MeasurementStatus())
        if not profile.targets.co2_enabled or not co2_status.usable(
            state.co2_ppm, config.sensor_timeout_ms
        ):
            continue

        error = abs(state.co2_ppm - profile.targets.co2_ppm)
        co2_abs_sum += error
        co2_steps += 1
        exhaust_active = applied.exhaust_fan > DEADZONE
        raw_active_steps += int(raw.co2_doser > DEADZONE)
        requested_active_steps += int(requested.co2_doser > DEADZONE)
        applied_active_steps += int(applied.co2_doser > DEADZONE)
        overlap_steps += int(exhaust_active and applied.co2_doser > DEADZONE)
        raw_sum += raw.co2_doser
        requested_sum += requested.co2_doser
        applied_sum += applied.co2_doser
        dose_seconds += applied.co2_doser * simulator.scenario.timestep_s
        product_sum += applied.exhaust_fan * applied.co2_doser
        co2_delta = next_state.co2_ppm - state.co2_ppm
        if exhaust_active:
            exhaust_on_steps += 1
            exhaust_on_error_sum += error
            delta_exhaust_on_sum += co2_delta
        else:
            exhaust_off_steps += 1
            exhaust_off_error_sum += error
            delta_exhaust_off_sum += co2_delta

    def per_step(value: float) -> float:
        return value / co2_steps if co2_steps else 0.0

    return Co2EpisodeMetrics(
        policy=policy,
        family=episode.family,
        scenario_id=episode.scenario.scenario_id,
        cooler_available=episode.scenario.actuators.cooler.available,
        co2_doser_available=episode.scenario.actuators.co2_doser.available,
        co2_steps=co2_steps,
        co2_mae_ppm=per_step(co2_abs_sum),
        co2_mae_exhaust_on_ppm=(
            exhaust_on_error_sum / exhaust_on_steps if exhaust_on_steps else 0.0
        ),
        co2_mae_exhaust_off_ppm=(
            exhaust_off_error_sum / exhaust_off_steps if exhaust_off_steps else 0.0
        ),
        exhaust_on_steps=exhaust_on_steps,
        exhaust_off_steps=exhaust_off_steps,
        exhaust_active_fraction=per_step(exhaust_on_steps),
        raw_co2_above_deadzone_fraction=per_step(raw_active_steps),
        requested_co2_active_fraction=per_step(requested_active_steps),
        applied_co2_active_fraction=per_step(applied_active_steps),
        exhaust_co2_overlap_fraction=per_step(overlap_steps),
        raw_co2_mean=per_step(raw_sum),
        requested_co2_mean=per_step(requested_sum),
        applied_co2_mean=per_step(applied_sum),
        co2_dose_command_seconds=dose_seconds,
        exhaust_co2_product_mean=per_step(product_sum),
        co2_delta_exhaust_on_ppm=(
            delta_exhaust_on_sum / exhaust_on_steps if exhaust_on_steps else 0.0
        ),
        co2_delta_exhaust_off_ppm=(
            delta_exhaust_off_sum / exhaust_off_steps if exhaust_off_steps else 0.0
        ),
    )


def _run_episode(work: _AuditWork) -> tuple[Co2EpisodeMetrics, ...]:
    return (
        _run_policy_episode("rule", work.episode, work.config, None),
        _run_policy_episode("teacher", work.episode, work.config, None),
        _run_policy_episode("ml_stage10", work.episode, work.config, work.stage10),
        _run_policy_episode("ml_stage11", work.episode, work.config, work.stage11),
    )


def _aggregate(rows: list[Co2EpisodeMetrics]) -> dict[str, float | int]:
    co2_steps = sum(row.co2_steps for row in rows)
    on_steps = sum(row.exhaust_on_steps for row in rows)
    off_steps = sum(row.exhaust_off_steps for row in rows)
    if not co2_steps:
        return {"episodes": len(rows), "co2_steps": 0}

    def weighted(name: str) -> float:
        return sum(getattr(row, name) * row.co2_steps for row in rows) / co2_steps

    return {
        "episodes": len(rows),
        "co2_steps": co2_steps,
        "co2_mae_ppm": weighted("co2_mae_ppm"),
        "co2_mae_exhaust_on_ppm": (
            sum(row.co2_mae_exhaust_on_ppm * row.exhaust_on_steps for row in rows) / on_steps
            if on_steps
            else 0.0
        ),
        "co2_mae_exhaust_off_ppm": (
            sum(row.co2_mae_exhaust_off_ppm * row.exhaust_off_steps for row in rows) / off_steps
            if off_steps
            else 0.0
        ),
        "exhaust_active_fraction": on_steps / co2_steps,
        "raw_co2_above_deadzone_fraction": weighted("raw_co2_above_deadzone_fraction"),
        "requested_co2_active_fraction": weighted("requested_co2_active_fraction"),
        "applied_co2_active_fraction": weighted("applied_co2_active_fraction"),
        "exhaust_co2_overlap_fraction": weighted("exhaust_co2_overlap_fraction"),
        "raw_co2_mean": weighted("raw_co2_mean"),
        "requested_co2_mean": weighted("requested_co2_mean"),
        "applied_co2_mean": weighted("applied_co2_mean"),
        "co2_dose_command_seconds_per_episode": sum(row.co2_dose_command_seconds for row in rows)
        / len(rows),
        "exhaust_co2_product_mean": weighted("exhaust_co2_product_mean"),
        "co2_delta_exhaust_on_ppm": (
            sum(row.co2_delta_exhaust_on_ppm * row.exhaust_on_steps for row in rows) / on_steps
            if on_steps
            else 0.0
        ),
        "co2_delta_exhaust_off_ppm": (
            sum(row.co2_delta_exhaust_off_ppm * row.exhaust_off_steps for row in rows) / off_steps
            if off_steps
            else 0.0
        ),
    }


def _dataset_label_audit(path: Path, *, base_rows: int) -> dict[str, object]:
    with np.load(path, allow_pickle=False) as archive:
        labels = np.asarray(archive["labels"], dtype=np.float32)
        splits = np.asarray(archive["splits"])
        output_names = tuple(str(value) for value in archive["output_names"])
    co2_index = output_names.index("co2_doser")

    def stats(values: np.ndarray) -> dict[str, float | int]:
        active = values > DEADZONE
        active_values = values[active]
        return {
            "rows": int(len(values)),
            "mean": float(np.mean(values)) if len(values) else 0.0,
            "active_fraction": float(np.mean(active)) if len(values) else 0.0,
            "strong_fraction_ge_0_5": float(np.mean(values >= 0.5)) if len(values) else 0.0,
            "active_mean": float(np.mean(active_values)) if len(active_values) else 0.0,
            "active_median": float(np.median(active_values)) if len(active_values) else 0.0,
        }

    base = labels[:base_rows, co2_index]
    dagger = labels[base_rows:, co2_index]
    train = labels[splits == "train", co2_index]
    return {
        "total_rows": int(len(labels)),
        "base_rows": int(base_rows),
        "dagger_rows": int(len(labels) - base_rows),
        "base": stats(base),
        "dagger": stats(dagger),
        "train": stats(train),
    }


def run_audit(
    stage10: ClimatePortableModel,
    stage11: ClimatePortableModel,
    *,
    config: Co2AuditConfig,
    dataset_path: Path | None = None,
    base_rows: int = 7200,
) -> dict[str, object]:
    episodes = tuple(
        episode
        for episode in structured_training_episodes(
            scenarios_per_family=config.scenarios_per_family,
            seed=config.seed,
        )
        if _co2_enabled_episode(episode)
    )
    work = tuple(_AuditWork(episode, config, stage10, stage11) for episode in episodes)
    if config.workers <= 1:
        nested = [_run_episode(item) for item in work]
    else:
        with ProcessPoolExecutor(max_workers=config.workers) as executor:
            nested = list(executor.map(_run_episode, work))
    rows = [row for group in nested for row in group]

    aggregate = {
        policy: _aggregate([row for row in rows if row.policy == policy])
        for policy in AUDIT_POLICIES
    }
    families = {
        family: {
            policy: _aggregate(
                [row for row in rows if row.family == family and row.policy == policy]
            )
            for policy in AUDIT_POLICIES
        }
        for family in sorted({row.family for row in rows})
    }
    capability_groups: dict[str, dict[str, dict[str, float | int]]] = {}
    for label, predicate in (
        ("cooler_available", lambda row: row.cooler_available),
        ("cooler_unavailable", lambda row: not row.cooler_available),
        ("co2_doser_available", lambda row: row.co2_doser_available),
        ("co2_doser_unavailable", lambda row: not row.co2_doser_available),
    ):
        capability_groups[label] = {
            policy: _aggregate([row for row in rows if row.policy == policy and predicate(row)])
            for policy in AUDIT_POLICIES
        }

    payload: dict[str, object] = {
        "config": asdict(config),
        "policies": list(AUDIT_POLICIES),
        "episode_count": len(episodes),
        "aggregate": aggregate,
        "families": families,
        "capability_groups": capability_groups,
        "episodes": [asdict(row) for row in rows],
    }
    if dataset_path is not None:
        payload["dataset_labels"] = _dataset_label_audit(dataset_path, base_rows=base_rows)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage10-weights", type=Path, required=True)
    parser.add_argument("--stage10-metadata", type=Path, required=True)
    parser.add_argument("--stage11-weights", type=Path, required=True)
    parser.add_argument("--stage11-metadata", type=Path, required=True)
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--base-rows", type=int, default=7200)
    parser.add_argument("--seed", type=int, default=424_242)
    parser.add_argument("--scenarios-per-family", type=int, default=4)
    parser.add_argument("--steps", type=int, default=60)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = Co2AuditConfig(
        seed=args.seed,
        scenarios_per_family=args.scenarios_per_family,
        steps_per_scenario=args.steps,
        workers=args.workers,
    )
    report = run_audit(
        load_portable_model(args.stage10_weights, args.stage10_metadata),
        load_portable_model(args.stage11_weights, args.stage11_metadata),
        config=config,
        dataset_path=args.dataset,
        base_rows=args.base_rows,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for policy in AUDIT_POLICIES:
        metrics = report["aggregate"][policy]
        print(
            f"CO2_AUDIT policy={policy} mae={metrics.get('co2_mae_ppm', 0.0):.3f} "
            f"exhaust={metrics.get('exhaust_active_fraction', 0.0):.4f} "
            f"co2_active={metrics.get('applied_co2_active_fraction', 0.0):.4f} "
            f"raw_above_deadzone={metrics.get('raw_co2_above_deadzone_fraction', 0.0):.4f} "
            f"overlap={metrics.get('exhaust_co2_overlap_fraction', 0.0):.4f}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
