"""Growbox training physics (Tier A chamber + helpers).

Chamber climate structure follows Van Henten (1994) as used in
mpcrl-greenhouse (Mallick et al.), used with authors' permission and attribution.
See docs/simulator/FORMULAS.md and SLOT_MAP.md.
"""

from .actuators import ChamberForcing, build_chamber_forcing
from .van_henten import (
    VanHentenParams,
    humidity_state_from_rh,
    rh_from_humidity_state,
    step_chamber_van_henten,
)

__all__ = [
    "ChamberForcing",
    "VanHentenParams",
    "build_chamber_forcing",
    "humidity_state_from_rh",
    "rh_from_humidity_state",
    "step_chamber_van_henten",
]
