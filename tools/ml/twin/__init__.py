"""Scientific 3D twin view for the lumped growbox simulator.

Public API (geometry is PyVista-free; rendering needs optional ``pyvista``).
"""

from __future__ import annotations

from .config import (
    GROWBOX_FIELDS,
    GrowboxConfig,
    apply_growbox_config,
    read_growbox_config,
)
from .live import render_snapshot, run_interactive_live, run_rollout
from .scene import (
    BoxGeometry,
    ExchangeField,
    TwinSnapshot,
    box_from_volume,
    exchange_field,
    pot_centers,
    pot_layout_positions,
    pot_radius_height,
    snapshot_from_simulator,
    vent_port_centers,
)

__all__ = [
    "BoxGeometry",
    "ExchangeField",
    "GROWBOX_FIELDS",
    "GrowboxConfig",
    "TwinSnapshot",
    "apply_growbox_config",
    "box_from_volume",
    "exchange_field",
    "pot_centers",
    "pot_layout_positions",
    "pot_radius_height",
    "read_growbox_config",
    "render_snapshot",
    "run_interactive_live",
    "run_rollout",
    "snapshot_from_simulator",
    "vent_port_centers",
]
