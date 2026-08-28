#!/usr/bin/env python3
"""Stage 16A read-only readiness audit for Sequence-Teacher DAgger."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path('.')
DAGGER = ROOT / 'tools/ml/climate_dagger.py'
DATASET = ROOT / 'tools/ml/climate_dataset.py'
TRAINING = ROOT / 'tools/ml/climate_training.py'
SEQUENCE = ROOT / 'tools/ml/climate_sequence_teacher.py'
POLICY = ROOT / 'tools/ml/climate_policy.py'


def has(text: str, needle: str) -> bool:
    return needle in text


def main() -> None:
    dagger = DAGGER.read_text()
    dataset = DATASET.read_text()
    training = TRAINING.read_text()
    sequence = SEQUENCE.read_text()
    policy = POLICY.read_text()

    artifact_candidates = []
    for path in sorted(ROOT.glob('**/*.json')):
        if any(part in {'.git', '.venv', 'node_modules'} for part in path.parts):
            continue
        name = path.name.lower()
        if 'climate' not in name and 'model' not in name and 'artifact' not in name:
            continue
        try:
            text = path.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        if 'feature_names' in text or 'schema_version' in text or 'trained_on_new_features' in text:
            artifact_candidates.append(str(path))
        if len(artifact_candidates) >= 30:
            break

    result = {
        'experiment': 'stage16a_sequence_dagger_readiness_audit',
        'dagger_hardcodes_old_rollout_teacher': (
            has(dagger, 'from .climate_teacher import ClimateRolloutTeacher')
            and has(dagger, 'teacher = ClimateRolloutTeacher()')
        ),
        'dagger_has_sequence_teacher_import': has(dagger, 'ClimateSequenceRolloutTeacher'),
        'dagger_uses_effective_action_estimator': has(dagger, 'ClimateEffectiveActionEstimator'),
        'dagger_encodes_estimated_effective_state': has(dagger, 'estimated_effective=effective_estimator.state'),
        'dagger_updates_estimator_from_safe_applied_action': has(
            dagger, 'effective_estimator.update(simulator.scenario, safety.action)'
        ),
        'dagger_applies_deadzone_arbitration_safety_before_simulator': all(
            has(dagger, needle)
            for needle in (
                'apply_ml_request_deadzone(raw_action)',
                'arbitrate_climate_action(requested, simulator.scenario)',
                'apply_climate_safety(',
                'simulator.step(safety.action',
            )
        ),
        'dagger_asserts_44x6_shapes': has(dagger, 'features.shape != (expected_rows, 44)')
        and has(dagger, 'labels.shape != (expected_rows, 6)'),
        'dagger_rows_train_only': has(dagger, 'DAgger rows must be train-only'),
        'dagger_preserves_frozen_split_helpers': has(dagger, 'frozen_split_fingerprint'),
        'dataset_defaults_old_rollout_teacher': (
            has(dataset, 'ClimateRolloutTeacher')
            and not has(dataset, 'ClimateSequenceRolloutTeacher')
        ),
        'sequence_teacher_available': has(sequence, 'class ClimateSequenceRolloutTeacher'),
        'training_is_direct_portable_model_path': has(training, 'ClimatePortableModel'),
        'safety_supervisor_path_present': has(policy, 'def apply_climate_safety('),
        'artifact_candidates': artifact_candidates,
        'required_change': 'Inject an explicit teacher/labeler into DAgger collection and make Sequence Teacher opt-in; do not change the existing old-teacher default silently.',
        'recommended_stage16_execution': 'After teacher injection is tested, run at most one bounded Sequence-Teacher DAgger iteration on DEV data only; preserve frozen validation/test fingerprints and stop if closed-loop DEV does not improve.',
        'reserved_stage14ab_test_split_evaluated': False,
    }

    blockers = []
    if result['dagger_hardcodes_old_rollout_teacher']:
        blockers.append('hardcoded_old_teacher')
    if not result['dagger_uses_effective_action_estimator']:
        blockers.append('missing_effective_estimator')
    if not result['dagger_updates_estimator_from_safe_applied_action']:
        blockers.append('wrong_estimator_update_source')
    if not result['dagger_asserts_44x6_shapes']:
        blockers.append('missing_44x6_contract')
    result['blockers'] = blockers
    result['sequence_dagger_ready_without_source_change'] = not blockers

    print('STAGE16A_JSON=' + json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
