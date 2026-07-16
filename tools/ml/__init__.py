"""Deterministic data generation and TinyML training tools.

Active training contract: environment-controller-v3 (128 features, 15 outputs).
Import path for a growbox simulation script:

    from tools.ml.alignment import load_active_contract, summarize_training_fields
    from tools.ml.controller_input import controller_input_record
    from tools.ml.simulator_v2 import SequentialEnvironmentSimulatorV2
    from tools.ml.scenario_payload import default_scenario
"""

from .alignment import load_active_contract, summarize_training_fields
from .contract import ACTIVE_CONTRACT_PATH, Contract, load_contract

__all__ = [
    "ACTIVE_CONTRACT_PATH",
    "Contract",
    "load_active_contract",
    "load_contract",
    "summarize_training_fields",
]
