from __future__ import annotations

import pytest

from tools.ml.generate_dataset import random_scenario
from tools.ml.simulator import Scenario


@pytest.fixture
def scenario() -> Scenario:
    return random_scenario(0, 12345)
