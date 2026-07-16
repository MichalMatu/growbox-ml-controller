"""Deterministic data generation and TinyML training tools.

Active contract: schemas/environment-controller.json (v4, 128 features, 15 outputs, pots).

Import path for a growbox simulation script::

    from tools.ml import load_active_contract, summarize_training_fields
    from tools.ml.controller_input import controller_input_record
    from tools.ml.simulator import SequentialEnvironmentSimulator
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
