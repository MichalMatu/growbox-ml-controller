from pathlib import Path

path = Path("tests/test_stage27c_soak.py")
text = path.read_text(encoding="utf-8")
if "test_parse_stage27c_v3_line_and_normalize_storage_fields" in text:
    raise RuntimeError("Stage27C v3 tests already present")
anchor = "def test_parse_stage27c_v2_line() -> None:\n"
if text.count(anchor) != 1:
    raise RuntimeError(f"expected one v2 parser test anchor, found {text.count(anchor)}")
helper = r'''def _line_v3(**overrides: object) -> str:
    legacy_payload = _line().split("soak_v=2 ", 1)[1]
    values = dict(token.split("=", 1) for token in legacy_payload.split() if "=" in token)
    for key in (
        "outputs",
        "sd_mounted",
        "sd_mount_errors",
        "sd_write_errors",
        "sd_queue_drops",
        "sd_records_written",
        "sd_records_skipped",
        "sd_last_write_ms",
    ):
        values.pop(key, None)
    values.update(
        {
            "output_v": 2,
            "supervisor_mode": 1,
            "transport_active": 0,
            "lifecycle_active": 1,
            "automation_requested": 0,
            "safety_latched": 0,
            "safety_reason": 0,
            "storage_backend": "sd",
            "storage_sd_mounted": 1,
            "storage_flash_mounted": 1,
            "storage_sd_mount_errors": 0,
            "storage_flash_mount_errors": 0,
            "storage_write_errors": 0,
            "storage_queue_drops": 0,
            "storage_records_written": 10,
            "storage_records_skipped": 0,
            "storage_fallbacks": 0,
            "storage_sd_recoveries": 0,
            "storage_last_write_ms": 900,
        }
    )
    values.update(overrides)
    payload = " ".join(f"{key}={value}" for key, value in values.items())
    return f"I (1000) climate_stage27: soak_v=3 {payload}"


'''
text = text.replace(anchor, helper + anchor, 1)
text = text.rstrip() + r'''


def test_parse_stage27c_v3_line_and_normalize_storage_fields() -> None:
    record = parse_soak_line(_line_v3(io_status=3))
    assert record is not None
    assert record["soak_v"] == 3
    assert record["output_v"] == 2
    assert record["transport_active"] == 0
    assert record["sd_mounted"] == 1
    assert record["sd_write_errors"] == 0
    assert record["sd_queue_drops"] == 0
    assert record["sd_records_written"] == 10

    summary = SoakSummary(expected_sha="a" * 40)
    summary.observe(record)
    assert summary.bad_outputs == 0
    assert summary.nonzero_io_status_records == 0
    assert summary.violations(require_sd=True) == []


def test_stage27c_v3_rejects_active_physical_transport() -> None:
    record = parse_soak_line(_line_v3(transport_active=1))
    assert record is not None
    summary = SoakSummary(expected_sha="a" * 40)
    summary.observe(record)
    assert summary.bad_outputs == 1
    assert "outputs not fake-locked" in summary.violations()


def test_stage27c_v2_keeps_legacy_nonzero_io_status_rule() -> None:
    record = parse_soak_line(_line(io_status=2))
    assert record is not None
    summary = SoakSummary(expected_sha="a" * 40)
    summary.observe(record)
    assert summary.bad_outputs == 0
    assert summary.nonzero_io_status_records == 1
    assert "nonzero IO status" in summary.violations()
''' + "\n"
path.write_text(text, encoding="utf-8")
print("STAGE27C_V3_TESTS_APPENDED")
