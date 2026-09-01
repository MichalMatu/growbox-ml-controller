"""Bounded Stage27C overnight serial soak capture and anomaly summarizer."""

from __future__ import annotations

import argparse
import importlib
import json
import math
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path[0] = str(Path(__file__).resolve().parents[1])

serial = importlib.import_module("serial")
list_ports = importlib.import_module("serial.tools.list_ports")

SOAK_MARKER = "soak_v=2 "
CH340_VID = 0x1A86
CH340_PID = 0x7523
COUNTER_KEYS = (
    "scd_samples",
    "scd_read_errors",
    "scd_invalid",
    "rtc_reads",
    "rtc_read_errors",
    "rtc_untrusted",
    "ble_scan_starts",
    "ble_scan_errors",
    "ble_scan_restarts",
    "ble_scan_completes",
    "ble_adv_lock_drops",
    "tp_packets",
    "tp_accepted",
    "tp_rejected",
    "xiaomi_packets",
    "xiaomi_accepted",
    "xiaomi_rejected",
)
REQUIRED_KEYS = {
    "firmware_sha",
    "uptime_ms",
    "reset_reason",
    "heap_internal",
    "heap_internal_min",
    "heap_internal_largest",
    "heap_psram",
    "heap_psram_min",
    "heap_psram_largest",
    "stack_free",
    "scd_age_ms",
    "scd_read_errors",
    "scd_invalid",
    "rtc_available",
    "rtc_trusted",
    "rtc_read_errors",
    "ble_scanning",
    "ble_scan_errors",
    "ble_scan_restarts",
    "ble_adv_lock_drops",
    "tp_age_ms",
    "tp_packets",
    "tp_accepted",
    "tp_rejected",
    "xiaomi_age_ms",
    "xiaomi_packets",
    "xiaomi_accepted",
    "xiaomi_rejected",
    "outputs",
}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _coerce(value: str) -> Any:
    try:
        return int(value, 10)
    except ValueError:
        try:
            number = float(value)
            return number if math.isfinite(number) else value
        except ValueError:
            return value


def parse_soak_line(line: str) -> dict[str, Any] | None:
    marker_index = line.find(SOAK_MARKER)
    if marker_index < 0:
        return None
    payload = line[marker_index + len(SOAK_MARKER) :].strip()
    record: dict[str, Any] = {"soak_v": 2}
    for token in payload.split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        if key:
            record[key] = _coerce(value)
    missing = sorted(REQUIRED_KEYS.difference(record))
    if missing:
        raise ValueError(f"missing Stage27C soak fields: {', '.join(missing)}")
    return record


@dataclass
class SoakSummary:
    expected_sha: str | None = None
    records: int = 0
    parse_errors: int = 0
    serial_disconnects: int = 0
    resets: int = 0
    firmware_changes: int = 0
    unexpected_sha_records: int = 0
    bad_outputs: int = 0
    ble_not_scanning_records: int = 0
    counter_regressions: int = 0
    nonzero_io_status_records: int = 0
    first_uptime_ms: int | None = None
    last_uptime_ms: int | None = None
    firmware_sha: str | None = None
    min_heap_internal: int | None = None
    min_heap_internal_largest: int | None = None
    min_heap_psram: int | None = None
    min_heap_psram_largest: int | None = None
    min_stack_free: int | None = None
    max_scd_age_ms: int = 0
    max_tp_age_ms: int = 0
    max_xiaomi_age_ms: int = 0
    max_scd_read_errors: int = 0
    max_scd_invalid: int = 0
    max_rtc_read_errors: int = 0
    max_rtc_untrusted: int = 0
    max_ble_scan_errors: int = 0
    max_ble_adv_lock_drops: int = 0
    _previous_counters: dict[str, int] = field(default_factory=dict, repr=False)

    def observe(self, record: dict[str, Any]) -> None:
        uptime_ms = int(record["uptime_ms"])
        sha = str(record["firmware_sha"])

        if self.first_uptime_ms is None:
            self.first_uptime_ms = uptime_ms
        elif self.last_uptime_ms is not None and uptime_ms < self.last_uptime_ms:
            self.resets += 1
        self.last_uptime_ms = uptime_ms

        if self.firmware_sha is None:
            self.firmware_sha = sha
        elif sha != self.firmware_sha:
            self.firmware_changes += 1
            self.firmware_sha = sha
        if self.expected_sha is not None and sha != self.expected_sha:
            self.unexpected_sha_records += 1

        if record["outputs"] != "fake-locked":
            self.bad_outputs += 1
        if int(record["ble_scanning"]) != 1:
            self.ble_not_scanning_records += 1
        if int(record.get("io_status", 0)) != 0:
            self.nonzero_io_status_records += 1

        for key in COUNTER_KEYS:
            value = int(record[key])
            previous = self._previous_counters.get(key)
            if previous is not None and value < previous:
                self.counter_regressions += 1
            self._previous_counters[key] = value

        self.min_heap_internal = _minimum(self.min_heap_internal, int(record["heap_internal"]))
        self.min_heap_internal_largest = _minimum(
            self.min_heap_internal_largest, int(record["heap_internal_largest"])
        )
        self.min_heap_psram = _minimum(self.min_heap_psram, int(record["heap_psram"]))
        self.min_heap_psram_largest = _minimum(
            self.min_heap_psram_largest, int(record["heap_psram_largest"])
        )
        self.min_stack_free = _minimum(self.min_stack_free, int(record["stack_free"]))
        self.max_scd_age_ms = max(self.max_scd_age_ms, int(record["scd_age_ms"]))
        self.max_tp_age_ms = max(self.max_tp_age_ms, int(record["tp_age_ms"]))
        self.max_xiaomi_age_ms = max(self.max_xiaomi_age_ms, int(record["xiaomi_age_ms"]))
        self.max_scd_read_errors = max(self.max_scd_read_errors, int(record["scd_read_errors"]))
        self.max_scd_invalid = max(self.max_scd_invalid, int(record["scd_invalid"]))
        self.max_rtc_read_errors = max(self.max_rtc_read_errors, int(record["rtc_read_errors"]))
        self.max_rtc_untrusted = max(self.max_rtc_untrusted, int(record["rtc_untrusted"]))
        self.max_ble_scan_errors = max(self.max_ble_scan_errors, int(record["ble_scan_errors"]))
        self.max_ble_adv_lock_drops = max(
            self.max_ble_adv_lock_drops, int(record["ble_adv_lock_drops"])
        )
        self.records += 1

    def violations(
        self,
        *,
        max_scd_age_ms: int | None = None,
        max_tp_age_ms: int | None = None,
        max_xiaomi_age_ms: int | None = None,
    ) -> list[str]:
        failures: list[str] = []
        hard_checks = {
            "no soak records": self.records == 0,
            "parse errors": self.parse_errors > 0,
            "serial disconnects": self.serial_disconnects > 0,
            "MCU reset/uptime regression": self.resets > 0,
            "firmware identity changed": self.firmware_changes > 0,
            "unexpected firmware SHA": self.unexpected_sha_records > 0,
            "outputs not fake-locked": self.bad_outputs > 0,
            "BLE scanner inactive": self.ble_not_scanning_records > 0,
            "counter regression": self.counter_regressions > 0,
            "nonzero IO status": self.nonzero_io_status_records > 0,
            "SCD41 read errors": self.max_scd_read_errors > 0,
            "SCD41 invalid measurements": self.max_scd_invalid > 0,
            "RTC read errors": self.max_rtc_read_errors > 0,
            "RTC untrusted reads": self.max_rtc_untrusted > 0,
            "BLE scan start errors": self.max_ble_scan_errors > 0,
            "BLE advertisement lock drops": self.max_ble_adv_lock_drops > 0,
        }
        failures.extend(label for label, failed in hard_checks.items() if failed)
        if max_scd_age_ms is not None and self.max_scd_age_ms > max_scd_age_ms:
            failures.append(f"SCD41 age exceeded {max_scd_age_ms} ms")
        if max_tp_age_ms is not None and self.max_tp_age_ms > max_tp_age_ms:
            failures.append(f"TP357 age exceeded {max_tp_age_ms} ms")
        if max_xiaomi_age_ms is not None and self.max_xiaomi_age_ms > max_xiaomi_age_ms:
            failures.append(f"Xiaomi age exceeded {max_xiaomi_age_ms} ms")
        return failures

    def as_dict(self, violations: list[str]) -> dict[str, Any]:
        public = {key: value for key, value in vars(self).items() if not key.startswith("_")}
        public["violations"] = violations
        public["passed"] = not violations
        return public


def _minimum(current: int | None, value: int) -> int:
    return value if current is None else min(current, value)


def detect_ch340_port() -> str:
    matches = [
        port.device
        for port in list_ports.comports()
        if port.vid == CH340_VID and port.pid == CH340_PID
    ]
    if not matches:
        raise RuntimeError("CH340 serial adapter 1A86:7523 not found")
    if len(matches) > 1:
        raise RuntimeError(f"multiple CH340 adapters found: {', '.join(sorted(matches))}")
    return matches[0]


def _write_summary(path: Path, summary: SoakSummary, violations: list[str]) -> None:
    payload = summary.as_dict(violations)
    payload["updated_at"] = _utc_now()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def capture(args: argparse.Namespace) -> tuple[SoakSummary, list[str]]:
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    parsed_path = output_dir / "soak.ndjson"
    summary_path = output_dir / "summary.json"
    summary = SoakSummary(expected_sha=args.expected_sha)
    started = time.monotonic()
    next_progress = started
    segment_index = -1
    raw_file = None
    device = None

    try:
        with parsed_path.open("a", encoding="utf-8", buffering=1) as parsed:
            while time.monotonic() - started < args.duration:
                elapsed = time.monotonic() - started
                wanted_segment = int(elapsed // args.segment_seconds)
                if wanted_segment != segment_index:
                    if raw_file is not None:
                        raw_file.close()
                    segment_index = wanted_segment
                    raw_file = (output_dir / f"raw-{segment_index + 1:03d}.log").open(
                        "a", encoding="utf-8", buffering=1
                    )

                if device is None:
                    try:
                        port = args.port or detect_ch340_port()
                        device = serial.Serial(
                            port=port,
                            baudrate=args.baud,
                            timeout=args.read_timeout,
                        )
                    except (serial.SerialException, RuntimeError) as exc:
                        summary.serial_disconnects += 1
                        print(f"[AGENT_PROGRESS] serial_reconnect_wait error={exc}", flush=True)
                        time.sleep(args.reconnect_seconds)
                        continue

                try:
                    raw = device.readline()
                except serial.SerialException as exc:
                    summary.serial_disconnects += 1
                    print(f"[AGENT_PROGRESS] serial_disconnected error={exc}", flush=True)
                    device.close()
                    device = None
                    time.sleep(args.reconnect_seconds)
                    continue

                if raw:
                    text = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                    raw_file.write(text + "\n")
                    try:
                        record = parse_soak_line(text)
                    except ValueError as exc:
                        summary.parse_errors += 1
                        parsed.write(
                            json.dumps(
                                {
                                    "type": "parse_error",
                                    "captured_at": _utc_now(),
                                    "segment": segment_index + 1,
                                    "error": str(exc),
                                    "line": text,
                                },
                                separators=(",", ":"),
                            )
                            + "\n"
                        )
                    else:
                        if record is not None:
                            record["captured_at"] = _utc_now()
                            record["segment"] = segment_index + 1
                            summary.observe(record)
                            parsed.write(json.dumps(record, separators=(",", ":")) + "\n")

                now = time.monotonic()
                if now >= next_progress:
                    print(
                        "[AGENT_PROGRESS] "
                        f"stage27c_soak elapsed_s={int(now - started)} records={summary.records} "
                        f"resets={summary.resets} disconnects={summary.serial_disconnects} "
                        f"max_tp_age_ms={summary.max_tp_age_ms} "
                        f"max_xiaomi_age_ms={summary.max_xiaomi_age_ms}",
                        flush=True,
                    )
                    next_progress = now + args.progress_seconds
                    current_violations = summary.violations(
                        max_scd_age_ms=args.max_scd_age_ms,
                        max_tp_age_ms=args.max_tp_age_ms,
                        max_xiaomi_age_ms=args.max_xiaomi_age_ms,
                    )
                    _write_summary(summary_path, summary, current_violations)
    finally:
        if device is not None:
            device.close()
        if raw_file is not None:
            raw_file.close()

    violations = summary.violations(
        max_scd_age_ms=args.max_scd_age_ms,
        max_tp_age_ms=args.max_tp_age_ms,
        max_xiaomi_age_ms=args.max_xiaomi_age_ms,
    )
    _write_summary(summary_path, summary, violations)
    return summary, violations


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="Serial device. Omit to auto-detect CH340 1A86:7523.")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--duration", type=int, default=600)
    parser.add_argument("--segment-seconds", type=int, default=6000)
    parser.add_argument("--progress-seconds", type=int, default=600)
    parser.add_argument("--reconnect-seconds", type=float, default=5.0)
    parser.add_argument("--read-timeout", type=float, default=1.0)
    parser.add_argument("--baud", type=int, default=115_200)
    parser.add_argument("--expected-sha")
    parser.add_argument("--max-scd-age-ms", type=int)
    parser.add_argument("--max-tp-age-ms", type=int)
    parser.add_argument("--max-xiaomi-age-ms", type=int)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero when the final summary contains an acceptance violation.",
    )
    return parser


def _positive(parser: argparse.ArgumentParser, name: str, value: int | float) -> None:
    if value <= 0:
        parser.error(f"{name} must be greater than zero")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _positive(parser, "--duration", args.duration)
    _positive(parser, "--segment-seconds", args.segment_seconds)
    _positive(parser, "--progress-seconds", args.progress_seconds)
    _positive(parser, "--reconnect-seconds", args.reconnect_seconds)
    _positive(parser, "--read-timeout", args.read_timeout)

    try:
        summary, violations = capture(args)
    except KeyboardInterrupt:
        print("Stage27C soak interrupted", file=sys.stderr)
        return 130

    print(json.dumps(summary.as_dict(violations), indent=2, sort_keys=True))
    return 1 if args.strict and violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
