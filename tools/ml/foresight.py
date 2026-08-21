"""Short-horizon open-loop prediction on the training simulator.

Inject sensor overrides, hold (or apply) an action for N steps, report
predicted state and tracking deviations. Complements ML: no neural net.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .deviations import TrackingReport, deviations_from_simulator
from .simulator import (
    MAX_POTS,
    ControlAction,
    EnvironmentState,
    SequentialEnvironmentSimulator,
)


@dataclass(frozen=True)
class ForesightStep:
    step_index: int
    elapsed_s: float
    state: EnvironmentState
    deviations: TrackingReport

    def as_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "elapsed_s": self.elapsed_s,
            "state": {
                "air_temperature_c": self.state.air_temperature_c,
                "air_humidity_pct": self.state.air_humidity_pct,
                "co2_ppm": self.state.co2_ppm,
                "nutrient_solution_temperature_c": self.state.nutrient_solution_temperature_c,
                "pots": [
                    {
                        "soil_moisture_pct": pot.soil_moisture_pct,
                        "soil_temperature_c": pot.soil_temperature_c,
                    }
                    for pot in self.state.pots
                ],
                "lights_active": self.state.lights_active,
            },
            "deviations": self.deviations.as_dict(),
        }


@dataclass(frozen=True)
class ForesightResult:
    initial: TrackingReport
    steps: tuple[ForesightStep, ...]
    action: ControlAction

    def as_dict(self) -> dict[str, Any]:
        return {
            "initial": self.initial.as_dict(),
            "action": self.action.as_dict(),
            "steps": [step.as_dict() for step in self.steps],
            "final": self.steps[-1].as_dict() if self.steps else None,
        }


_SENSOR_FIELDS = (
    "air_temperature_c",
    "air_humidity_pct",
    "co2_ppm",
    "outside_temperature_c",
    "outside_humidity_pct",
    "outside_co2_ppm",
    "nutrient_solution_temperature_c",
    "lights_active",
)


def inject_state(
    simulator: SequentialEnvironmentSimulator,
    overrides: Mapping[str, Any],
    *,
    pot_overrides: Mapping[int, Mapping[str, Any]] | None = None,
) -> EnvironmentState:
    """Overwrite live simulator sensors in place (training / panel twin only).

    ``overrides`` keys match ``EnvironmentState`` field names.
    ``pot_overrides`` maps pot index 0..3 → ``{soil_moisture_pct, soil_temperature_c}``.
    """
    state = simulator.state
    for key in _SENSOR_FIELDS:
        if key not in overrides:
            continue
        value = overrides[key]
        if key == "lights_active":
            state.lights_active = bool(value)
        else:
            setattr(state, key, float(value))

    if pot_overrides:
        for index, pot_map in pot_overrides.items():
            idx = int(index)
            if idx < 0 or idx >= MAX_POTS:
                raise ValueError(f"pot index out of range: {idx}")
            pot = state.pots[idx]
            if "soil_moisture_pct" in pot_map:
                pot.soil_moisture_pct = float(pot_map["soil_moisture_pct"])
            if "soil_temperature_c" in pot_map:
                pot.soil_temperature_c = float(pot_map["soil_temperature_c"])

    # Keep physical clamps consistent with observe().
    state.air_humidity_pct = min(100.0, max(0.0, state.air_humidity_pct))
    state.co2_ppm = max(0.0, state.co2_ppm)
    for pot in state.pots:
        pot.soil_moisture_pct = min(100.0, max(0.0, pot.soil_moisture_pct))
    return copy.deepcopy(state)


def foresight(
    simulator: SequentialEnvironmentSimulator,
    action: ControlAction | Mapping[str, float] | None = None,
    *,
    steps: int = 6,
    inject: Mapping[str, Any] | None = None,
    pot_inject: Mapping[int, Mapping[str, Any]] | None = None,
    add_sensor_noise: bool = False,
) -> ForesightResult:
    """Clone the simulator, optionally inject sensors, roll action for ``steps``.

    Does not mutate the caller's simulator.
    """
    if steps < 0:
        raise ValueError("steps must be non-negative")
    rollout = simulator.clone()
    if inject or pot_inject:
        inject_state(rollout, inject or {}, pot_overrides=pot_inject)

    if action is None:
        control = ControlAction()
    elif isinstance(action, ControlAction):
        control = action
    else:
        control = ControlAction.from_mapping(action)

    initial = deviations_from_simulator(rollout)
    trail: list[ForesightStep] = []
    for index in range(steps):
        state = rollout.step(control, add_sensor_noise=add_sensor_noise)
        trail.append(
            ForesightStep(
                step_index=index + 1,
                elapsed_s=rollout.elapsed_s,
                state=copy.deepcopy(state),
                deviations=deviations_from_simulator(rollout),
            )
        )
    return ForesightResult(initial=initial, steps=tuple(trail), action=control.clipped())
