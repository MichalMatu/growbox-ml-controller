from __future__ import annotations

from tools.ml.climate_dataset import ClimateDatasetConfig, assert_climate_dataset_ready, audit_climate_dataset
from tools.ml.climate_dataset_parallel import generate_climate_dataset_parallel


def main() -> None:
    print("CLIMATE_V6_PARALLEL_FULL_AUDIT_START", flush=True)
    config = ClimateDatasetConfig.full(seed=1847)
    bundle = generate_climate_dataset_parallel(config, workers=4)
    report = audit_climate_dataset(bundle)
    print("CLIMATE_V6_PARALLEL_FULL_AUDIT", flush=True)
    for line in report.summary_lines():
        print(line, flush=True)
    print("families=", report.family_counts, flush=True)
    print("splits=", report.split_counts, flush=True)
    print("mean_level=", report.mean_level, flush=True)
    print("conflicting_temperature_rows=", report.conflicting_temperature_rows, flush=True)
    print("conflicting_humidity_rows=", report.conflicting_humidity_rows, flush=True)
    assert_climate_dataset_ready(
        report,
        require_family_coverage_in_each_split=True,
        bundle=bundle,
    )
    print("FULL_DATASET_GATE=PASS", flush=True)


if __name__ == "__main__":
    main()
