"""Growbox training physics (Tier A chamber + helpers).

Chamber climate structure follows Van Henten (1994) as used in
mpcrl-greenhouse (Mallick et al.), used with authors' permission and attribution.
See docs/simulator/FORMULAS.md and SLOT_MAP.md.
"""

from .actuators import ChamberForcing, build_chamber_forcing
from .pots_substrate import (
    PotPhysicsConfig,
    PotPhysicsState,
    PotStepResult,
    step_pot,
    water_ml_to_humidity_pp,
)
from .psychrometrics import air_moisture_capacity_g, sat_absolute_humidity_g_m3
from .van_henten import (
    VanHentenParams,
    humidity_state_from_rh,
    rh_from_humidity_state,
    step_chamber_van_henten,
)

__all__ = [
    "ChamberForcing",
    "PotPhysicsConfig",
    "PotPhysicsState",
    "PotStepResult",
    "VanHentenParams",
    "air_moisture_capacity_g",
    "build_chamber_forcing",
    "humidity_state_from_rh",
    "rh_from_humidity_state",
    "sat_absolute_humidity_g_m3",
    "step_chamber_van_henten",
    "step_pot",
    "water_ml_to_humidity_pp",
]
