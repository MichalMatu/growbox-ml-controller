from tools.stage27c_soak import SoakSummary, parse_soak_line


def _line(**overrides: object) -> str:
    values: dict[str, object] = {
        "firmware_sha": "a" * 40,
        "uptime_ms": 1000,
        "reset_reason": 1,
        "input_sampled": 1,
        "io_status": 0,
        "heap_internal": 260000,
        "heap_internal_min": 259000,
        "heap_internal_largest": 200000,
        "heap_psram": 8380000,
        "heap_psram_min": 8380000,
        "heap_psram_largest": 8300000,
        "stack_free": 4096,
        "scd_available": 1,
        "scd_sample": 1,
        "scd_t": 24.0,
        "scd_rh": 60.0,
        "scd_co2": 700,
        "scd_age_ms": 4000,
        "scd_read_errors": 0,
        "scd_invalid": 0,
        "scd_samples": 10,
        "rtc_available": 1,
        "rtc_trusted": 1,
        "rtc_reads": 100,
        "rtc_read_errors": 0,
        "rtc_untrusted": 0,
        "rtc_last_success_ms": 1000,
        "rtc_last_trusted_ms": 1000,
        "ble_scanning": 1,
        "ble_scan_starts": 1,
        "ble_scan_errors": 0,
        "ble_scan_restarts": 0,
        "ble_scan_completes": 0,
        "ble_adv_lock_drops": 0,
        "tp_sample": 1,
        "tp_age_ms": 15000,
        "tp_packets": 20,
        "tp_accepted": 20,
        "tp_rejected": 0,
        "xiaomi_sample": 1,
        "xiaomi_age_ms": 5000,
        "xiaomi_packets": 50,
        "xiaomi_accepted": 25,
        "xiaomi_rejected": 25,
        "sd_mounted": 1,
        "sd_mount_errors": 0,
        "sd_write_errors": 0,
        "sd_queue_drops": 0,
        "sd_records_written": 10,
        "sd_records_skipped": 0,
        "sd_last_write_ms": 900,
        "outputs": "fake-locked",
    }
    values.update(overrides)
    payload = " ".join(f"{key}={value}" for key, value in values.items())
    return f"I (1000) climate_stage27: soak_v=2 {payload}"


def test_parse_stage27c_v2_line() -> None:
    record = parse_soak_line(_line())
    assert record is not None
    assert record["soak_v"] == 2
    assert record["uptime_ms"] == 1000
    assert record["firmware_sha"] == "a" * 40
    assert record["outputs"] == "fake-locked"


def test_non_soak_line_is_ignored() -> None:
    assert parse_soak_line("I (10) other: hello") is None


def test_missing_required_field_is_rejected() -> None:
    line = _line().replace(" rtc_read_errors=0", "")
    try:
        parse_soak_line(line)
    except ValueError as exc:
        assert "rtc_read_errors" in str(exc)
    else:
        raise AssertionError("missing required field was accepted")


def test_summary_accepts_nominal_monotonic_records() -> None:
    summary = SoakSummary(expected_sha="a" * 40)
    first = parse_soak_line(_line())
    second = parse_soak_line(
        _line(
            uptime_ms=11000,
            scd_samples=12,
            rtc_reads=110,
            tp_packets=22,
            tp_accepted=22,
            xiaomi_packets=55,
            xiaomi_accepted=28,
            xiaomi_rejected=27,
        )
    )
    assert first is not None and second is not None
    summary.observe(first)
    summary.observe(second)
    assert summary.records == 2
    assert (
        summary.violations(max_scd_age_ms=15000, max_tp_age_ms=60000, max_xiaomi_age_ms=30000) == []
    )


def test_summary_detects_reset_counter_regression_and_bad_output() -> None:
    summary = SoakSummary(expected_sha="a" * 40)
    first = parse_soak_line(_line(uptime_ms=5000, tp_packets=20))
    second = parse_soak_line(
        _line(
            uptime_ms=100,
            tp_packets=1,
            outputs="unsafe",
            ble_scanning=0,
            rtc_read_errors=1,
        )
    )
    assert first is not None and second is not None
    summary.observe(first)
    summary.observe(second)
    violations = summary.violations()
    assert summary.resets == 1
    assert summary.counter_regressions >= 1
    assert "MCU reset/uptime regression" in violations
    assert "outputs not fake-locked" in violations
    assert "BLE scanner inactive" in violations
    assert "RTC read errors" in violations


def test_summary_detects_firmware_mismatch_and_age_thresholds() -> None:
    summary = SoakSummary(expected_sha="b" * 40)
    record = parse_soak_line(_line(tp_age_ms=70000, xiaomi_age_ms=40000))
    assert record is not None
    summary.observe(record)
    violations = summary.violations(max_tp_age_ms=60000, max_xiaomi_age_ms=30000)
    assert "unexpected firmware SHA" in violations
    assert "TP357 age exceeded 60000 ms" in violations
    assert "Xiaomi age exceeded 30000 ms" in violations


def test_summary_can_require_healthy_sd_logging() -> None:
    summary = SoakSummary(expected_sha="a" * 40)
    first = parse_soak_line(_line(sd_mounted=0, sd_records_written=0))
    second = parse_soak_line(_line(uptime_ms=11000, sd_mounted=1, sd_records_written=1))
    assert first is not None and second is not None
    summary.observe(first)
    summary.observe(second)
    assert summary.violations(require_sd=True) == []

    failing = SoakSummary(expected_sha="a" * 40)
    record = parse_soak_line(_line(sd_write_errors=1, sd_records_skipped=1))
    assert record is not None
    failing.observe(record)
    violations = failing.violations(require_sd=True)
    assert "SD write errors" in violations
    assert "SD records skipped" in violations


def test_historical_v2_record_without_sd_fields_still_observes() -> None:
    line = _line()
    for key in (
        "sd_mounted",
        "sd_mount_errors",
        "sd_write_errors",
        "sd_queue_drops",
        "sd_records_written",
        "sd_records_skipped",
        "sd_last_write_ms",
    ):
        line = " ".join(token for token in line.split() if not token.startswith(f"{key}="))
    record = parse_soak_line(line)
    assert record is not None
    summary = SoakSummary(expected_sha="a" * 40)
    summary.observe(record)
    assert summary.records == 1
    assert summary.sd_fields_seen is False
    assert summary.violations() == []
    assert "SD telemetry fields missing" in summary.violations(require_sd=True)
