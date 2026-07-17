"""Scientific 3D scene data for the growbox lumped simulator.

This is **not** CFD. Vectors represent *effective air exchange* implied by
fan command, leak ACH, and outside conditions — suitable for PyVista glyphs.

Geometry is derived from ``growbox_volume_m3`` with a fixed aspect ratio.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .simulator import (
    MAX_POTS,
    ControlAction,
    EnvironmentState,
    SequentialEnvironmentSimulator,
)

# Box aspect: length : width : height (grow tent-ish)
_ASPECT = (1.0, 0.75, 1.2)


@dataclass(frozen=True)
class BoxGeometry:
    """Axis-aligned chamber box with origin at floor center."""

    size_xyz: tuple[float, float, float]  # full extents [m]
    volume_m3: float

    @property
    def half(self) -> tuple[float, float, float]:
        sx, sy, sz = self.size_xyz
        return (0.5 * sx, 0.5 * sy, 0.5 * sz)

    @property
    def bounds(self) -> tuple[float, float, float, float, float, float]:
        hx, hy, hz = self.half
        return (-hx, hx, -hy, hy, 0.0, 2.0 * hz)


def box_from_volume(volume_m3: float) -> BoxGeometry:
    """Scale fixed aspect box so product of edges ≈ volume."""
    volume = max(0.05, float(volume_m3))
    ax, ay, az = _ASPECT
    # V = (s·ax)*(s·ay)*(s·az) = s³ · ax·ay·az
    scale = (volume / (ax * ay * az)) ** (1.0 / 3.0)
    return BoxGeometry(size_xyz=(scale * ax, scale * ay, scale * az), volume_m3=volume)


def pot_centers(box: BoxGeometry, n_pots: int = MAX_POTS) -> list[tuple[float, float, float]]:
    """Place up to 4 pots on the floor in a 2×2 grid."""
    n = max(0, min(MAX_POTS, int(n_pots)))
    hx, hy, _ = box.half
    # Inset from walls
    xs = (-0.35 * hx, 0.35 * hx)
    ys = (-0.35 * hy, 0.35 * hy)
    slots = [
        (xs[0], ys[0], 0.0),
        (xs[1], ys[0], 0.0),
        (xs[0], ys[1], 0.0),
        (xs[1], ys[1], 0.0),
    ]
    return slots[:n]


def pot_radius_height(box: BoxGeometry) -> tuple[float, float]:
    """Pot cylinder size — large enough to read as a plant pot, not a pin."""
    hx, hy, hz = box.half
    radius = 0.22 * min(hx, hy)
    height = 0.28 * (2.0 * hz)
    return max(0.06, radius), max(0.12, height)


@dataclass(frozen=True)
class ExchangeField:
    """Discrete sample points + vectors for air-exchange glyphs (lumped model)."""

    points: np.ndarray  # (N, 3)
    vectors: np.ndarray  # (N, 3)
    magnitudes: np.ndarray  # (N,)
    labels: tuple[str, ...]  # semantic tag per point group (optional parallel)
    fan_ach_proxy: float
    leak_ach: float
    outside_temperature_c: float
    outside_humidity_pct: float


def vent_port_centers(
    box: BoxGeometry,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Inlet (−X wall) and outlet (+X wall) opening centers (fan on outlet)."""
    hx, _hy, hz = box.half
    height = 2.0 * hz
    z = 0.55 * height  # slightly above mid-height, typical duct height cue
    inlet = (-hx, 0.0, z)
    outlet = (hx, 0.0, z)
    return inlet, outlet


def exchange_field(
    box: BoxGeometry,
    *,
    fan_command: float,
    air_leak_rate_ach: float,
    fan_max_airflow_m3_h: float,
    outside_temperature_c: float,
    outside_humidity_pct: float,
    air_temperature_c: float,
    air_humidity_pct: float,
) -> ExchangeField:
    """Build glyphs for **inlet / outlet** air path only (not through walls).

    Hardware model:
    - sealed walls (no permeation arrows),
    - inlet opening on −X,
    - outlet opening on +X with **fan on exhaust**.

    ``air_leak_rate_ach`` is kept in the snapshot for HUD/debug (sim parameter)
    but is **not** drawn as wall flux — real tents exchange via ports, not fabric.
    """
    fan = min(1.0, max(0.0, float(fan_command)))
    leak = max(0.0, float(air_leak_rate_ach))
    volume = max(0.05, box.volume_m3)
    fan_ach = fan * max(0.0, fan_max_airflow_m3_h) / volume  # 1/h at full map

    t_gap = min(1.0, abs(air_temperature_c - outside_temperature_c) / 15.0)
    rh_gap = min(1.0, abs(air_humidity_pct - outside_humidity_pct) / 50.0)
    gap = 0.35 + 0.65 * max(t_gap, rh_gap)

    hx, hy, hz = box.half
    height = 2.0 * hz
    points: list[list[float]] = []
    vectors: list[list[float]] = []
    mags: list[float] = []
    labels: list[str] = []

    inlet, outlet = vent_port_centers(box)
    # Flow strength only when fan runs (exhaust pulls air in the inlet).
    flow = 0.40 * box.size_xyz[0] * (0.30 + 0.70 * fan) * gap

    if fan > 0.02:
        # Inlet: outside → inside (+X)
        for y_off in (-0.12 * hy, 0.0, 0.12 * hy):
            for z_off in (-0.08 * height, 0.0, 0.08 * height):
                points.append([inlet[0] - 0.02 * hx, inlet[1] + y_off, inlet[2] + z_off])
                vectors.append([flow, 0.0, 0.0])
                mags.append(flow)
                labels.append("inlet")
        # Interior path toward outlet
        for x_frac in (-0.35, 0.0, 0.35):
            points.append([x_frac * hx, 0.0, inlet[2]])
            vectors.append([flow * 0.85, 0.0, 0.0])
            mags.append(flow * 0.85)
            labels.append("duct")
        # Outlet / fan exhaust: inside → outside (+X)
        for y_off in (-0.12 * hy, 0.0, 0.12 * hy):
            for z_off in (-0.08 * height, 0.0, 0.08 * height):
                points.append([outlet[0] + 0.02 * hx, outlet[1] + y_off, outlet[2] + z_off])
                vectors.append([flow, 0.0, 0.0])
                mags.append(flow)
                labels.append("outlet_fan")

    if not points:
        pts = np.zeros((0, 3), dtype=np.float64)
        vecs = np.zeros((0, 3), dtype=np.float64)
        mags_a = np.zeros((0,), dtype=np.float64)
        label_t: tuple[str, ...] = ()
    else:
        pts = np.asarray(points, dtype=np.float64)
        vecs = np.asarray(vectors, dtype=np.float64)
        mags_a = np.asarray(mags, dtype=np.float64)
        label_t = tuple(labels)

    return ExchangeField(
        points=pts,
        vectors=vecs,
        magnitudes=mags_a,
        labels=label_t,
        fan_ach_proxy=float(fan_ach),
        leak_ach=float(leak),
        outside_temperature_c=float(outside_temperature_c),
        outside_humidity_pct=float(outside_humidity_pct),
    )


@dataclass(frozen=True)
class TwinSnapshot:
    """All numbers needed to paint one 3D frame."""

    box: BoxGeometry
    air_temperature_c: float
    air_humidity_pct: float
    co2_ppm: float
    outside_temperature_c: float
    outside_humidity_pct: float
    outside_co2_ppm: float
    pot_moisture: tuple[float, ...]
    pot_temperature: tuple[float, ...]
    pot_active: tuple[bool, ...]
    exchange: ExchangeField
    elapsed_s: float
    action: ControlAction

    def title(self) -> str:
        return (
            f"t={self.elapsed_s:.0f}s  "
            f"T={self.air_temperature_c:.1f}°C  RH={self.air_humidity_pct:.0f}%  "
            f"CO₂={self.co2_ppm:.0f}ppm  "
            f"fan={self.action.fan:.2f}  heater={self.action.heater:.2f}"
        )


def snapshot_from_simulator(
    simulator: SequentialEnvironmentSimulator,
    action: ControlAction | None = None,
) -> TwinSnapshot:
    """Capture current sim state + exchange field for visualization."""
    scenario = simulator.scenario
    state: EnvironmentState = simulator.state
    action = (action or simulator.effective_action).clipped()
    box = box_from_volume(scenario.environment.growbox_volume_m3)
    caps = scenario.actuators
    exchange = exchange_field(
        box,
        fan_command=action.fan if caps.fan.available else 0.0,
        air_leak_rate_ach=scenario.environment.air_leak_rate_ach,
        fan_max_airflow_m3_h=caps.fan.max_airflow_m3_h,
        outside_temperature_c=state.outside_temperature_c,
        outside_humidity_pct=state.outside_humidity_pct,
        air_temperature_c=state.air_temperature_c,
        air_humidity_pct=state.air_humidity_pct,
    )
    moisture: list[float] = []
    soil_t: list[float] = []
    active: list[bool] = []
    for index in range(MAX_POTS):
        pot_cfg = scenario.pots[index]
        pot_st = state.pots[index]
        active.append(bool(pot_cfg.available))
        moisture.append(float(pot_st.soil_moisture_pct))
        soil_t.append(float(pot_st.soil_temperature_c))
    return TwinSnapshot(
        box=box,
        air_temperature_c=state.air_temperature_c,
        air_humidity_pct=state.air_humidity_pct,
        co2_ppm=state.co2_ppm,
        outside_temperature_c=state.outside_temperature_c,
        outside_humidity_pct=state.outside_humidity_pct,
        outside_co2_ppm=state.outside_co2_ppm,
        pot_moisture=tuple(moisture),
        pot_temperature=tuple(soil_t),
        pot_active=tuple(active),
        exchange=exchange,
        elapsed_s=float(simulator.elapsed_s),
        action=action,
    )


def temperature_to_rgb(
    temperature_c: float, t_min: float = 10.0, t_max: float = 35.0
) -> tuple[float, float, float]:
    """Map temperature to RGB in [0, 1] (blue → red)."""
    x = (float(temperature_c) - t_min) / max(1e-6, t_max - t_min)
    x = min(1.0, max(0.0, x))
    # blue (cold) → cyan → yellow → red (hot)
    if x < 0.5:
        t = x * 2.0
        return (t, t, 1.0 - 0.3 * t)
    t = (x - 0.5) * 2.0
    return (1.0, 1.0 - 0.7 * t, 0.2 * (1.0 - t))


def humidity_opacity(humidity_pct: float) -> float:
    """Map RH% to surface opacity for a soft 'air mass' cue."""
    return min(0.85, max(0.12, float(humidity_pct) / 100.0 * 0.75 + 0.12))


def soil_moisture_to_rgb(moisture_pct: float) -> tuple[float, float, float]:
    """Dry brown → wet dark blue-green."""
    x = min(1.0, max(0.0, float(moisture_pct) / 100.0))
    return (0.45 * (1.0 - x), 0.25 + 0.35 * x, 0.1 + 0.45 * x)
