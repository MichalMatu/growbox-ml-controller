"""Build v3 replay scenarios for on-device serial tests."""

from __future__ import annotations

import json
from typing import Any

from tools.ml.scenario_payload import default_scenario


def load_scenario_command(*, seed: int = 101, preset: str = "nominal") -> dict[str, Any]:
    scenario = default_scenario(seed=seed, preset=preset)
    command = {"command": "load_scenario", "seed": scenario["seed"]}
    for key, value in scenario.items():
        if key == "seed":
            continue
        command[key] = value
    return command


def nominal_replay_commands(*, seed: int = 101, preset: str = "nominal") -> list[dict[str, Any]]:
    return [
        {"command": "pause"},
        {"command": "mode", "value": "replay"},
        load_scenario_command(seed=seed, preset=preset),
        {"command": "step"},
        {"command": "status"},
    ]


def write_replay_script(path: str | Any, *, seed: int = 101, preset: str = "nominal") -> None:
    from pathlib import Path

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(command, separators=(",", ":")) for command in nominal_replay_commands(seed=seed)
    ]
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
