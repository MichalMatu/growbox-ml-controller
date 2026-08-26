from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"expected block not found in {path}: {old[:80]!r}")
    p.write_text(text.replace(old, new, 1))


# climate_scenarios.py: add explicit RH/VPD coverage families.
replace_once(
    "tools/ml/climate_scenarios.py",
    '    "humid_dehumidification",\n    "outside_helpful",\n',
    '    "humid_dehumidification",\n    "dry_vpd_control",\n    "humid_vpd_control",\n    "outside_helpful",\n',
)
replace_once(
    "tools/ml/climate_scenarios.py",
    '    elif family == "outside_helpful":\n',
    '''    elif family == "dry_vpd_control":\n        state = replace(\n            state,\n            air_temperature_c=float(rng.uniform(24.0, 27.0)),\n            relative_humidity_pct=float(rng.uniform(26.0, 40.0)),\n            outside_humidity_pct=float(rng.uniform(20.0, 42.0)),\n        )\n        first = _profile(\n            "dry-vpd",\n            temperature=state.air_temperature_c,\n            humidity=60.0,\n            vpd=float(rng.uniform(1.05, 1.30)),\n            mode="VPD",\n        )\n    elif family == "humid_vpd_control":\n        state = replace(\n            state,\n            air_temperature_c=float(rng.uniform(23.0, 26.0)),\n            relative_humidity_pct=float(rng.uniform(78.0, 92.0)),\n            outside_humidity_pct=float(rng.uniform(78.0, 96.0)),\n        )\n        first = _profile(\n            "humid-vpd",\n            temperature=state.air_temperature_c,\n            humidity=60.0,\n            vpd=float(rng.uniform(1.05, 1.30)),\n            mode="VPD",\n        )\n    elif family == "outside_helpful":\n''',
)

# climate_dataset.py: persist humidity mode metadata and require global RH/VPD coverage.
replace_once(
    "tools/ml/climate_dataset.py",
    '    profiles: np.ndarray\n    safe_fallbacks: np.ndarray\n',
    '    profiles: np.ndarray\n    humidity_modes: np.ndarray\n    safe_fallbacks: np.ndarray\n',
)
replace_once(
    "tools/ml/climate_dataset.py",
    '            len(values) != rows for values in (self.families, self.profiles, self.safe_fallbacks)\n',
    '            len(values) != rows\n            for values in (self.families, self.profiles, self.humidity_modes, self.safe_fallbacks)\n',
)
replace_once(
    "tools/ml/climate_dataset.py",
    '    split_counts: dict[str, int]\n    active_fraction: dict[str, float]\n',
    '    split_counts: dict[str, int]\n    humidity_mode_counts: dict[str, int]\n    active_fraction: dict[str, float]\n',
)
replace_once(
    "tools/ml/climate_dataset.py",
    '            f"rows={self.row_count} features={self.feature_count} outputs={self.output_count}",\n            f"active_fraction: {label_summary}",\n',
    '            f"rows={self.row_count} features={self.feature_count} outputs={self.output_count}",\n            "humidity_modes: "\n            + ", ".join(f"{name}={self.humidity_mode_counts.get(name, 0)}" for name in ("RH", "VPD")),\n            f"active_fraction: {label_summary}",\n',
)
replace_once(
    "tools/ml/climate_dataset.py",
    '    profiles: list[str] = []\n    safe_fallbacks: list[bool] = []\n',
    '    profiles: list[str] = []\n    humidity_modes: list[str] = []\n    safe_fallbacks: list[bool] = []\n',
)
replace_once(
    "tools/ml/climate_dataset.py",
    '            profiles.append(profile.name)\n            safe_fallbacks.append(teacher_result.safe_fallback)\n',
    '            profiles.append(profile.name)\n            humidity_modes.append(profile.humidity_control_mode)\n            safe_fallbacks.append(teacher_result.safe_fallback)\n',
)
replace_once(
    "tools/ml/climate_dataset.py",
    '        profiles=np.asarray(profiles),\n        safe_fallbacks=np.asarray(safe_fallbacks, dtype=np.bool_),\n',
    '        profiles=np.asarray(profiles),\n        humidity_modes=np.asarray(humidity_modes),\n        safe_fallbacks=np.asarray(safe_fallbacks, dtype=np.bool_),\n',
)
replace_once(
    "tools/ml/climate_dataset.py",
    '    split_counts = dict(Counter(str(value) for value in dataset.splits))\n    for split in ("train", "validation", "test"):\n',
    '''    split_counts = dict(Counter(str(value) for value in dataset.splits))\n    for split in ("train", "validation", "test"):\n        if split_counts.get(split, 0) == 0:\n            errors.append(f"split {split!r} has no rows")\n\n    humidity_mode_counts = dict(Counter(str(value) for value in bundle.humidity_modes))\n    for mode in ("RH", "VPD"):\n        if humidity_mode_counts.get(mode, 0) == 0:\n            errors.append(f"humidity mode {mode!r} has no rows")\n\n    for split in ():  # keep the following historical block structurally stable\n''',
)
# Remove duplicate body introduced by the structural replacement above.
replace_once(
    "tools/ml/climate_dataset.py",
    '    for split in ():  # keep the following historical block structurally stable\n        if split_counts.get(split, 0) == 0:\n            errors.append(f"split {split!r} has no rows")\n\n    active_fraction: dict[str, float] = {}\n',
    '    active_fraction: dict[str, float] = {}\n',
)
replace_once(
    "tools/ml/climate_dataset.py",
    '        split_counts=split_counts,\n        active_fraction=active_fraction,\n',
    '        split_counts=split_counts,\n        humidity_mode_counts=humidity_mode_counts,\n        active_fraction=active_fraction,\n',
)
replace_once(
    "tools/ml/climate_dataset.py",
    '    require_family_coverage_in_each_split: bool = False,\n    bundle: ClimateDatasetBundle | None = None,\n',
    '    require_family_coverage_in_each_split: bool = False,\n    require_humidity_mode_coverage_in_each_split: bool = False,\n    bundle: ClimateDatasetBundle | None = None,\n',
)
replace_once(
    "tools/ml/climate_dataset.py",
    '    if errors:\n        raise ValueError("climate dataset is not ready for training: " + " | ".join(errors))\n',
    '''    if require_humidity_mode_coverage_in_each_split:\n        if bundle is None:\n            raise ValueError("bundle is required for split/humidity-mode coverage check")\n        mode_pairs = {\n            (str(mode), str(split))\n            for mode, split in zip(bundle.humidity_modes, bundle.dataset.splits, strict=True)\n        }\n        for mode in ("RH", "VPD"):\n            for split in ("train", "validation", "test"):\n                if (mode, split) not in mode_pairs:\n                    errors.append(f"humidity mode {mode!r} is absent from {split!r} split")\n    if errors:\n        raise ValueError("climate dataset is not ready for training: " + " | ".join(errors))\n''',
)

# climate_dataset_parallel.py: preserve bit-exact humidity mode metadata.
replace_once(
    "tools/ml/climate_dataset_parallel.py",
    '    profiles: np.ndarray\n    safe_fallbacks: np.ndarray\n',
    '    profiles: np.ndarray\n    humidity_modes: np.ndarray\n    safe_fallbacks: np.ndarray\n',
)
replace_once(
    "tools/ml/climate_dataset_parallel.py",
    '    profiles: list[str] = []\n    safe_fallbacks: list[bool] = []\n',
    '    profiles: list[str] = []\n    humidity_modes: list[str] = []\n    safe_fallbacks: list[bool] = []\n',
)
replace_once(
    "tools/ml/climate_dataset_parallel.py",
    '        profiles.append(profile.name)\n        safe_fallbacks.append(teacher_result.safe_fallback)\n',
    '        profiles.append(profile.name)\n        humidity_modes.append(profile.humidity_control_mode)\n        safe_fallbacks.append(teacher_result.safe_fallback)\n',
)
replace_once(
    "tools/ml/climate_dataset_parallel.py",
    '        profiles=np.asarray(profiles),\n        safe_fallbacks=np.asarray(safe_fallbacks, dtype=np.bool_),\n',
    '        profiles=np.asarray(profiles),\n        humidity_modes=np.asarray(humidity_modes),\n        safe_fallbacks=np.asarray(safe_fallbacks, dtype=np.bool_),\n',
)
replace_once(
    "tools/ml/climate_dataset_parallel.py",
    '        profiles=_concat(chunks, "profiles"),\n        safe_fallbacks=_concat(chunks, "safe_fallbacks"),\n',
    '        profiles=_concat(chunks, "profiles"),\n        humidity_modes=_concat(chunks, "humidity_modes"),\n        safe_fallbacks=_concat(chunks, "safe_fallbacks"),\n',
)

# tests: require explicit VPD families and audit behavior.
replace_once(
    "tests/test_climate_dataset.py",
    'def test_sensor_fault_family_faults_only_second_half() -> None:\n',
    '''def test_vpd_families_use_vpd_mode() -> None:\n    dry = build_training_episode("dry_vpd_control", 0, 1004)\n    humid = build_training_episode("humid_vpd_control", 0, 1005)\n    assert dry.first_profile.humidity_control_mode == "VPD"\n    assert humid.first_profile.humidity_control_mode == "VPD"\n    assert dry.first_profile.targets.air_vpd_kpa > 0.0\n    assert humid.first_profile.targets.air_vpd_kpa > 0.0\n\n\ndef test_sensor_fault_family_faults_only_second_half() -> None:\n''',
)
replace_once(
    "tests/test_climate_dataset.py",
    '    assert set(bundle.families) == set(REQUIRED_SCENARIO_FAMILIES)\n    assert set(dataset.splits) == {"train", "validation", "test"}\n',
    '    assert set(bundle.families) == set(REQUIRED_SCENARIO_FAMILIES)\n    assert set(bundle.humidity_modes) == {"RH", "VPD"}\n    assert set(dataset.splits) == {"train", "validation", "test"}\n',
)
replace_once(
    "tests/test_climate_dataset.py",
    '    assert np.array_equal(left.families, right.families)\n',
    '    assert np.array_equal(left.families, right.families)\n    assert np.array_equal(left.humidity_modes, right.humidity_modes)\n',
)
replace_once(
    "tests/test_climate_dataset.py",
    '    assert set(report.family_counts) == set(REQUIRED_SCENARIO_FAMILIES)\n',
    '    assert set(report.family_counts) == set(REQUIRED_SCENARIO_FAMILIES)\n    assert set(report.humidity_mode_counts) == {"RH", "VPD"}\n',
)
replace_once(
    "tests/test_climate_dataset.py",
    '        profiles=source.profiles,\n        safe_fallbacks=source.safe_fallbacks,\n',
    '        profiles=source.profiles,\n        humidity_modes=source.humidity_modes,\n        safe_fallbacks=source.safe_fallbacks,\n',
)
replace_once(
    "tests/test_climate_dataset.py",
    'def test_full_style_family_coverage_gate_requires_bundle() -> None:\n',
    '''def test_audit_rejects_dataset_without_vpd_rows() -> None:\n    source = generate_climate_dataset(\n        ClimateDatasetConfig(\n            scenarios_per_family=1,\n            steps_per_scenario=1,\n            seed=9753,\n            random_invalid_probability=0.0,\n            random_stale_probability=0.0,\n        ),\n        teacher=fast_teacher(),\n    )\n    rh_only = ClimateDatasetBundle(\n        dataset=source.dataset,\n        families=source.families,\n        profiles=source.profiles,\n        humidity_modes=np.full(len(source.humidity_modes), "RH"),\n        safe_fallbacks=source.safe_fallbacks,\n    )\n    report = audit_climate_dataset(rh_only, minimum_active_fraction=0.0)\n    assert not report.ready_for_training\n    assert any("VPD" in error for error in report.errors)\n\n\ndef test_full_style_family_coverage_gate_requires_bundle() -> None:\n''',
)

replace_once(
    "tests/test_climate_dataset_parallel.py",
    '    np.testing.assert_array_equal(reference.profiles, parallel.profiles)\n    np.testing.assert_array_equal(reference.safe_fallbacks, parallel.safe_fallbacks)\n',
    '    np.testing.assert_array_equal(reference.profiles, parallel.profiles)\n    np.testing.assert_array_equal(reference.humidity_modes, parallel.humidity_modes)\n    np.testing.assert_array_equal(reference.safe_fallbacks, parallel.safe_fallbacks)\n',
)

print("STAGE9A_PATCH_APPLIED")
