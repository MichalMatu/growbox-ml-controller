#!/usr/bin/env python3
"""Apply the minimal Stage 16 Sequence-Teacher DAgger injection change."""

from pathlib import Path

DAGGER = Path("tools/ml/climate_dagger.py")
TEST = Path("tests/test_climate_dagger.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"expected exactly one {label} block, found {text.count(old)}")
    return text.replace(old, new, 1)


dag = DAGGER.read_text()
dag = replace_once(
    dag,
    "from .climate_scenarios import ClimateTrainingEpisode, structured_training_episodes\nfrom .climate_simulator import CLIMATE_OUTPUT_NAMES, ClimateAction, ClimateSimulator\nfrom .climate_teacher import ClimateRolloutTeacher\n",
    "from .climate_scenarios import ClimateTrainingEpisode, structured_training_episodes\nfrom .climate_sequence_teacher import ClimateSequenceRolloutTeacher\nfrom .climate_simulator import CLIMATE_OUTPUT_NAMES, ClimateAction, ClimateSimulator\nfrom .climate_teacher import ClimateRolloutTeacher\n",
    "teacher import",
)
dag = replace_once(
    dag,
    "    workers: int = 6\n    random_invalid_probability: float = 0.01\n",
    "    workers: int = 6\n    teacher_kind: str = \"rollout\"\n    random_invalid_probability: float = 0.01\n",
    "teacher_kind field",
)
dag = replace_once(
    dag,
    "        if self.scenarios_per_family <= 0 or self.steps_per_scenario <= 0 or self.workers <= 0:\n            raise ValueError(\"DAgger scenarios, steps and workers must be positive\")\n        if not 0.0 <= self.random_invalid_probability < 1.0:\n",
    "        if self.scenarios_per_family <= 0 or self.steps_per_scenario <= 0 or self.workers <= 0:\n            raise ValueError(\"DAgger scenarios, steps and workers must be positive\")\n        if self.teacher_kind not in {\"rollout\", \"sequence\"}:\n            raise ValueError(\"DAgger teacher_kind must be 'rollout' or 'sequence'\")\n        if not 0.0 <= self.random_invalid_probability < 1.0:\n",
    "teacher_kind validation",
)
dag = replace_once(
    dag,
    "\ndef _collect_episode(\n",
    "\ndef _make_teacher(\n    teacher_kind: str,\n) -> ClimateRolloutTeacher | ClimateSequenceRolloutTeacher:\n    if teacher_kind == \"rollout\":\n        return ClimateRolloutTeacher()\n    if teacher_kind == \"sequence\":\n        return ClimateSequenceRolloutTeacher()\n    raise ValueError(f\"unsupported DAgger teacher_kind: {teacher_kind!r}\")\n\n\ndef _collect_episode(\n",
    "teacher factory insertion",
)
dag = replace_once(
    dag,
    "    teacher = ClimateRolloutTeacher()\n",
    "    teacher = _make_teacher(config.teacher_kind)\n",
    "teacher construction",
)
DAGGER.write_text(dag)

test = TEST.read_text()
test = replace_once(
    test,
    "from tools.ml.climate_dagger import append_train_only, frozen_split_fingerprint\nfrom tools.ml.climate_simulator import CLIMATE_OUTPUT_NAMES\n",
    "from tools.ml.climate_dagger import (\n    DaggerCollectionConfig,\n    _make_teacher,\n    append_train_only,\n    frozen_split_fingerprint,\n)\nfrom tools.ml.climate_sequence_teacher import ClimateSequenceRolloutTeacher\nfrom tools.ml.climate_simulator import CLIMATE_OUTPUT_NAMES\nfrom tools.ml.climate_teacher import ClimateRolloutTeacher\n",
    "test imports",
)
test += '''\n\ndef test_dagger_teacher_kind_preserves_rollout_default_and_allows_sequence_opt_in() -> None:\n    default = DaggerCollectionConfig(seed=1)\n    assert default.teacher_kind == "rollout"\n    assert isinstance(_make_teacher(default.teacher_kind), ClimateRolloutTeacher)\n\n    sequence = DaggerCollectionConfig(seed=1, teacher_kind="sequence")\n    assert sequence.teacher_kind == "sequence"\n    assert isinstance(_make_teacher(sequence.teacher_kind), ClimateSequenceRolloutTeacher)\n\n\ndef test_dagger_teacher_kind_rejects_unknown_value() -> None:\n    try:\n        DaggerCollectionConfig(seed=1, teacher_kind="unknown")\n    except ValueError as exc:\n        assert "teacher_kind" in str(exc)\n    else:\n        raise AssertionError("unknown DAgger teacher_kind must be rejected")\n'''
TEST.write_text(test)
