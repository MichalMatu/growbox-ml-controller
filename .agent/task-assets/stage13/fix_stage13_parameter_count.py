#!/usr/bin/env python3
from pathlib import Path


def replace_exact(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one occurrence in {path}: {old!r}; found {count}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_exact(
    "tools/ml/climate_training.py",
    "expected_params = hidden_units * hidden_units + 46 * hidden_units + 6",
    "expected_params = hidden_units * hidden_units + 52 * hidden_units + 6",
)
replace_exact(
    "tests/test_climate_training.py",
    "def test_climate_model_is_fixed_small_38_32_32_6_mlp() -> None:",
    "def test_climate_model_is_fixed_small_44_32_32_6_mlp() -> None:",
)
replace_exact(
    "tests/test_climate_training.py",
    "assert model.count_params() == 2502",
    "assert model.count_params() == 2694",
)

text = Path("tests/test_climate_training.py").read_text(encoding="utf-8")
if "assert model.input_shape == (None, 44)" not in text:
    raise SystemExit("Stage 13 dirty checkpoint does not contain the expected 44-feature model input shape")

print("Stage 13 parameter-count recovery applied")
