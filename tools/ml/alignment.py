"""Validate simulator I/O against the active training contract.

Physics lives in the simulator; field names, order, and counts live in the schema.
This module is the guardrail between those layers so a new growbox sim script cannot
silently drift from ``schemas/environment-controller.json``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .contract import ACTIVE_CONTRACT_PATH, Contract, load_contract


def load_active_contract() -> Contract:
    """Load the contract used for current ML training (v3)."""
    return load_contract(ACTIVE_CONTRACT_PATH)


def assert_outputs_match_contract(
    contract: Contract,
    output_names: Sequence[str],
    *,
    context: str = "simulator",
) -> None:
    """Raise if output names/order diverge from the contract."""
    expected = list(contract.outputs)
    actual = list(output_names)
    if actual != expected:
        raise ValueError(
            f"{context} outputs do not match contract v{contract.schema_version} "
            f"({contract.short_hash}): expected {expected!r}, got {actual!r}"
        )


def assert_feature_count(
    contract: Contract,
    feature_count: int,
    *,
    context: str = "encoder",
) -> None:
    expected = len(contract.features)
    if feature_count != expected:
        raise ValueError(
            f"{context} feature count {feature_count} != contract "
            f"v{contract.schema_version} ({expected} features, {contract.short_hash})"
        )


def assert_encoded_vector(contract: Contract, vector: Any) -> None:
    """Validate a single encoded feature row."""
    try:
        length = int(getattr(vector, "shape", [len(vector)])[0])
    except (TypeError, IndexError, ValueError) as exc:
        raise ValueError("encoded vector must be a 1-D sequence") from exc
    assert_feature_count(contract, length, context="encoded vector")
    values = list(vector)
    if any(not (0.0 <= float(value) <= 1.0) for value in values):
        raise ValueError("encoded features must lie in [0, 1] after contract normalization")


def feature_path_index(contract: Contract) -> dict[str, int]:
    """Map contract feature paths to encoder indices."""
    return {feature.path: index for index, feature in enumerate(contract.features)}


def summarize_training_fields(contract: Contract | None = None) -> dict[str, Any]:
    """Compact inventory of ML training fields (for audits / new sim scripts)."""
    contract = contract or load_active_contract()
    groups: dict[str, list[str]] = {}
    for feature in contract.features:
        parts = feature.path.split(".")
        if parts[0] == "pots" and len(parts) >= 3:
            group = f"pots.*.{parts[2]}"
        else:
            group = parts[0]
        groups.setdefault(group, []).append(feature.name)
    return {
        "schema_version": contract.schema_version,
        "schema_hash": contract.short_hash,
        "feature_count": len(contract.features),
        "output_count": len(contract.outputs),
        "outputs": list(contract.outputs),
        "feature_groups": {key: len(names) for key, names in sorted(groups.items())},
        "feature_names": list(contract.feature_names),
    }
