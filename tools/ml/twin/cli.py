"""CLI entry for the scientific 3D twin view."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..simulator import ControlAction
from .live import run_interactive_live, run_rollout

_CLI_DOC = """Scientific 3D twin view for the lumped growbox simulator (PyVista).

Minimal stable scene:
  - single white wireframe chamber outline (no fill, no T/RH color map)
  - fixed-color pot + inlet/outlet rings
  - at most two fixed-color fan arrows (visibility toggle only)
  - HUD tables for numbers (temperature lives only in the table)
  - mouse trackball rotate/zoom + keyboard camera presets (7/c HOME, 8/9/0/i)

No temperature/humidity geometric overlays. No solid chamber wash.
No orientation gizmo (VTK camera orientation widget removed — poor UX).
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=_CLI_DOC)
    p.add_argument("--steps", type=int, default=30)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--heater", type=float, default=0.0)
    p.add_argument("--fan", type=float, default=0.0)
    p.add_argument("--humidifier", type=float, default=0.0)
    p.add_argument("--outside-temperature-c", type=float, default=None)
    p.add_argument("--screenshot", type=Path, default=None)
    p.add_argument("--interactive", action="store_true")
    p.add_argument("--live", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.live or (args.interactive and args.steps == 0 and args.screenshot is None):
        run_interactive_live(seed=args.seed)
        return 0
    action = ControlAction(
        heater=float(args.heater),
        fan=float(args.fan),
        humidifier=float(args.humidifier),
    )
    snap = run_rollout(
        steps=int(args.steps),
        action=action,
        seed=int(args.seed),
        outside_temperature_c=args.outside_temperature_c,
        screenshot=args.screenshot,
        interactive=bool(args.interactive),
    )
    if args.screenshot is None and not args.interactive:
        print(snap.title())
        print(snap.params_table())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
