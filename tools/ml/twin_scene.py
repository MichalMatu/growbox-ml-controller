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
    hx, hy, hz = box.half
    radius = 0.12 * min(hx, hy)
    height = 0.18 * (2.0 * hz)
    return max(0.02, radius), max(0.05, height)


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
    """Build glyph field from fan + leak (not Navier–Stokes).

    - Fan: stronger horizontal through-flow along +X (inlet −X → outlet +X).
    - Leak: weaker vertical / wall exchange proportional to ACH.
    Magnitude scales with command and |inside − outside| climate gap (visual cue).
    """
    fan = min(1.0, max(0.0, float(fan_command)))
    leak = max(0.0, float(air_leak_rate_ach))
    volume = max(0.05, box.volume_m3)
    fan_ach = fan * max(0.0, fan_max_airflow_m3_h) / volume  # 1/h at full map
    # Climate gap [0, 1] — stronger arrows when driving force is large
    t_gap = min(1.0, abs(air_temperature_c - outside_temperature_c) / 15.0)
    rh_gap = min(1.0, abs(air_humidity_pct - outside_humidity_pct) / 50.0)
    gap = 0.35 + 0.65 * max(t_gap, rh_gap)

    hx, hy, hz = box.half
    height = 2.0 * hz
    points: list[list[float]] = []
    vectors: list[list[float]] = []
    mags: list[float] = []
    labels: list[str] = []

    # --- Fan through-flow: 3 layers × mid-line samples ---
    fan_scale = 0.08 * box.size_xyz[0] * (0.15 + 0.85 * fan) * gap
    for z_frac in (0.25, 0.5, 0.75):
        z = z_frac * height
        for y_frac in (-0.4, 0.0, 0.4):
            y = y_frac * hy
            # inlet side
            points.append([-0.85 * hx, y, z])
            vectors.append([fan_scale, 0.0, 0.0])
            mags.append(fan_scale)
            labels.append("fan")
            # mid
            points.append([0.0, y, z])
            vectors.append([fan_scale, 0.0, 0.0])
            mags.append(fan_scale)
            labels.append("fan")
            # outlet
            points.append([0.85 * hx, y, z])
            vectors.append([fan_scale, 0.0, 0.0])
            mags.append(fan_scale)
            labels.append("fan")

    # --- Leak: small outward normals on walls, scale with leak ACH ---
    leak_scale = 0.03 * box.size_xyz[0] * min(2.0, leak / 0.25) * gap
    wall_samples = [
        ([hx, 0.0, 0.5 * height], [leak_scale, 0.0, 0.0]),
        ([-hx, 0.0, 0.5 * height], [-leak_scale, 0.0, 0.0]),
        ([0.0, hy, 0.5 * height], [0.0, leak_scale, 0.0]),
        ([0.0, -hy, 0.5 * height], [0.0, -leak_scale, 0.0]),
        ([0.0, 0.0, height], [0.0, 0.0, leak_scale * 0.6]),
    ]
    for pt, vec in wall_samples:
        points.append(pt)
        vectors.append(vec)
        mags.append(float(np.linalg.norm(vec)))
        labels.append("leak")

    pts = np.asarray(points, dtype=np.float64)
    vecs = np.asarray(vectors, dtype=np.float64)
    mags_a = np.asarray(mags, dtype=np.float64)
    return ExchangeField(
        points=pts,
        vectors=vecs,
        magnitudes=mags_a,
        labels=tuple(labels),
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
