# Generated-parity fixture generator for climate runtime.

from __future__ import annotations

import argparse
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np

from tools.ml.climate_input import ClimateTargets, MeasurementStatus
from tools.ml.climate_runtime import (
    ClimatePolicyMode,
    ClimateRuntimeConfig,
    ClimateRuntimeController,
    ClimateRuntimeStatus,
)
from tools.ml.climate_scenarios import ClimateProfile
from tools.ml.climate_simulator import (
    ClimateAction,
    ClimateActuatorCapabilities,
    ClimateResponseLag,
    ClimateScenario,
    ClimateState,
    Co2DoserCapabilities,
    CoolerCapabilities,
    DehumidifierCapabilities,
    ExhaustFanCapabilities,
    HeaterCapabilities,
    HumidifierCapabilities,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = PROJECT_ROOT / "tests" / "fixtures" / "climate_runtime_parity_generated.h"

SENSOR_NAMES = (
    "air_temperature_c",
    "relative_humidity_pct",
    "co2_ppm",
    "outside_temperature_c",
    "outside_humidity_pct",
)
INTERVENTION_BITS = {
    "unavailable:heater": 1 << 0,
    "unavailable:cooler": 1 << 1,
    "unavailable:exhaust_fan": 1 << 2,
    "unavailable:humidifier": 1 << 3,
    "unavailable:dehumidifier": 1 << 4,
    "unavailable:co2_doser": 1 << 5,
    "opposition:heater:cooler": 1 << 6,
    "opposition:humidifier:dehumidifier": 1 << 7,
    "required_sensor_unusable": 1 << 8,
    "co2_dosing_inhibited": 1 << 9,
    "high_temperature": 1 << 10,
    "low_temperature": 1 << 11,
    "high_humidity": 1 << 12,
    "high_co2": 1 << 13,
}
MODE_CODE = {
    ClimatePolicyMode.RULE: 0,
    ClimatePolicyMode.ML_SHADOW: 1,
    ClimatePolicyMode.ML_ACTIVE: 2,
}
STATUS_CODE = {
    ClimateRuntimeStatus.OK: 0,
    ClimateRuntimeStatus.ML_PROVIDER_MISSING: 1,
    ClimateRuntimeStatus.ML_INFERENCE_FAILED: 2,
    ClimateRuntimeStatus.ML_ACTIVE_NOT_ALLOWED: 3,
}


class _FixedModel:
    def __init__(self, values: tuple[float, ...]) -> None:
        self.values = np.asarray(values, dtype=np.float32)

    def predict(self, features: np.ndarray) -> np.ndarray:
        if features.shape != (44,):
            raise ValueError("golden model expected 44 features")
        return self.values.copy()


class _FailingModel:
    def predict(self, features: np.ndarray) -> np.ndarray:
        if features.shape != (44,):
            raise ValueError("golden model expected 44 features")
        raise RuntimeError("intentional golden inference failure")


@dataclass(frozen=True)
class CaseSpec:
    name: str
    mode: ClimatePolicyMode
    model_behavior: str = "none"
    model_output: tuple[float, ...] = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    allow_ml_active: bool = False
    state: ClimateState = field(
        default_factory=lambda: ClimateState(
            air_temperature_c=18.0,
            relative_humidity_pct=60.0,
            co2_ppm=500.0,
            outside_temperature_c=10.0,
            outside_humidity_pct=50.0,
            light_level=0.6,
        )
    )
    humidity_mode: str = "RH"
    targets: ClimateTargets = ClimateTargets(
        air_temperature_c=24.0,
        relative_humidity_pct=60.0,
        air_vpd_kpa=1.2,
        co2_enabled=True,
        co2_ppm=950.0,
    )
    capabilities: tuple[bool, ...] = (True, True, True, True, True, True)
    statuses: tuple[MeasurementStatus, ...] = (
        MeasurementStatus(),
        MeasurementStatus(),
        MeasurementStatus(),
        MeasurementStatus(),
        MeasurementStatus(),
    )
    previous: ClimateAction = ClimateAction(
        heater=0.1,
        cooler=0.2,
        exhaust_fan=0.3,
        humidifier=0.4,
        dehumidifier=0.5,
        co2_doser=0.6,
    )
    monotonic_ms: int = 120_000
    sensor_timeout_ms: int = 30_000
    timestep_s: float = 10.0


def _case_specs() -> tuple[CaseSpec, ...]:
    base = CaseSpec(name="rule_nominal", mode=ClimatePolicyMode.RULE)
    shadow_model = (0.20, 0.80, 0.70, 0.60, 0.40, 0.90)
    all_on = (1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
    return (
        base,
        replace(
            base,
            name="ml_shadow_opposition",
            mode=ClimatePolicyMode.ML_SHADOW,
            model_behavior="fixed",
            model_output=shadow_model,
        ),
        replace(
            base,
            name="ml_active_allowed",
            mode=ClimatePolicyMode.ML_ACTIVE,
            model_behavior="fixed",
            model_output=shadow_model,
            allow_ml_active=True,
        ),
        replace(
            base,
            name="ml_active_blocked",
            mode=ClimatePolicyMode.ML_ACTIVE,
            model_behavior="fixed",
            model_output=shadow_model,
        ),
        replace(
            base,
            name="ml_provider_missing",
            mode=ClimatePolicyMode.ML_SHADOW,
            model_behavior="none",
        ),
        replace(
            base,
            name="ml_inference_failed",
            mode=ClimatePolicyMode.ML_SHADOW,
            model_behavior="fail",
        ),
        replace(
            base,
            name="required_sensor_invalid",
            mode=ClimatePolicyMode.ML_SHADOW,
            model_behavior="fixed",
            model_output=all_on,
            statuses=(
                MeasurementStatus(valid=False, age_ms=0),
                MeasurementStatus(),
                MeasurementStatus(),
                MeasurementStatus(),
                MeasurementStatus(),
            ),
        ),
        replace(
            base,
            name="high_temperature",
            mode=ClimatePolicyMode.ML_SHADOW,
            model_behavior="fixed",
            model_output=all_on,
            state=replace(base.state, air_temperature_c=45.0),
        ),
        replace(
            base,
            name="high_humidity",
            mode=ClimatePolicyMode.ML_SHADOW,
            model_behavior="fixed",
            model_output=all_on,
            state=replace(base.state, relative_humidity_pct=96.0),
        ),
        replace(
            base,
            name="high_co2",
            mode=ClimatePolicyMode.ML_SHADOW,
            model_behavior="fixed",
            model_output=all_on,
            state=replace(base.state, co2_ppm=1_900.0),
        ),
        replace(
            base,
            name="unavailable_cooler",
            mode=ClimatePolicyMode.ML_SHADOW,
            model_behavior="fixed",
            model_output=shadow_model,
            capabilities=(True, False, True, True, True, True),
        ),
        replace(
            base,
            name="vpd_shadow",
            mode=ClimatePolicyMode.ML_SHADOW,
            model_behavior="fixed",
            model_output=(0.10, 0.20, 0.30, 0.75, 0.25, 0.40),
            state=ClimateState(
                air_temperature_c=26.0,
                relative_humidity_pct=35.0,
                co2_ppm=700.0,
                outside_temperature_c=18.0,
                outside_humidity_pct=70.0,
                light_level=0.8,
            ),
            humidity_mode="VPD",
            targets=ClimateTargets(
                air_temperature_c=25.0,
                relative_humidity_pct=60.0,
                air_vpd_kpa=1.2,
                co2_enabled=True,
                co2_ppm=1_000.0,
            ),
        ),
    )


def _scenario(spec: CaseSpec) -> ClimateScenario:
    heater, cooler, exhaust, humidifier, dehumidifier, co2 = spec.capabilities
    return ClimateScenario(
        scenario_id=f"parity-{spec.name}",
        seed=1,
        initial_state=spec.state,
        actuators=ClimateActuatorCapabilities(
            heater=HeaterCapabilities(available=heater, max_power_w=200.0, efficiency=0.9),
            cooler=CoolerCapabilities(available=cooler, max_cooling_w=220.0),
            exhaust_fan=ExhaustFanCapabilities(
                available=exhaust, max_airflow_m3_h=100.0, minimum_command=0.0
            ),
            humidifier=HumidifierCapabilities(
                available=humidifier, max_output_g_h=120.0, delivery_efficiency=0.6
            ),
            dehumidifier=DehumidifierCapabilities(
                available=dehumidifier, max_removal_g_h=100.0, delivery_efficiency=0.6
            ),
            co2_doser=Co2DoserCapabilities(available=co2, max_injection_ppm_s=2.0),
        ),
        response_lag=ClimateResponseLag(),
        timestep_s=spec.timestep_s,
    )


def _profile(spec: CaseSpec) -> ClimateProfile:
    return ClimateProfile(
        name=f"parity-{spec.name}",
        targets=spec.targets,
        humidity_control_mode=spec.humidity_mode,
        light_level=spec.state.light_level,
    )


def _model(spec: CaseSpec):
    if spec.model_behavior == "none":
        return None
    if spec.model_behavior == "fixed":
        return _FixedModel(spec.model_output)
    if spec.model_behavior == "fail":
        return _FailingModel()
    raise ValueError(f"unknown model behavior: {spec.model_behavior}")


def _status_map(spec: CaseSpec) -> dict[str, MeasurementStatus]:
    return dict(zip(SENSOR_NAMES, spec.statuses, strict=True))


def _action_values(action: ClimateAction | None) -> tuple[float, ...]:
    if action is None:
        return (0.0,) * 6
    return action.as_tuple()


def _intervention_mask(reasons: tuple[str, ...]) -> int:
    mask = 0
    for reason in reasons:
        try:
            mask |= INTERVENTION_BITS[reason]
        except KeyError as exc:
            raise ValueError(f"unmapped intervention reason: {reason}") from exc
    return mask


def _measurement_values(spec: CaseSpec) -> tuple[float, ...]:
    return (
        spec.state.air_temperature_c,
        spec.state.relative_humidity_pct,
        spec.state.co2_ppm,
        spec.state.outside_temperature_c,
        spec.state.outside_humidity_pct,
    )


def _result(spec: CaseSpec) -> dict[str, object]:
    runtime = ClimateRuntimeController(
        model=_model(spec),
        config=ClimateRuntimeConfig(
            mode=spec.mode,
            sensor_timeout_ms=spec.sensor_timeout_ms,
            allow_unqualified_ml_active=spec.allow_ml_active,
        ),
    )
    decision = runtime.step(
        _scenario(spec),
        spec.state,
        _profile(spec),
        previous_command=spec.previous,
        monotonic_ms=spec.monotonic_ms,
        status=_status_map(spec),
        timestep_s=spec.timestep_s,
    )
    return {
        "spec": spec,
        "status": STATUS_CODE[decision.status],
        "authoritative_ml": decision.authoritative_policy == "ml",
        "ml_evaluated": decision.ml_safe is not None,
        "rule_raw": _action_values(decision.rule_raw),
        "rule_arbitrated": _action_values(decision.rule_arbitrated),
        "rule_safe": _action_values(decision.rule_safe),
        "rule_arb_mask": _intervention_mask(decision.rule_arbitration_interventions),
        "rule_safety_mask": _intervention_mask(decision.rule_safety_interventions),
        "ml_raw": _action_values(decision.ml_raw),
        "ml_arbitrated": _action_values(decision.ml_arbitrated),
        "ml_safe": _action_values(decision.ml_safe),
        "ml_arb_mask": _intervention_mask(decision.ml_arbitration_interventions),
        "ml_safety_mask": _intervention_mask(decision.ml_safety_interventions),
        "has_ml_features": decision.ml_features is not None,
        "ml_features": decision.ml_features or (0.0,) * 44,
        "applied": _action_values(decision.applied),
        "effective_before": _action_values(decision.effective_before),
        "effective_after": _action_values(decision.effective_after),
    }


def _float(value: float) -> str:
    number = float(value)
    if not np.isfinite(number):
        raise ValueError("golden vectors must be finite")
    text = format(number, ".9g")
    if "e" not in text and "." not in text:
        text += ".0"
    return f"{text}F"


def _float_array(values) -> str:
    return "{{" + ", ".join(_float(value) for value in values) + "}}"


def _bool(value: bool) -> str:
    return "true" if value else "false"


def _bool_array(values) -> str:
    return "{{" + ", ".join(_bool(bool(value)) for value in values) + "}}"


def _uint_array(values) -> str:
    return "{{" + ", ".join(f"{int(value)}ULL" for value in values) + "}}"


def render_header() -> str:
    results = tuple(_result(spec) for spec in _case_specs())
    lines = [
        "#pragma once",
        "",
        "#include <array>",
        "#include <cstddef>",
        "#include <cstdint>",
        "",
        "namespace growbox::climate::parity_fixture {",
        "",
        "enum class ModelBehavior : std::uint8_t { None = 0U, Fixed = 1U, Fail = 2U };",
        "",
        "struct Case {",
        "  const char* name;",
        "  std::uint8_t mode;",
        "  bool allow_ml_active;",
        "  ModelBehavior model_behavior;",
        "  std::array<float, 6> model_output;",
        "  std::array<float, 5> measurement_values;",
        "  std::array<bool, 5> measurement_valid;",
        "  std::array<std::uint64_t, 5> measurement_age_ms;",
        "  bool humidity_vpd;",
        "  float target_temperature_c;",
        "  float target_humidity_pct;",
        "  float target_vpd_kpa;",
        "  bool co2_enabled;",
        "  float target_co2_ppm;",
        "  float light_level;",
        "  std::array<bool, 6> capabilities;",
        "  std::array<float, 6> previous;",
        "  std::uint64_t monotonic_ms;",
        "  std::uint64_t sensor_timeout_ms;",
        "  float timestep_s;",
        "  std::uint8_t expected_status;",
        "  bool expected_authoritative_ml;",
        "  bool expected_ml_evaluated;",
        "  std::array<float, 6> expected_rule_raw;",
        "  std::array<float, 6> expected_rule_arbitrated;",
        "  std::array<float, 6> expected_rule_safe;",
        "  std::uint32_t expected_rule_arb_mask;",
        "  std::uint32_t expected_rule_safety_mask;",
        "  std::array<float, 6> expected_ml_raw;",
        "  std::array<float, 6> expected_ml_arbitrated;",
        "  std::array<float, 6> expected_ml_safe;",
        "  std::uint32_t expected_ml_arb_mask;",
        "  std::uint32_t expected_ml_safety_mask;",
        "  bool expected_has_ml_features;",
        "  std::array<float, 44> expected_ml_features;",
        "  std::array<float, 6> expected_applied;",
        "  std::array<float, 6> expected_effective_before;",
        "  std::array<float, 6> expected_effective_after;",
        "};",
        "",
        f"inline constexpr std::array<Case, {len(results)}> kCases = {{{{",
    ]
    behavior_code = {
        "none": "ModelBehavior::None",
        "fixed": "ModelBehavior::Fixed",
        "fail": "ModelBehavior::Fail",
    }
    for result in results:
        spec = result["spec"]
        if not isinstance(spec, CaseSpec):
            raise TypeError("invalid golden spec")
        measurement_valid = tuple(status.valid for status in spec.statuses)
        measurement_age = tuple(status.age_ms for status in spec.statuses)
        lines.extend(
            [
                "  Case{",
                f'    "{spec.name}",',
                f"    {MODE_CODE[spec.mode]}U,",
                f"    {_bool(spec.allow_ml_active)},",
                f"    {behavior_code[spec.model_behavior]},",
                f"    {_float_array(spec.model_output)},",
                f"    {_float_array(_measurement_values(spec))},",
                f"    {_bool_array(measurement_valid)},",
                f"    {_uint_array(measurement_age)},",
                f"    {_bool(spec.humidity_mode == 'VPD')},",
                f"    {_float(spec.targets.air_temperature_c)},",
                f"    {_float(spec.targets.relative_humidity_pct)},",
                f"    {_float(spec.targets.air_vpd_kpa)},",
                f"    {_bool(spec.targets.co2_enabled)},",
                f"    {_float(spec.targets.co2_ppm)},",
                f"    {_float(spec.state.light_level)},",
                f"    {_bool_array(spec.capabilities)},",
                f"    {_float_array(spec.previous.as_tuple())},",
                f"    {spec.monotonic_ms}ULL,",
                f"    {spec.sensor_timeout_ms}ULL,",
                f"    {_float(spec.timestep_s)},",
                f"    {result['status']}U,",
                f"    {_bool(bool(result['authoritative_ml']))},",
                f"    {_bool(bool(result['ml_evaluated']))},",
                f"    {_float_array(result['rule_raw'])},",
                f"    {_float_array(result['rule_arbitrated'])},",
                f"    {_float_array(result['rule_safe'])},",
                f"    {result['rule_arb_mask']}U,",
                f"    {result['rule_safety_mask']}U,",
                f"    {_float_array(result['ml_raw'])},",
                f"    {_float_array(result['ml_arbitrated'])},",
                f"    {_float_array(result['ml_safe'])},",
                f"    {result['ml_arb_mask']}U,",
                f"    {result['ml_safety_mask']}U,",
                f"    {_bool(bool(result['has_ml_features']))},",
                f"    {_float_array(result['ml_features'])},",
                f"    {_float_array(result['applied'])},",
                f"    {_float_array(result['effective_before'])},",
                f"    {_float_array(result['effective_after'])},",
                "  },",
            ]
        )
    lines.extend(["}};", "", "} // namespace growbox::climate::parity_fixture", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    destination = args.output
    if not destination.is_absolute():
        destination = PROJECT_ROOT / destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_header(), encoding="utf-8")
    print(f"wrote {destination}")


if __name__ == "__main__":
    main()
