from __future__ import annotations

from tools.ml.climate_dataset import (
    ClimateDatasetConfig,
    assert_climate_dataset_ready,
    audit_climate_dataset,
)
from tools.ml.climate_dataset_parallel import generate_climate_dataset_parallel


def main() -> None:
    bundle = generate_climate_dataset_parallel(
        ClimateDatasetConfig(
            scenarios_per_family=3,
            steps_per_scenario=1,
            seed=99173,
            random_invalid_probability=0.0,
            random_stale_probability=0.0,
        ),
        workers=3,
    )
    report = audit_climate_dataset(bundle, minimum_active_fraction=0.0)
    assert report.ready_for_training, report.errors
    assert set(report.humidity_mode_counts) == {"RH", "VPD"}
    assert_climate_dataset_ready(
        report,
        require_family_coverage_in_each_split=True,
        require_humidity_mode_coverage_in_each_split=True,
        bundle=bundle,
    )
    print("STAGE9A_VPD_COVERAGE=PASS", flush=True)


if __name__ == "__main__":
    main()
