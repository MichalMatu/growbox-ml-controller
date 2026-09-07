from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "stage28e_phase_h_closed_tent.py"


def load_observer():
    sys.modules.setdefault("serial", types.SimpleNamespace(Serial=object))
    spec = importlib.util.spec_from_file_location("stage28e_phase_h_closed_tent_test_module", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_h_safety_clear_accepts_safe_and_timer_off() -> None:
    observer = load_observer()
    assert observer.is_h_safety_clear(0, 0, observer.LAMP_SAFETY_REASON_SAFE)
    assert observer.is_h_safety_clear(0, 0, observer.LAMP_SAFETY_REASON_TIMER_OFF)


def test_h_safety_clear_rejects_actual_safety_reasons_and_forcing() -> None:
    observer = load_observer()
    for reason in (2, 3, 4, 5):
        assert not observer.is_h_safety_clear(0, 0, reason)
    assert not observer.is_h_safety_clear(1, 0, observer.LAMP_SAFETY_REASON_SAFE)
    assert not observer.is_h_safety_clear(0, 1, observer.LAMP_SAFETY_REASON_SAFE)
