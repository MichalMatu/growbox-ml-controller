"""Van Henten (1994) greenhouse chamber dynamics (compact form).

Source implementation reference:
  third_party/mpcrl-greenhouse/greenhouse/model.py (Model.df / Model.output)
  Mallick et al., Smart Agricultural Technology 10 (2025) — mpcrl-greenhouse.
  Used with authors' permission when cited (see docs/simulator/SOURCES.md).

This module re-implements the ODEs in plain NumPy for our MIT training stack.
Crop dry-weight state x0 is optional (held or weakly evolved); ML contract does
not expose it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

# Physical scale vector from mpcrl Model.p_scale (true multipliers p_i = 1).
P_SCALE = np.asarray(
    [
        0.544,
        2.65e-7,
        53.0,
        3.55e-9,
        5.11e-6,
        2.3e-4,
        6.29e-4,
        5.2e-5,
        4.1,
        4.87e-7,
        7.5e-6,
        8.31,
        273.15,
        101325.0,
        0.044,
        3.0e4,
        1290.0,
        6.1,
        0.2,
        4.1,
        0.0036,
        9348.0,
        8314.0,
        273.15,
        17.4,
        239.0,
        17.269,
        238.3,
    ],
    dtype=np.float64,
)

# S03 native input maxima (Model.get_u_max).
U_CO2_MAX = 1.2
U_VENT_MAX = 7.5
U_HEAT_MAX = 150.0


def _default_p() -> np.ndarray:
    return np.ones(P_SCALE.size, dtype=np.float64)


@dataclass(frozen=True)
class VanHentenParams:
    """Normalized parameter multipliers (1.0 = literature true scale)."""

    p: np.ndarray = field(default_factory=_default_p)

    def __post_init__(self) -> None:
        vector = np.asarray(self.p, dtype=np.float64).reshape(-1)
        if vector.size != P_SCALE.size:
            raise ValueError(f"expected {P_SCALE.size} parameters, got {vector.size}")
        object.__setattr__(self, "p", vector)

    def starred(self, index: int) -> float:
        return float(self.p[index] * P_SCALE[index])


def _psi(x: np.ndarray, d: np.ndarray, params: VanHentenParams) -> float:
    p = params
    return p.starred(3) * d[0] + (
        -p.starred(4) * x[2] ** 2 + p.starred(5) * x[2] - p.starred(6)
    ) * (x[1] - p.starred(7))


def _phi_phot_c(x: np.ndarray, d: np.ndarray, params: VanHentenParams) -> float:
    p = params
    psi = _psi(x, d, params)
    if abs(psi) < 1e-18:
        return 0.0
    canopy = 1.0 - math.exp(-p.starred(2) * x[0])
    return (
        canopy
        * (
            p.starred(3)
            * d[0]
            * (-p.starred(4) * x[2] ** 2 + p.starred(5) * x[2] - p.starred(6))
            * (x[1] - p.starred(7))
        )
        / psi
    )


def _phi_vent_c(x: np.ndarray, u: np.ndarray, d: np.ndarray, params: VanHentenParams) -> float:
    return (u[1] * 1e-3 + params.starred(10)) * (x[1] - d[1])


def _phi_vent_h(x: np.ndarray, u: np.ndarray, d: np.ndarray, params: VanHentenParams) -> float:
    return (u[1] * 1e-3 + params.starred(10)) * (x[3] - d[3])


def _phi_transp_h(x: np.ndarray, params: VanHentenParams) -> float:
    p = params
    canopy = 1.0 - math.exp(-p.starred(2) * x[0])
    sat_term = (p.starred(21) / (p.starred(22) * (x[2] + p.starred(23)))) * math.exp(
        (p.starred(24) * x[2]) / (x[2] + p.starred(25))
    )
    return p.starred(20) * canopy * (sat_term - x[3])


def state_derivative(
    x: np.ndarray,
    u: np.ndarray,
    d: np.ndarray,
    params: VanHentenParams,
    *,
    evolve_crop: bool = False,
) -> np.ndarray:
    """Continuous-time dx/dt for Van Henten state vector."""
    p = params
    phot = _phi_phot_c(x, d, params)
    resp = x[0] * (2.0 ** (x[2] / 10.0 - 2.5))
    if evolve_crop:
        dx0 = p.starred(0) * phot - p.starred(1) * resp
    else:
        dx0 = 0.0
    dx1 = (p.p[8] / P_SCALE[8]) * (
        -phot + p.starred(9) * resp + u[0] * 1e-6 - _phi_vent_c(x, u, d, params)
    )
    dx2 = (p.p[15] / P_SCALE[15]) * (
        u[2] - (p.starred(16) * u[1] * 1e-3 + p.starred(17)) * (x[2] - d[2]) + p.starred(18) * d[0]
    )
    dx3 = (p.p[19] / P_SCALE[19]) * (_phi_transp_h(x, params) - _phi_vent_h(x, u, d, params))
    return np.array([dx0, dx1, dx2, dx3], dtype=np.float64)


def euler_step(
    x: np.ndarray,
    u: np.ndarray,
    d: np.ndarray,
    params: VanHentenParams,
    dt: float,
    *,
    evolve_crop: bool = False,
) -> np.ndarray:
    return x + dt * state_derivative(x, u, d, params, evolve_crop=evolve_crop)


def rk4_step(
    x: np.ndarray,
    u: np.ndarray,
    d: np.ndarray,
    params: VanHentenParams,
    dt: float,
    *,
    evolve_crop: bool = False,
    substeps: int = 1,
) -> np.ndarray:
    h = dt / max(1, int(substeps))
    state = np.asarray(x, dtype=np.float64).copy()
    for _ in range(max(1, int(substeps))):
        k1 = state_derivative(state, u, d, params, evolve_crop=evolve_crop)
        k2 = state_derivative(state + 0.5 * h * k1, u, d, params, evolve_crop=evolve_crop)
        k3 = state_derivative(state + 0.5 * h * k2, u, d, params, evolve_crop=evolve_crop)
        k4 = state_derivative(state + h * k3, u, d, params, evolve_crop=evolve_crop)
        state = state + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    return state


def co2_state_from_ppm(co2_ppm: float, air_temperature_c: float, params: VanHentenParams) -> float:
    """Inverse of Model.output y2 for p_i=1 scale."""
    t_shift = air_temperature_c + params.starred(12)
    factor = (
        1e3
        * (params.p[13] * params.p[14])
        * params.starred(11)
        * t_shift
        / (P_SCALE[13] * P_SCALE[14])
    )
    if abs(factor) < 1e-18:
        return 0.0
    return float(co2_ppm) / factor


def co2_ppm_from_state(x1: float, air_temperature_c: float, params: VanHentenParams) -> float:
    t_shift = air_temperature_c + params.starred(12)
    factor = (
        1e3
        * (params.p[13] * params.p[14])
        * params.starred(11)
        * t_shift
        / (P_SCALE[13] * P_SCALE[14])
    )
    return float(factor * x1)


def humidity_state_from_rh(
    relative_humidity_pct: float, air_temperature_c: float, params: VanHentenParams
) -> float:
    """Inverse of Model.output y4 (RH%)."""
    t_shift = air_temperature_c + params.starred(12)
    denom = 11.0 * math.exp(
        (params.starred(26) * air_temperature_c) / (air_temperature_c + params.starred(27))
    )
    factor = (1e2 * params.starred(11) * t_shift) / denom
    if abs(factor) < 1e-18:
        return 0.0
    return float(relative_humidity_pct) / factor


def rh_from_humidity_state(
    humidity_state: float, air_temperature_c: float, params: VanHentenParams
) -> float:
    t_shift = air_temperature_c + params.starred(12)
    denom = 11.0 * math.exp(
        (params.starred(26) * air_temperature_c) / (air_temperature_c + params.starred(27))
    )
    factor = (1e2 * params.starred(11) * t_shift) / denom
    return float(factor * humidity_state)


def pack_state(
    *,
    crop_dry_weight: float,
    co2_ppm: float,
    air_temperature_c: float,
    air_humidity_pct: float,
    params: VanHentenParams | None = None,
) -> np.ndarray:
    params = params or VanHentenParams()
    return np.array(
        [
            max(0.0, crop_dry_weight),
            max(0.0, co2_state_from_ppm(co2_ppm, air_temperature_c, params)),
            float(air_temperature_c),
            max(0.0, humidity_state_from_rh(air_humidity_pct, air_temperature_c, params)),
        ],
        dtype=np.float64,
    )


def unpack_climate(
    x: np.ndarray, params: VanHentenParams | None = None
) -> tuple[float, float, float]:
    """Return (air_temperature_c, air_humidity_pct, co2_ppm)."""
    params = params or VanHentenParams()
    temperature = float(x[2])
    humidity = float(np.clip(rh_from_humidity_state(x[3], temperature, params), 0.0, 100.0))
    co2 = float(np.clip(co2_ppm_from_state(x[1], temperature, params), 0.0, 5000.0))
    return temperature, humidity, co2


def step_chamber_van_henten(
    *,
    air_temperature_c: float,
    air_humidity_pct: float,
    co2_ppm: float,
    outside_temperature_c: float,
    outside_humidity_pct: float,
    outside_co2_ppm: float,
    u_co2: float,
    u_vent: float,
    u_heat: float,
    radiation: float,
    dt_s: float,
    crop_dry_weight: float = 0.0025,
    params: VanHentenParams | None = None,
    evolve_crop: bool = False,
    integrator: str = "rk4",
    rk4_substeps: int = 1,
) -> tuple[float, float, float, float]:
    """Advance chamber climate one step.

    ``u_*`` are in **S03 native units** (see U_*_MAX), not [0, 1].
    ``radiation`` is disturbance d0 (same role as outdoor light in S03).

    Returns
    -------
    air_temperature_c, air_humidity_pct, co2_ppm, crop_dry_weight
    """
    params = params or VanHentenParams()
    if not math.isfinite(dt_s) or dt_s <= 0.0:
        raise ValueError("dt_s must be finite and positive")

    x = pack_state(
        crop_dry_weight=crop_dry_weight,
        co2_ppm=co2_ppm,
        air_temperature_c=air_temperature_c,
        air_humidity_pct=air_humidity_pct,
        params=params,
    )
    # Outside humidity: convert RH% → humidity state at outside T for vent driving force.
    d = np.array(
        [
            max(0.0, float(radiation)),
            max(0.0, co2_state_from_ppm(outside_co2_ppm, outside_temperature_c, params)),
            float(outside_temperature_c),
            max(0.0, humidity_state_from_rh(outside_humidity_pct, outside_temperature_c, params)),
        ],
        dtype=np.float64,
    )
    u = np.array(
        [max(0.0, float(u_co2)), max(0.0, float(u_vent)), max(0.0, float(u_heat))],
        dtype=np.float64,
    )

    # Substep for stability at small growbox Δt vs S03 900 s training step.
    if integrator == "euler":
        # Multiple Euler substeps (~1 s) for dt up to a few minutes.
        n = max(1, int(math.ceil(dt_s / 1.0)))
        h = dt_s / n
        for _ in range(n):
            x = euler_step(x, u, d, params, h, evolve_crop=evolve_crop)
    else:
        n = max(1, int(rk4_substeps), int(math.ceil(dt_s / 5.0)))
        x = rk4_step(x, u, d, params, dt_s, evolve_crop=evolve_crop, substeps=n)

    x[0] = max(0.0, x[0])
    x[1] = max(0.0, x[1])
    x[3] = max(0.0, x[3])
    temperature, humidity, co2 = unpack_climate(x, params)
    temperature = float(np.clip(temperature, -30.0, 70.0))
    return temperature, humidity, co2, float(x[0])
