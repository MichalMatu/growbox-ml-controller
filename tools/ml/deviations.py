"""Live tracking errors: sensors vs control targets.

Pure functions — no ML. Used by foresight, calibration diagnostics, NDJSON
analysis, and panel-facing summaries.

Error convention: positive means reading is above target.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .simulator import (
    MAX_POTS,
    ControlTargets,
    EnvironmentState,
    PotConfig,
    SequentialEnvironmentSimulator,
)

# Same normalizers as tools.ml.teacher.CostConfig (keep rollouts comparable).
NORM_AIR_TEMPERATURE_C = 10.0
NORM_AIR_HUMIDITY_PCT = 35.0
NORM_CO2_PPM = 1200.0
NORM_SOIL_MOISTURE_PCT = 50.0
NORM_SOIL_TEMPERATURE_C = 12.0
NORM_NUTRIENT_TEMPERATURE_C = 12.0


@dataclass(frozen=True)
class MetricDeviation:
    """One scalar tracking error."""

    key: str
    label: str
    reading: float | None
    target: float | None
    error: float | None
    normalized_error: float | None
    unit: str
    valid: bool = True

    @property
    def abs_error(self) -> float | None:
        if self.error is None:
            return None
        return abs(self.error)

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "reading": self.reading,
            "target": self.target,
            "error": self.error,
            "normalized_error": self.normalized_error,
            "abs_error": self.abs_error,
            "unit": self.unit,
            "valid": self.valid,
        }


@dataclass(frozen=True)
class TrackingReport:
    """Chamber + pot deviations at one timestep."""

    metrics: tuple[MetricDeviation, ...]
    rms_normalized: float
    max_abs_normalized: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "metrics": [m.as_dict() for m in self.metrics],
            "rms_normalized": self.rms_normalized,
            "max_abs_normalized": self.max_abs_normalized,
        }

    def by_key(self) -> dict[str, MetricDeviation]:
        return {m.key: m for m in self.metrics}


def _finite(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _metric(
    *,
    key: str,
    label: str,
    reading: Any,
    target: Any,
    scale: float,
    unit: str,
    valid: bool = True,
) -> MetricDeviation:
    r = _finite(reading)
    t = _finite(target)
    if r is None or t is None or not valid:
        return MetricDeviation(
            key=key,
            label=label,
            reading=r,
            target=t,
            error=None,
            normalized_error=None,
            unit=unit,
            valid=valid and r is not None and t is not None,
        )
    error = r - t
    return MetricDeviation(
        key=key,
        label=label,
        reading=r,
        target=t,
        error=error,
        normalized_error=error / scale if scale else error,
        unit=unit,
        valid=True,
    )


def compute_deviations(
    *,
    sensors: Mapping[str, Any],
    targets: Mapping[str, Any],
    validity: Mapping[str, Any] | None = None,
    pots: Sequence[Mapping[str, Any]] | None = None,
    pot_configs: Sequence[Any] | None = None,
) -> TrackingReport:
    """Compute tracking errors from plain dicts (decision NDJSON / panel state)."""
    validity = validity or {}
    metrics: list[MetricDeviation] = [
        _metric(
            key="air_temperature_c",
            label="Air temperature",
            reading=sensors.get("air_temperature_c"),
            target=targets.get("air_temperature_c")
            if "air_temperature_c" in targets
            else targets.get("target_air_temperature_c"),
            scale=NORM_AIR_TEMPERATURE_C,
            unit="°C",
            valid=validity.get("air_temperature_c", True) is not False,
        ),
        _metric(
            key="air_humidity_pct",
            label="Air humidity",
            reading=sensors.get("air_humidity_pct"),
            target=targets.get("air_humidity_pct")
            if "air_humidity_pct" in targets
            else targets.get("target_air_humidity_pct"),
            scale=NORM_AIR_HUMIDITY_PCT,
            unit="%",
            valid=validity.get("air_humidity_pct", True) is not False,
        ),
        _metric(
            key="co2_ppm",
            label="CO₂",
            reading=sensors.get("co2_ppm"),
            target=targets.get("co2_ppm")
            if "co2_ppm" in targets
            else targets.get("target_co2_ppm"),
            scale=NORM_CO2_PPM,
            unit="ppm",
            valid=validity.get("co2_ppm", True) is not False,
        ),
    ]

    nutrient_target = targets.get("nutrient_solution_temperature_c")
    if nutrient_target is None:
        nutrient_target = targets.get("target_nutrient_solution_temperature_c")
    if sensors.get("nutrient_solution_temperature_c") is not None or nutrient_target is not None:
        metrics.append(
            _metric(
                key="nutrient_solution_temperature_c",
                label="Nutrient solution T",
                reading=sensors.get("nutrient_solution_temperature_c"),
                target=nutrient_target,
                scale=NORM_NUTRIENT_TEMPERATURE_C,
                unit="°C",
                valid=validity.get("nutrient_solution_temperature_c", True) is not False,
            )
        )

    pot_list = list(pots or [])
    for index in range(min(MAX_POTS, max(len(pot_list), 0))):
        pot = pot_list[index] if index < len(pot_list) else {}
        pot_sensors = pot.get("sensors") if isinstance(pot.get("sensors"), Mapping) else pot
        pot_targets = pot.get("targets") if isinstance(pot.get("targets"), Mapping) else {}
        pot_validity = pot.get("validity") if isinstance(pot.get("validity"), Mapping) else {}
        available = pot.get("available", True)
        if available is False:
            continue
        cfg = None
        if pot_configs is not None and index < len(pot_configs):
            cfg = pot_configs[index]
            if hasattr(cfg, "available") and not cfg.available:
                continue

        soil_m_target = pot_targets.get("soil_moisture_pct")
        if soil_m_target is None and cfg is not None:
            soil_m_target = getattr(cfg, "target_soil_moisture_pct", None)
        soil_t_target = pot_targets.get("soil_temperature_c")
        if soil_t_target is None and cfg is not None:
            soil_t_target = getattr(cfg, "target_soil_temperature_c", None)

        metrics.append(
            _metric(
                key=f"pot_{index + 1}_soil_moisture_pct",
                label=f"Pot {index + 1} soil moisture",
                reading=pot_sensors.get("soil_moisture_pct")
                if isinstance(pot_sensors, Mapping)
                else None,
                target=soil_m_target,
                scale=NORM_SOIL_MOISTURE_PCT,
                unit="%",
                valid=pot_validity.get("soil_moisture_pct", True) is not False,
            )
        )
        if soil_t_target is not None or (
            isinstance(pot_sensors, Mapping) and pot_sensors.get("soil_temperature_c") is not None
        ):
            metrics.append(
                _metric(
                    key=f"pot_{index + 1}_soil_temperature_c",
                    label=f"Pot {index + 1} soil temperature",
                    reading=pot_sensors.get("soil_temperature_c")
                    if isinstance(pot_sensors, Mapping)
                    else None,
                    target=soil_t_target,
                    scale=NORM_SOIL_TEMPERATURE_C,
                    unit="°C",
                    valid=pot_validity.get("soil_temperature_c", True) is not False,
                )
            )

    return _finalize(metrics)


def deviations_from_state(
    state: EnvironmentState,
    targets: ControlTargets,
    *,
    pots: Sequence[PotConfig] | None = None,
    nutrient_valid: bool = True,
) -> TrackingReport:
    """Deviations from an in-memory simulator state."""
    sensors = {
        "air_temperature_c": state.air_temperature_c,
        "air_humidity_pct": state.air_humidity_pct,
        "co2_ppm": state.co2_ppm,
        "nutrient_solution_temperature_c": state.nutrient_solution_temperature_c,
    }
    target_map = {
        "air_temperature_c": targets.target_air_temperature_c,
        "air_humidity_pct": targets.target_air_humidity_pct,
        "co2_ppm": targets.target_co2_ppm,
        "nutrient_solution_temperature_c": targets.target_nutrient_solution_temperature_c,
    }
    pot_payloads: list[dict[str, Any]] = []
    for index, pot_state in enumerate(state.pots):
        pot_cfg = pots[index] if pots is not None and index < len(pots) else None
        pot_payloads.append(
            {
                "available": True if pot_cfg is None else pot_cfg.available,
                "sensors": {
                    "soil_moisture_pct": pot_state.soil_moisture_pct,
                    "soil_temperature_c": pot_state.soil_temperature_c,
                },
                "targets": {
                    "soil_moisture_pct": getattr(pot_cfg, "target_soil_moisture_pct", None)
                    if pot_cfg
                    else None,
                    "soil_temperature_c": getattr(pot_cfg, "target_soil_temperature_c", None)
                    if pot_cfg
                    else None,
                },
                "validity": {
                    "soil_moisture_pct": getattr(pot_cfg, "soil_moisture_valid", True)
                    if pot_cfg
                    else True,
                    "soil_temperature_c": getattr(pot_cfg, "soil_temperature_valid", True)
                    if pot_cfg
                    else True,
                },
            }
        )
    return compute_deviations(
        sensors=sensors,
        targets=target_map,
        validity={"nutrient_solution_temperature_c": nutrient_valid},
        pots=pot_payloads,
        pot_configs=pots,
    )


def deviations_from_simulator(simulator: SequentialEnvironmentSimulator) -> TrackingReport:
    return deviations_from_state(
        simulator.state,
        simulator.scenario.targets,
        pots=simulator.scenario.pots,
        nutrient_valid=simulator.scenario.validity.nutrient_solution_temperature_c,
    )


def deviations_from_decision(record: Mapping[str, Any]) -> TrackingReport:
    """Extract deviations from a firmware/panel decision NDJSON object."""
    sensors = record.get("sensors") if isinstance(record.get("sensors"), Mapping) else {}
    targets = record.get("targets") if isinstance(record.get("targets"), Mapping) else {}
    validity = record.get("validity") if isinstance(record.get("validity"), Mapping) else {}
    pots = record.get("pots") if isinstance(record.get("pots"), Sequence) else None
    return compute_deviations(sensors=sensors, targets=targets, validity=validity, pots=pots)


def _finalize(metrics: list[MetricDeviation]) -> TrackingReport:
    norms = [m.normalized_error for m in metrics if m.normalized_error is not None]
    if not norms:
        return TrackingReport(metrics=tuple(metrics), rms_normalized=0.0, max_abs_normalized=0.0)
    rms = math.sqrt(sum(n * n for n in norms) / len(norms))
    max_abs = max(abs(n) for n in norms)
    return TrackingReport(
        metrics=tuple(metrics),
        rms_normalized=float(rms),
        max_abs_normalized=float(max_abs),
    )
