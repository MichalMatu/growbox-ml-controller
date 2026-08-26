"""Python-side climate-v6 controller input and trend semantics.

Training and simulation must encode exactly the same 38 features as the C++
``ClimateFeatureEncoder`` used by firmware. This module deliberately does not
reuse the historical v4 controller-input bridge.
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np

from .climate_simulator import ClimateAction, ClimateScenario, ClimateState
from .contract import Contract, load_contract
from .physics.psychrometrics import sat_vapour_pressure_pa

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLIMATE_V6_CONTRACT_PATH = PROJECT_ROOT / "schemas" / "environment-controller.v6.json"
DEFAULT_SENSOR_TIMEOUT_MS = 30_000
TREND_WINDOW_MS = 60_000
TREND_MINIMUM_SAMPLE_SPACING_MS = 5_000
TREND_MINIMUM_SPAN_MS = 10_000
TREND_MAXIMUM_SAMPLES = 16

SENSOR_NAMES = (
    "air_temperature_c",
    "relative_humidity_pct",
    "co2_ppm",
    "outside_temperature_c",
    "outside_humidity_pct",
)

HumidityControlMode = Literal["RH", "VPD"]


@dataclass(frozen=True)
class MeasurementStatus:
    valid: bool = True
    age_ms: int = 0

    def fresh(self, timeout_ms: int) -> bool:
        return 0 <= int(self.age_ms) <= int(timeout_ms)

    def usable(self, value: float, timeout_ms: int) -> bool:
        return bool(self.valid) and self.fresh(timeout_ms) and math.isfinite(float(value))


@dataclass(frozen=True)
class TrendValue:
    rate_per_min: float = 0.0
    available: bool = False


@dataclass(frozen=True)
class ClimateTrends:
    temperature: TrendValue = field(default_factory=TrendValue)
    humidity: TrendValue = field(default_factory=TrendValue)
    co2: TrendValue = field(default_factory=TrendValue)


@dataclass(frozen=True)
class ClimateTargets:
    air_temperature_c: float = 24.0
    relative_humidity_pct: float = 60.0
    air_vpd_kpa: float = 1.2
    co2_enabled: bool = False
    co2_ppm: float = 800.0


@dataclass(frozen=True)
class ClimateInputConfig:
    targets: ClimateTargets = field(default_factory=ClimateTargets)
    humidity_control_mode: HumidityControlMode = "RH"
    sensor_timeout_ms: int = DEFAULT_SENSOR_TIMEOUT_MS


class _TrendChannel:
    def __init__(self) -> None:
        self.samples: deque[tuple[int, float]] = deque(maxlen=TREND_MAXIMUM_SAMPLES)

    def reset(self) -> None:
        self.samples.clear()

    def update(self, value: float, source_timestamp_ms: int) -> TrendValue:
        timestamp = int(source_timestamp_ms)
        if self.samples and timestamp < self.samples[-1][0]:
            self.reset()

        while self.samples and timestamp - self.samples[0][0] > TREND_WINDOW_MS:
            self.samples.popleft()

        if self.samples:
            last_timestamp, _ = self.samples[-1]
            if timestamp == last_timestamp:
                self.samples[-1] = (timestamp, float(value))
                return self.estimate()
            if timestamp - last_timestamp < TREND_MINIMUM_SAMPLE_SPACING_MS:
                return self.estimate()

        self.samples.append((timestamp, float(value)))
        return self.estimate()

    def estimate(self) -> TrendValue:
        if len(self.samples) < 2:
            return TrendValue()
        first_timestamp = self.samples[0][0]
        span_ms = self.samples[-1][0] - first_timestamp
        if span_ms < TREND_MINIMUM_SPAN_MS:
            return TrendValue()

        x = np.asarray(
            [(timestamp - first_timestamp) / 60_000.0 for timestamp, _ in self.samples],
            dtype=np.float64,
        )
        y = np.asarray([value for _, value in self.samples], dtype=np.float64)
        x_mean = float(np.mean(x))
        y_mean = float(np.mean(y))
        denominator = float(np.sum((x - x_mean) ** 2))
        if abs(denominator) < 1.0e-12:
            return TrendValue()
        slope = float(np.sum((x - x_mean) * (y - y_mean)) / denominator)
        if not math.isfinite(slope):
            return TrendValue()
        return TrendValue(rate_per_min=slope, available=True)


class ClimateTrendEstimator:
    """Mirror the C++ 60 s least-squares trend estimator."""

    def __init__(self) -> None:
        self._temperature = _TrendChannel()
        self._humidity = _TrendChannel()
        self._co2 = _TrendChannel()
        self._last_monotonic_ms: int | None = None

    def reset(self) -> None:
        self._temperature.reset()
        self._humidity.reset()
        self._co2.reset()
        self._last_monotonic_ms = None

    def update(
        self,
        state: ClimateState,
        monotonic_ms: int,
        *,
        status: Mapping[str, MeasurementStatus] | None = None,
        sensor_timeout_ms: int = DEFAULT_SENSOR_TIMEOUT_MS,
    ) -> ClimateTrends:
        now = int(monotonic_ms)
        if self._last_monotonic_ms is not None and now < self._last_monotonic_ms:
            self.reset()
        self._last_monotonic_ms = now
        statuses = status or {}

        def channel_update(name: str, value: float, channel: _TrendChannel) -> TrendValue:
            sensor_status = statuses.get(name, MeasurementStatus())
            age_ms = int(sensor_status.age_ms)
            if (
                not sensor_status.valid
                or age_ms < 0
                or age_ms > sensor_timeout_ms
                or age_ms > now
                or not math.isfinite(float(value))
            ):
                return TrendValue()
            return channel.update(float(value), now - age_ms)

        return ClimateTrends(
            temperature=channel_update(
                "air_temperature_c", state.air_temperature_c, self._temperature
            ),
            humidity=channel_update(
                "relative_humidity_pct", state.relative_humidity_pct, self._humidity
            ),
            co2=channel_update("co2_ppm", state.co2_ppm, self._co2),
        )


def air_vpd_kpa(temperature_c: float, relative_humidity_pct: float) -> float:
    rh = min(100.0, max(0.0, float(relative_humidity_pct)))
    return sat_vapour_pressure_pa(float(temperature_c)) / 1000.0 * (1.0 - rh / 100.0)


def _feature_defaults(contract: Contract) -> dict[str, float]:
    return {feature.name: feature.default for feature in contract.features}


def climate_controller_record(
    scenario: ClimateScenario,
    state: ClimateState,
    *,
    previous: ClimateAction | None = None,
    trends: ClimateTrends | None = None,
    status: Mapping[str, MeasurementStatus] | None = None,
    config: ClimateInputConfig | None = None,
    contract: Contract | None = None,
) -> dict[str, object]:
    """Build a v6 record with C++-equivalent fallback semantics."""

    contract = contract or load_contract(CLIMATE_V6_CONTRACT_PATH)
    if contract.schema_version != 6:
        raise ValueError("climate controller record requires schema v6")
    defaults = _feature_defaults(contract)
    previous = previous or ClimateAction()
    trends = trends or ClimateTrends()
    config = config or ClimateInputConfig()
    statuses = status or {}
    timeout = int(config.sensor_timeout_ms)
    if timeout < 0:
        raise ValueError("sensor_timeout_ms must be non-negative")

    values = {
        "air_temperature_c": float(state.air_temperature_c),
        "relative_humidity_pct": float(state.relative_humidity_pct),
        "co2_ppm": float(state.co2_ppm),
        "outside_temperature_c": float(state.outside_temperature_c),
        "outside_humidity_pct": float(state.outside_humidity_pct),
    }
    measurements: dict[str, dict[str, object]] = {}
    usable: dict[str, bool] = {}
    for name in SENSOR_NAMES:
        sensor_status = statuses.get(name, MeasurementStatus())
        fresh = sensor_status.fresh(timeout)
        value_usable = sensor_status.usable(values[name], timeout)
        usable[name] = value_usable
        measurements[name] = {
            "value": values[name] if value_usable else defaults[name],
            "valid": bool(sensor_status.valid and math.isfinite(values[name])),
            "fresh": fresh,
            "age_ms": max(0, int(sensor_status.age_ms)),
        }

    vpd_usable = usable["air_temperature_c"] and usable["relative_humidity_pct"]
    vpd = (
        air_vpd_kpa(state.air_temperature_c, state.relative_humidity_pct)
        if vpd_usable
        else defaults["air_vpd_kpa"]
    )

    def trend_value(name: str, value: TrendValue, source_name: str) -> float:
        if usable[source_name] and value.available and math.isfinite(value.rate_per_min):
            return float(value.rate_per_min)
        return defaults[name]

    caps = scenario.actuators
    targets = config.targets
    return {
        "measurements": measurements,
        "derived": {"air_vpd_kpa": vpd},
        "control": {"humidity_control_mode": config.humidity_control_mode},
        "targets": {
            "air_temperature_c": targets.air_temperature_c,
            "relative_humidity_pct": targets.relative_humidity_pct,
            "air_vpd_kpa": targets.air_vpd_kpa,
            "co2_enabled": targets.co2_enabled,
            "co2_ppm": targets.co2_ppm,
        },
        "schedule": {"light_level": state.light_level},
        "trends": {
            "temperature_rate_c_min": trend_value(
                "temperature_rate_c_min", trends.temperature, "air_temperature_c"
            ),
            "humidity_rate_pct_min": trend_value(
                "humidity_rate_pct_min", trends.humidity, "relative_humidity_pct"
            ),
            "co2_rate_ppm_min": trend_value("co2_rate_ppm_min", trends.co2, "co2_ppm"),
        },
        "previous": previous.as_dict(),
        "capabilities": {
            "heater": {"available": caps.heater.available},
            "cooler": {"available": caps.cooler.available},
            "exhaust_fan": {"available": caps.exhaust_fan.available},
            "humidifier": {"available": caps.humidifier.available},
            "dehumidifier": {"available": caps.dehumidifier.available},
            "co2_doser": {"available": caps.co2_doser.available},
        },
    }


def encode_climate_input(
    scenario: ClimateScenario,
    state: ClimateState,
    *,
    previous: ClimateAction | None = None,
    trends: ClimateTrends | None = None,
    status: Mapping[str, MeasurementStatus] | None = None,
    config: ClimateInputConfig | None = None,
    contract: Contract | None = None,
) -> np.ndarray:
    contract = contract or load_contract(CLIMATE_V6_CONTRACT_PATH)
    record = climate_controller_record(
        scenario,
        state,
        previous=previous,
        trends=trends,
        status=status,
        config=config,
        contract=contract,
    )
    encoded = contract.encode(record)
    if encoded.shape != (38,):
        raise ValueError(f"expected 38 climate features, got {encoded.shape}")
    return encoded


__all__ = [
    "CLIMATE_V6_CONTRACT_PATH",
    "DEFAULT_SENSOR_TIMEOUT_MS",
    "ClimateInputConfig",
    "ClimateTargets",
    "ClimateTrendEstimator",
    "ClimateTrends",
    "HumidityControlMode",
    "MeasurementStatus",
    "TrendValue",
    "air_vpd_kpa",
    "climate_controller_record",
    "encode_climate_input",
]
