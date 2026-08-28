#!/usr/bin/env python3
from pathlib import Path


def replace_exact_count(path: str, old: str, new: str, expected_count: int) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected_count:
        raise SystemExit(
            f"expected {expected_count} occurrences in {path}: {old!r}; found {count}"
        )
    file_path.write_text(text.replace(old, new), encoding="utf-8")


replace_exact_count(
    "tools/ml/climate_training.py",
    "expected_params = hidden_units * hidden_units + 46 * hidden_units + 6",
    "expected_params = hidden_units * hidden_units + 52 * hidden_units + 6",
    1,
)
replace_exact_count(
    "tests/test_climate_training.py",
    "def test_climate_model_is_fixed_small_38_32_32_6_mlp() -> None:",
    "def test_climate_model_is_fixed_small_44_32_32_6_mlp() -> None:",
    1,
)
replace_exact_count(
    "tests/test_climate_training.py",
    "assert model.count_params() == 2502",
    "assert model.count_params() == 2694",
    1,
)
replace_exact_count(
    "tests/test_climate_model_artifact.py",
    "assert portable.parameter_count == 2502",
    "assert portable.parameter_count == 2694",
    1,
)
replace_exact_count(
    "tests/test_climate_model_artifact.py",
    "assert loaded.parameter_count == 2502",
    "assert loaded.parameter_count == 2694",
    1,
)
replace_exact_count(
    "tests/test_climate_model_artifact.py",
    "assert portable.parameter_count == 7046",
    "assert portable.parameter_count == 7430",
    1,
)
replace_exact_count(
    "tests/test_climate_model_artifact.py",
    "assert loaded.parameter_count == 7046",
    "assert loaded.parameter_count == 7430",
    1,
)

training = Path("tests/test_climate_training.py").read_text(encoding="utf-8")
artifact = Path("tests/test_climate_model_artifact.py").read_text(encoding="utf-8")
if "assert model.input_shape == (None, 44)" not in training:
    raise SystemExit("Stage 13 migration does not contain the expected 44-feature model input shape")
for shape in ("size=(32, 44)", "size=(16, 44)", "size=(7, 44)", "np.zeros((44,)"):
    if shape not in artifact:
        raise SystemExit(f"Stage 13 migration is missing expected artifact shape: {shape}")

print("Stage 13 parameter-count expectations updated for 44 features")
