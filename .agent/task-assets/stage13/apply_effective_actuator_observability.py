#!/usr/bin/env python3
"""Apply Stage 13 effective-actuator observability migration."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path.cwd()


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one occurrence of {old!r}, found {count}")
    write(path, text.replace(old, new, 1))


schema_path = ROOT / "schemas/environment-controller.v6.json"
schema = json.loads(schema_path.read_text(encoding="utf-8"))
features = schema["model"]["features"]
expected_previous = [
    "previous_heater",
    "previous_cooler",
    "previous_exhaust_fan",
    "previous_humidifier",
    "previous_dehumidifier",
    "previous_co2_doser",
]
expected_caps = [
    "heater_available",
    "cooler_available",
    "exhaust_fan_available",
    "humidifier_available",
    "dehumidifier_available",
    "co2_doser_available",
]
if schema["model"]["feature_count"] != 38 or len(features) != 38:
    raise RuntimeError("Stage 13 requires the frozen 38-feature climate-v6 baseline")
if [item["name"] for item in features[26:32]] != expected_previous:
    raise RuntimeError("Unexpected previous-command feature order")
if [item["name"] for item in features[32:38]] != expected_caps:
    raise RuntimeError("Unexpected capability feature order")
roles = ("heater", "cooler", "exhaust_fan", "humidifier", "dehumidifier", "co2_doser")
effective_features = [
    {
        "name": f"estimated_effective_{role}",
        "path": f"estimated_effective.{role}",
        "type": "number",
        "unit": "ratio",
        "minimum": 0.0,
        "maximum": 1.0,
        "default": 0.0,
    }
    for role in roles
]
schema["model"]["features"] = features[:32] + effective_features + features[32:]
schema["model"]["feature_count"] = 44
schema_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

replace_once(
    "tools/schema/generate_climate_contract.py",
    'if model.get("feature_count") != 38 or len(features) != 38:\n        raise ValueError("climate v6 must contain exactly 38 features")',
    'if model.get("feature_count") != 44 or len(features) != 44:\n        raise ValueError("climate v6 must contain exactly 44 features")',
)

replace_once(
    "lib/environment_control/src/climate/ClimateTypes.h",
    "struct PreviousClimateActions {\n  float heater = 0.0F, cooler = 0.0F, exhaust_fan = 0.0F, humidifier = 0.0F, dehumidifier = 0.0F,\n        co2_doser = 0.0F;\n};\n",
    "struct PreviousClimateActions {\n  float heater = 0.0F, cooler = 0.0F, exhaust_fan = 0.0F, humidifier = 0.0F, dehumidifier = 0.0F,\n        co2_doser = 0.0F;\n};\nstruct EstimatedEffectiveClimateActions {\n  float heater = 0.0F, cooler = 0.0F, exhaust_fan = 0.0F, humidifier = 0.0F, dehumidifier = 0.0F,\n        co2_doser = 0.0F;\n};\n",
)
replace_once(
    "lib/environment_control/src/climate/ClimateTypes.h",
    "  PreviousClimateActions previous{};\n  ClimateCapabilities capabilities{};\n",
    "  PreviousClimateActions previous{};\n  EstimatedEffectiveClimateActions estimated_effective{};\n  ClimateCapabilities capabilities{};\n",
)

replace_once(
    "lib/environment_control/src/climate/ClimateFeatureEncoder.cpp",
    "  w.write(contract::FeatureIndex::PreviousCo2Doser, input.previous.co2_doser);\n  w.flag(contract::FeatureIndex::HeaterAvailable, input.capabilities.heater);\n",
    "  w.write(contract::FeatureIndex::PreviousCo2Doser, input.previous.co2_doser);\n  w.write(contract::FeatureIndex::EstimatedEffectiveHeater, input.estimated_effective.heater);\n  w.write(contract::FeatureIndex::EstimatedEffectiveCooler, input.estimated_effective.cooler);\n  w.write(contract::FeatureIndex::EstimatedEffectiveExhaustFan, input.estimated_effective.exhaust_fan);\n  w.write(contract::FeatureIndex::EstimatedEffectiveHumidifier, input.estimated_effective.humidifier);\n  w.write(contract::FeatureIndex::EstimatedEffectiveDehumidifier, input.estimated_effective.dehumidifier);\n  w.write(contract::FeatureIndex::EstimatedEffectiveCo2Doser, input.estimated_effective.co2_doser);\n  w.flag(contract::FeatureIndex::HeaterAvailable, input.capabilities.heater);\n",
)

estimator_header = r'''#pragma once
#include "ClimateTypes.h"
#include <algorithm>
#include <cmath>
namespace growbox::climate {
struct ClimateActuatorLagSeconds {
  float heater = 35.0F;
  float cooler = 45.0F;
  float exhaust_fan = 8.0F;
  float humidifier = 20.0F;
  float dehumidifier = 20.0F;
  float co2_doser = 0.0F;
};
class ClimateActuatorStateEstimator {
public:
  void reset() noexcept { state_ = {}; }
  const EstimatedEffectiveClimateActions& state() const noexcept { return state_; }
  EstimatedEffectiveClimateActions update(const ClimatePolicyRequest& requested, float timestep_s,
                                          const ClimateCapabilities& capabilities,
                                          ClimateActuatorLagSeconds lag = {}) noexcept {
    if (!std::isfinite(timestep_s) || timestep_s <= 0.0F) {
      return state_;
    }
    const auto bounded = [](float value) noexcept {
      if (!std::isfinite(value)) {
        return 0.0F;
      }
      return std::clamp(value, 0.0F, 1.0F);
    };
    const float heater = capabilities.heater ? bounded(requested.heater) : 0.0F;
    const float cooler = capabilities.cooler ? bounded(requested.cooler) : 0.0F;
    const float exhaust = capabilities.exhaust_fan ? bounded(requested.exhaust_fan) : 0.0F;
    const float humidifier = capabilities.humidifier ? bounded(requested.humidifier) : 0.0F;
    const float dehumidifier = capabilities.dehumidifier ? bounded(requested.dehumidifier) : 0.0F;
    const float co2 = capabilities.co2_doser ? bounded(requested.co2_doser) : 0.0F;
    state_.heater = advance(state_.heater, heater, timestep_s, lag.heater);
    state_.cooler = advance(state_.cooler, cooler, timestep_s, lag.cooler);
    state_.exhaust_fan = advance(state_.exhaust_fan, exhaust, timestep_s, lag.exhaust_fan);
    state_.humidifier = advance(state_.humidifier, humidifier, timestep_s, lag.humidifier);
    state_.dehumidifier = advance(state_.dehumidifier, dehumidifier, timestep_s, lag.dehumidifier);
    state_.co2_doser = advance(state_.co2_doser, co2, timestep_s, lag.co2_doser);
    return state_;
  }
private:
  static float advance(float previous, float requested, float dt, float time_constant) noexcept {
    if (!std::isfinite(time_constant) || time_constant <= 0.0F) {
      return requested;
    }
    const float alpha = 1.0F - std::exp(-dt / time_constant);
    return previous + alpha * (requested - previous);
  }
  EstimatedEffectiveClimateActions state_{};
};
} // namespace growbox::climate
'''
header_path = ROOT / "lib/environment_control/src/climate/ClimateActuatorStateEstimator.h"
if header_path.exists():
    raise RuntimeError(f"Refusing to overwrite existing {header_path}")
header_path.write_text(estimator_header, encoding="utf-8")

climate_input_path = "tools/ml/climate_input.py"
text = read(climate_input_path)
text = text.replace("exactly the same 38 features", "exactly the same 44 features", 1)
anchor = '''@dataclass(frozen=True)\nclass ClimateInputConfig:\n    targets: ClimateTargets = field(default_factory=ClimateTargets)\n    humidity_control_mode: HumidityControlMode = "RH"\n    sensor_timeout_ms: int = DEFAULT_SENSOR_TIMEOUT_MS\n\n\n'''
estimator_py = '''@dataclass(frozen=True)\nclass ClimateInputConfig:\n    targets: ClimateTargets = field(default_factory=ClimateTargets)\n    humidity_control_mode: HumidityControlMode = "RH"\n    sensor_timeout_ms: int = DEFAULT_SENSOR_TIMEOUT_MS\n\n\nclass ClimateEffectiveActionEstimator:\n    """Runtime-equivalent first-order actuator-state estimator."""\n\n    def __init__(self) -> None:\n        self.state = ClimateAction()\n\n    def reset(self) -> None:\n        self.state = ClimateAction()\n\n    @staticmethod\n    def _lag(previous: float, requested: float, dt: float, time_constant: float) -> float:\n        if time_constant <= 0.0:\n            return requested\n        alpha = 1.0 - math.exp(-dt / time_constant)\n        return previous + alpha * (requested - previous)\n\n    @staticmethod\n    def _masked_command(scenario: ClimateScenario, command: ClimateAction) -> ClimateAction:\n        values = command.clipped().as_dict()\n        caps = scenario.actuators\n        values["heater"] = values["heater"] if caps.heater.available else 0.0\n        values["cooler"] = values["cooler"] if caps.cooler.available else 0.0\n        if caps.exhaust_fan.available:\n            fan = values["exhaust_fan"]\n            if 0.0 < fan < caps.exhaust_fan.minimum_command:\n                fan = 0.0\n            values["exhaust_fan"] = fan\n        else:\n            values["exhaust_fan"] = 0.0\n        values["humidifier"] = values["humidifier"] if caps.humidifier.available else 0.0\n        values["dehumidifier"] = (\n            values["dehumidifier"] if caps.dehumidifier.available else 0.0\n        )\n        values["co2_doser"] = values["co2_doser"] if caps.co2_doser.available else 0.0\n        return ClimateAction.from_mapping(values)\n\n    def update(\n        self,\n        scenario: ClimateScenario,\n        command: ClimateAction,\n        timestep_s: float | None = None,\n    ) -> ClimateAction:\n        dt = float(scenario.timestep_s if timestep_s is None else timestep_s)\n        if not math.isfinite(dt) or dt <= 0.0:\n            raise ValueError("timestep_s must be finite and positive")\n        requested = self._masked_command(scenario, command)\n        old = self.state\n        lag = scenario.response_lag\n        self.state = ClimateAction(\n            heater=self._lag(old.heater, requested.heater, dt, lag.heater_s),\n            cooler=self._lag(old.cooler, requested.cooler, dt, lag.cooler_s),\n            exhaust_fan=self._lag(\n                old.exhaust_fan, requested.exhaust_fan, dt, lag.exhaust_fan_s\n            ),\n            humidifier=self._lag(\n                old.humidifier, requested.humidifier, dt, lag.humidifier_s\n            ),\n            dehumidifier=self._lag(\n                old.dehumidifier, requested.dehumidifier, dt, lag.dehumidifier_s\n            ),\n            co2_doser=self._lag(old.co2_doser, requested.co2_doser, dt, lag.co2_doser_s),\n        )\n        return self.state\n\n\n'''
if anchor not in text:
    raise RuntimeError("Could not locate ClimateInputConfig anchor")
text = text.replace(anchor, estimator_py, 1)
text = text.replace(
    "    previous: ClimateAction | None = None,\n    trends: ClimateTrends | None = None,",
    "    previous: ClimateAction | None = None,\n    estimated_effective: ClimateAction | None = None,\n    trends: ClimateTrends | None = None,",
    2,
)
text = text.replace(
    "    previous = previous or ClimateAction()\n    trends = trends or ClimateTrends()",
    "    previous = previous or ClimateAction()\n    estimated_effective = estimated_effective or ClimateAction()\n    trends = trends or ClimateTrends()",
    1,
)
text = text.replace(
    '        "previous": previous.as_dict(),\n        "capabilities": {',
    '        "previous": previous.as_dict(),\n        "estimated_effective": estimated_effective.as_dict(),\n        "capabilities": {',
    1,
)
text = text.replace(
    "        previous=previous,\n        trends=trends,",
    "        previous=previous,\n        estimated_effective=estimated_effective,\n        trends=trends,",
    1,
)
text = text.replace("if encoded.shape != (38,):", "if encoded.shape != (44,):", 1)
text = text.replace("expected 38 climate features", "expected 44 climate features", 1)
text = text.replace(
    '    "ClimateInputConfig",\n',
    '    "ClimateEffectiveActionEstimator",\n    "ClimateInputConfig",\n',
    1,
)
write(climate_input_path, text)

climate_dataset_path = "tools/ml/climate_dataset.py"
text = read(climate_dataset_path)
text = text.replace(
    "    ClimateInputConfig,\n    ClimateTrendEstimator,",
    "    ClimateEffectiveActionEstimator,\n    ClimateInputConfig,\n    ClimateTrendEstimator,",
    1,
)
text = text.replace(
    "        trend_estimator = ClimateTrendEstimator()\n        status_rng =",
    "        trend_estimator = ClimateTrendEstimator()\n        effective_estimator = ClimateEffectiveActionEstimator()\n        status_rng =",
    1,
)
text = text.replace(
    "                    previous=simulator.previous_command,\n                    trends=trends,",
    "                    previous=simulator.previous_command,\n                    estimated_effective=effective_estimator.state,\n                    trends=trends,",
    1,
)
text = text.replace(
    "            simulator.step(\n                teacher_result.action,\n                add_sensor_noise=False,\n                light_level=profile.light_level,\n            )",
    "            simulator.step(\n                teacher_result.action,\n                add_sensor_noise=False,\n                light_level=profile.light_level,\n            )\n            effective_estimator.update(simulator.scenario, teacher_result.action)",
    1,
)
text = text.replace("if feature_count != 38:", "if feature_count != 44:", 1)
text = text.replace('errors.append(f"expected 38 features, got {feature_count}")', 'errors.append(f"expected 44 features, got {feature_count}")', 1)
write(climate_dataset_path, text)

replace_once(
    "tests/test_mvp_contract_v6.py",
    '    "previous_co2_doser",\n    "heater_available",',
    '    "previous_co2_doser",\n    "estimated_effective_heater",\n    "estimated_effective_cooler",\n    "estimated_effective_exhaust_fan",\n    "estimated_effective_humidifier",\n    "estimated_effective_dehumidifier",\n    "estimated_effective_co2_doser",\n    "heater_available",',
)
replace_once(
    "tests/test_mvp_contract_v6.py",
    'assert model["feature_count"] == len(EXPECTED_FEATURES) == 38',
    'assert model["feature_count"] == len(EXPECTED_FEATURES) == 44',
)

cpp_test = "test/test_climate_v6/test_main.cpp"
text = read(cpp_test)
text = text.replace('#include "ClimateContract.h"\n', '#include "ClimateActuatorStateEstimator.h"\n#include "ClimateContract.h"\n', 1)
text = text.replace('check(c::kFeatureCount == 38U, "feature count");', 'check(c::kFeatureCount == 44U, "feature count");', 1)
text = text.replace(
    "  in.previous.heater = 2.0F;\n  in.capabilities.heater = true;",
    "  in.previous.heater = 2.0F;\n  in.estimated_effective.heater = 0.25F;\n  in.capabilities.heater = true;",
    1,
)
text = text.replace(
    '  check(r.clamped(c::FeatureIndex::PreviousHeater), "clamp diagnostic");\n}',
    '  check(r.clamped(c::FeatureIndex::PreviousHeater), "clamp diagnostic");\n  check(near(feature(v, c::FeatureIndex::EstimatedEffectiveHeater), 0.25F, 0.0001F),\n        "effective actuator context");\n}\nvoid actuatorEstimatorTest() {\n  using namespace growbox::climate;\n  ClimateActuatorStateEstimator estimator{};\n  ClimateCapabilities capabilities{};\n  capabilities.heater = true;\n  capabilities.cooler = true;\n  capabilities.exhaust_fan = true;\n  capabilities.humidifier = true;\n  capabilities.dehumidifier = true;\n  capabilities.co2_doser = true;\n  ClimatePolicyRequest command{};\n  command.heater = 1.0F;\n  command.cooler = 0.5F;\n  command.exhaust_fan = 0.8F;\n  command.humidifier = 0.6F;\n  command.dehumidifier = 0.4F;\n  command.co2_doser = 0.7F;\n  const auto first = estimator.update(command, 10.0F, capabilities);\n  check(near(first.heater, 1.0F - std::exp(-10.0F / 35.0F), 0.0001F), "heater lag");\n  check(near(first.cooler, 0.5F * (1.0F - std::exp(-10.0F / 45.0F)), 0.0001F),\n        "cooler lag");\n  check(near(first.co2_doser, 0.7F, 0.0001F), "zero-lag CO2");\n  estimator.reset();\n  capabilities.heater = false;\n  const auto masked = estimator.update(command, 10.0F, capabilities);\n  check(masked.heater == 0.0F, "unavailable actuator masked");\n}\n',
    1,
)
text = text.replace("  encoderTest();\n  trendTest();", "  encoderTest();\n  actuatorEstimatorTest();\n  trendTest();", 1)
write(cpp_test, text)

py_test = "tests/test_climate_input.py"
text = read(py_test)
text = text.replace(
    "    ClimateInputConfig,\n",
    "    ClimateEffectiveActionEstimator,\n    ClimateInputConfig,\n",
    1,
)
text = text.replace("    assert vector.shape == (38,)", "    assert vector.shape == (44,)", 1)
text = text.replace(
    "        previous=ClimateAction(heater=2.0),\n        trends=trends,",
    "        previous=ClimateAction(heater=2.0),\n        estimated_effective=ClimateAction(heater=0.25),\n        trends=trends,",
    1,
)
text = text.replace(
    '    assert feature_value(vector, "previous_heater") == 1.0\n',
    '    assert feature_value(vector, "previous_heater") == 1.0\n    assert math.isclose(\n        feature_value(vector, "estimated_effective_heater"), 0.25, abs_tol=1e-6\n    )\n',
    1,
)
text += '''\n\ndef test_effective_action_estimator_matches_simulator_response_lag() -> None:\n    scenario = ClimateScenario()\n    from tools.ml.climate_simulator import ClimateSimulator\n\n    simulator = ClimateSimulator(scenario)\n    estimator = ClimateEffectiveActionEstimator()\n    commands = (\n        ClimateAction(heater=1.0, exhaust_fan=0.8, humidifier=0.6),\n        ClimateAction(heater=0.2, exhaust_fan=0.1, humidifier=0.0),\n        ClimateAction(heater=0.0, exhaust_fan=1.0, humidifier=0.4),\n    )\n    for command in commands:\n        simulator.step(command, add_sensor_noise=False)\n        estimated = estimator.update(scenario, command)\n        assert np.allclose(\n            np.asarray(estimated.as_tuple()),\n            np.asarray(simulator.effective_action.as_tuple()),\n            atol=1.0e-12,\n        )\n\n\ndef test_effective_action_estimator_reset_returns_zero_state() -> None:\n    scenario = ClimateScenario()\n    estimator = ClimateEffectiveActionEstimator()\n    estimator.update(scenario, ClimateAction(heater=1.0))\n    estimator.reset()\n    assert estimator.state == ClimateAction()\n'''
write(py_test, text)

shape_files = [
    "tools/ml/run_climate_v6_dataset_audit.py",
    "tests/test_climate_training.py",
    "tests/test_climate_dagger_distributed.py",
    "tests/test_climate_dataset.py",
    "tests/test_climate_training_weighted.py",
    "tests/test_climate_dagger.py",
    "tests/test_climate_model_artifact.py",
    "tools/ml/export_climate_v6_winner.py",
    "tools/ml/run_dagger_overnight.py",
    "tools/ml/run_weighted_climate_v6_training.py",
    "tools/ml/climate_training.py",
    "tools/ml/climate_dagger.py",
    "tools/ml/climate_training_weighted.py",
    "tools/ml/climate_model_artifact.py",
    "tools/ml/run_dagger_distributed.py",
]
for path in shape_files:
    text = read(path)
    updated = re.sub(r"\b38\b", "44", text)
    if updated == text:
        raise RuntimeError(f"{path}: expected at least one 38-feature dependency")
    write(path, updated)

print("Stage 13 effective-actuator observability migration applied")
