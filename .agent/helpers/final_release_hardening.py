from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_section(path: str, start: str, end: str, replacement: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    start_index = text.find(start)
    if start_index < 0:
        raise RuntimeError(f"{path}: start marker not found: {start!r}")
    end_index = text.find(end, start_index)
    if end_index < 0:
        raise RuntimeError(f"{path}: end marker not found: {end!r}")
    target.write_text(text[:start_index] + replacement + text[end_index:], encoding="utf-8")


# LampSafety: temperature unavailability is fail-closed for the current cycle, but is not
# itself evidence that an over-temperature trip happened. Any pre-existing real thermal
# latch remains preserved because we deliberately do not clear thermal_latched_ here.
replace_once(
    "src/climate/output/LampSafety.cpp",
    """  if (!temperature_usable) {\n    thermal_latched_ = true;\n    recovery_running_ = false;\n""",
    """  if (!temperature_usable) {\n    recovery_running_ = false;\n""",
)

cpp_test_path = "test/test_stage28d_lamp_safety/test_main.cpp"
cpp_tests = Path(cpp_test_path).read_text(encoding="utf-8")
insert_before = "void testNoFanCapabilityDoesNotInventActuation() {\n"
if cpp_tests.count(insert_before) != 1:
    raise RuntimeError("lamp safety test insertion point is not unique")
new_cpp_tests = r'''void testInitialTemperatureUnavailableDoesNotStartThermalRecovery() {
  LampSafetyController controller;
  const auto unavailable = controller.evaluate(input(1.0F, 24.0F, false, 0U, 1U));
  assert(!unavailable.effective_lamp_on);
  assert(unavailable.force_exhaust_on);
  assert(unavailable.thermal_latched);
  assert(unavailable.reason == LampSafetyReason::TemperatureUnavailable);

  const auto valid = controller.evaluate(input(1.0F, 27.0F, true, 0U, 2U));
  assert(valid.effective_lamp_on);
  assert(!valid.force_exhaust_on);
  assert(!valid.thermal_latched);
  assert(!valid.recovery_running);
  assert(valid.reason == LampSafetyReason::Safe);
}

void testTemperatureUnavailablePreservesRealOvertemperatureLatch() {
  LampSafetyController controller;
  const auto tripped = controller.evaluate(input(1.0F, 29.0F, true, 0U, 0U));
  assert(tripped.thermal_latched);
  assert(tripped.reason == LampSafetyReason::OverTemperature);

  const auto unavailable = controller.evaluate(input(1.0F, 24.0F, false, 0U, 100U));
  assert(!unavailable.effective_lamp_on);
  assert(unavailable.thermal_latched);
  assert(unavailable.reason == LampSafetyReason::TemperatureUnavailable);

  const auto warm = controller.evaluate(input(1.0F, 27.0F, true, 0U, 200U));
  assert(!warm.effective_lamp_on);
  assert(warm.thermal_latched);
  assert(!warm.recovery_running);
  assert(warm.reason == LampSafetyReason::RecoveryHold);

  const auto recovery_start = controller.evaluate(input(1.0F, 25.5F, true, 0U, 1'000U));
  assert(!recovery_start.effective_lamp_on);
  assert(recovery_start.thermal_latched);
  assert(recovery_start.recovery_running);

  const auto almost = controller.evaluate(input(1.0F, 25.5F, true, 0U, 600'999U));
  assert(!almost.effective_lamp_on);
  assert(almost.thermal_latched);

  const auto recovered = controller.evaluate(input(1.0F, 25.5F, true, 0U, 601'000U));
  assert(recovered.effective_lamp_on);
  assert(!recovered.thermal_latched);
  assert(!recovered.recovery_running);
  assert(recovered.reason == LampSafetyReason::Safe);
}

'''
cpp_tests = cpp_tests.replace(insert_before, new_cpp_tests + insert_before, 1)
main_anchor = "  testStaleInvalidAndNonFiniteTemperatureFailClosed();\n"
if cpp_tests.count(main_anchor) != 1:
    raise RuntimeError("lamp safety main insertion point is not unique")
cpp_tests = cpp_tests.replace(
    main_anchor,
    main_anchor
    + "  testInitialTemperatureUnavailableDoesNotStartThermalRecovery();\n"
    + "  testTemperatureUnavailablePreservesRealOvertemperatureLatch();\n",
    1,
)
Path(cpp_test_path).write_text(cpp_tests, encoding="utf-8")

# Stage27C soak: retain historical v2 parsing and accept the current v3 telemetry contract.
replace_once(
    "tools/stage27c_soak.py",
    'SOAK_MARKER = "soak_v=2 "\n',
    'SOAK_MARKERS = ((3, "soak_v=3 "), (2, "soak_v=2 "))\n',
)
replace_once(
    "tools/stage27c_soak.py",
    "REQUIRED_KEYS = {\n",
    "COMMON_REQUIRED_KEYS = {\n",
)
replace_once(
    "tools/stage27c_soak.py",
    '''    "xiaomi_rejected",\n    "outputs",\n}\n''',
    '''    "xiaomi_rejected",\n}\nREQUIRED_KEYS_BY_VERSION = {\n    2: COMMON_REQUIRED_KEYS | {"outputs"},\n    3: COMMON_REQUIRED_KEYS | {"output_v", "transport_active"},\n}\nV3_STORAGE_ALIASES = {\n    "storage_sd_mounted": "sd_mounted",\n    "storage_sd_mount_errors": "sd_mount_errors",\n    "storage_write_errors": "sd_write_errors",\n    "storage_queue_drops": "sd_queue_drops",\n    "storage_records_written": "sd_records_written",\n    "storage_records_skipped": "sd_records_skipped",\n}\n''',
)
replace_section(
    "tools/stage27c_soak.py",
    "def parse_soak_line(line: str) -> dict[str, Any] | None:\n",
    "\n\n@dataclass\n",
    '''def parse_soak_line(line: str) -> dict[str, Any] | None:\n    version: int | None = None\n    payload: str | None = None\n    for candidate_version, marker in SOAK_MARKERS:\n        marker_index = line.find(marker)\n        if marker_index >= 0:\n            version = candidate_version\n            payload = line[marker_index + len(marker) :].strip()\n            break\n    if version is None or payload is None:\n        return None\n\n    record: dict[str, Any] = {"soak_v": version}\n    for token in payload.split():\n        if "=" not in token:\n            continue\n        key, value = token.split("=", 1)\n        if key:\n            record[key] = _coerce(value)\n\n    missing = sorted(REQUIRED_KEYS_BY_VERSION[version].difference(record))\n    if missing:\n        raise ValueError(\n            f"missing Stage27C soak v{version} fields: {', '.join(missing)}"\n        )\n\n    if version == 3:\n        for source, target in V3_STORAGE_ALIASES.items():\n            if source in record:\n                record[target] = record[source]\n    return record\n''',
)
replace_once(
    "tools/stage27c_soak.py",
    '''        if record["outputs"] != "fake-locked":\n            self.bad_outputs += 1\n        if int(record["ble_scanning"]) != 1:\n            self.ble_not_scanning_records += 1\n        if int(record.get("io_status", 0)) != 0:\n            self.nonzero_io_status_records += 1\n''',
    '''        soak_version = int(record["soak_v"])\n        if soak_version == 2:\n            if record["outputs"] != "fake-locked":\n                self.bad_outputs += 1\n        elif int(record["output_v"]) != 2 or int(record["transport_active"]) != 0:\n            self.bad_outputs += 1\n        if int(record["ble_scanning"]) != 1:\n            self.ble_not_scanning_records += 1\n        # v3 output ownership moved behind OutputSupervisor. With the physical transport\n        # intentionally disabled, the legacy loop can report ActuatorApplyFailed/FaultLatched\n        # while the v3 physical-output fence is healthy. Preserve the legacy v2 check only.\n        if soak_version == 2 and int(record.get("io_status", 0)) != 0:\n            self.nonzero_io_status_records += 1\n''',
)

python_test = Path("tests/test_stage27c_soak.py")
if python_test.exists():
    raise RuntimeError("tests/test_stage27c_soak.py already exists")
python_test.write_text(
    r'''from __future__ import annotations

from tools.stage27c_soak import SoakSummary, parse_soak_line


def _common_fields() -> dict[str, object]:
    return {
        "firmware_sha": "deadbeef",
        "uptime_ms": 1_000,
        "reset_reason": 1,
        "heap_internal": 100_000,
        "heap_internal_min": 90_000,
        "heap_internal_largest": 50_000,
        "heap_psram": 2_000_000,
        "heap_psram_min": 1_900_000,
        "heap_psram_largest": 1_000_000,
        "stack_free": 4_096,
        "scd_age_ms": 100,
        "scd_read_errors": 0,
        "scd_invalid": 0,
        "scd_samples": 1,
        "rtc_available": 1,
        "rtc_trusted": 1,
        "rtc_reads": 1,
        "rtc_read_errors": 0,
        "rtc_untrusted": 0,
        "ble_scanning": 1,
        "ble_scan_starts": 1,
        "ble_scan_errors": 0,
        "ble_scan_restarts": 0,
        "ble_scan_completes": 0,
        "ble_adv_lock_drops": 0,
        "tp_age_ms": 100,
        "tp_packets": 1,
        "tp_accepted": 1,
        "tp_rejected": 0,
        "xiaomi_age_ms": 100,
        "xiaomi_packets": 1,
        "xiaomi_accepted": 1,
        "xiaomi_rejected": 0,
        "runtime_status": 0,
        "io_status": 0,
    }


def _line(version: int, **overrides: object) -> str:
    fields = _common_fields()
    if version == 2:
        fields["outputs"] = "fake-locked"
    elif version == 3:
        fields.update(
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
                "storage_records_written": 2,
                "storage_records_skipped": 0,
                "storage_fallbacks": 0,
                "storage_sd_recoveries": 0,
                "storage_last_write_ms": 900,
            }
        )
    else:
        raise ValueError(version)
    fields.update(overrides)
    payload = " ".join(f"{key}={value}" for key, value in fields.items())
    return f"I (1234) climate: soak_v={version} {payload}"


def test_v3_parser_accepts_current_contract_and_normalizes_storage() -> None:
    record = parse_soak_line(_line(3, io_status=3))
    assert record is not None
    assert record["soak_v"] == 3
    assert record["sd_mounted"] == 1
    assert record["sd_write_errors"] == 0
    assert record["sd_queue_drops"] == 0
    assert record["sd_records_written"] == 2

    summary = SoakSummary()
    summary.observe(record)
    assert summary.bad_outputs == 0
    assert summary.nonzero_io_status_records == 0
    assert summary.violations(require_sd=True) == []


def test_v3_parser_rejects_an_active_physical_output_transport() -> None:
    record = parse_soak_line(_line(3, transport_active=1))
    assert record is not None
    summary = SoakSummary()
    summary.observe(record)
    assert summary.bad_outputs == 1
    assert "outputs not fake-locked" in summary.violations()


def test_v2_parser_keeps_legacy_io_status_acceptance_rule() -> None:
    record = parse_soak_line(_line(2, io_status=2))
    assert record is not None
    assert record["soak_v"] == 2
    summary = SoakSummary()
    summary.observe(record)
    assert summary.bad_outputs == 0
    assert summary.nonzero_io_status_records == 1
    assert "nonzero IO status" in summary.violations()
''',
    encoding="utf-8",
)

# Keep status documentation current without hard-coding a future qualification result.
replace_section(
    "docs/CURRENT_STATUS.md",
    "## Current phase\n",
    "## Structural cleanup closeout\n",
    '''## Current phase\n\nThe architecture/quality refactor and the follow-up structural cleanup are complete. Final release-readiness hardening on current `main` closes two issues found by the bounded post-flash inspection:\n\n- `tools/stage27c_soak.py` accepts both historical `soak_v=2` and current `soak_v=3`; v3 fake-output acceptance uses the explicit `output_v=2` / `transport_active=0` physical-output fence rather than the legacy loop `io_status`;\n- startup `TemperatureUnavailable` remains fail-closed for the current cycle but no longer invents an over-temperature latch or a 10-minute recovery hold; a real thermal trip remains latched across later temporary temperature unavailability.\n\nThe exact acceptance identity is intentionally not duplicated in this status file because the firmware embeds the Git SHA. Final closeout requires the same exact `main` commit to pass the repository guards, host/Python tests, clang-tidy, ESP-IDF builds, canonical GitHub checks and the bounded hardware task `20260912-final-main-hardware-qualification-v1`. The terminal task evidence is authoritative for physical qualification.\n\n''',
)
replace_once(
    "docs/CURRENT_STATUS.md",
    """The current code-bearing identity `0a7097a30280ec0f7bb408799c07093761d63e88` has passed software/build/CI verification but has **not** yet completed a new bounded physical qualification. It is ready to flash; do not call it hardware-qualified until the physical run finishes successfully.\n""",
    """`0a7097a30280ec0f7bb408799c07093761d63e88` is the software-verified structural-cleanup baseline. Current `main` adds the final release-readiness hardening above. Treat the current executable as hardware-qualified only when `20260912-final-main-hardware-qualification-v1` is terminal PASS on that exact same commit; do not infer qualification from an ancestor or a documentation-only descendant.\n""",
)
replace_section(
    "docs/CURRENT_STATUS.md",
    "## Immediate next work\n",
    "",
    '''## Immediate next work\n\nAfter the exact current `main` commit has green canonical checks and terminal PASS from `20260912-final-main-hardware-qualification-v1`, resume normal product development from `docs/PROJECT_ROADMAP.md`. The cleanup/hardening line is closed at that point; avoid another broad architecture rewrite unless concrete evidence exposes a new responsibility or ownership problem.\n''',
)

replace_once(
    "docs/CHANGELOG.md",
    "## Unreleased\n\n",
    '''## Unreleased\n\n### Final release-readiness hardening — 2026-09-12\n\n- Updated the Stage27C soak parser to preserve historical `soak_v=2` support while accepting current `soak_v=3` telemetry and its renamed storage fields.\n- For v3 fake-output soak acceptance, validate the explicit physical-output fence (`output_v=2`, `transport_active=0`) instead of treating legacy loop `io_status=2/3` as a physical-output failure.\n- Kept missing/stale lamp temperature fail-closed without synthesizing a thermal trip; a genuine over-temperature trip still survives temporary temperature loss and requires the full recovery hold.\n- Added regression coverage for both parser versions and both lamp-safety state-history cases.\n- Confirmed the intended long-lived remote branches are only `main`, `agent-control` and `gh-pages`; the latter two are required control/publishing branches, not cleanup candidates.\n\n''',
)

print("FINAL_RELEASE_HARDENING_PATCH_APPLIED")
