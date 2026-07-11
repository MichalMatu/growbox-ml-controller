"""Capture newline-delimited JSON records from the demo firmware."""

from __future__ import annotations

import argparse
import json
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

import serial


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def capture(
    port: str,
    output: Path,
    *,
    baud: int = 115_200,
    invalid: str = "mark",
    timeout: float = 1.0,
) -> tuple[int, int]:
    """Capture until interrupted and return ``(valid, invalid)`` counts."""

    if invalid not in {"mark", "skip"}:
        raise ValueError("invalid policy must be 'mark' or 'skip'")

    output.parent.mkdir(parents=True, exist_ok=True)
    stop = False

    def request_stop(_signum: int, _frame: object) -> None:
        nonlocal stop
        stop = True

    previous_handler = signal.signal(signal.SIGINT, request_stop)
    valid_count = 0
    invalid_count = 0
    try:
        with serial.Serial(port=port, baudrate=baud, timeout=timeout) as device:
            with output.open("a", encoding="utf-8", buffering=1) as destination:
                while not stop:
                    raw = device.readline()
                    if not raw:
                        continue
                    text = raw.decode("utf-8", errors="replace").strip()
                    try:
                        record = json.loads(text)
                        if not isinstance(record, dict):
                            raise ValueError("record is not an object")
                    except (json.JSONDecodeError, ValueError) as exc:
                        invalid_count += 1
                        if invalid == "mark":
                            marker = {
                                "type": "invalid_serial_line",
                                "captured_at": _utc_now(),
                                "error": str(exc),
                                "line": text,
                            }
                            destination.write(json.dumps(marker, separators=(",", ":")) + "\n")
                        continue

                    destination.write(json.dumps(record, separators=(",", ":")) + "\n")
                    valid_count += 1
    finally:
        signal.signal(signal.SIGINT, previous_handler)
    return valid_count, invalid_count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="Serial device, for example /dev/cu.usbserial-10")
    parser.add_argument("--output", required=True, type=Path, help="Append NDJSON records here")
    parser.add_argument("--baud", type=int, default=115_200)
    parser.add_argument("--timeout", type=float, default=1.0)
    parser.add_argument(
        "--invalid", choices=("mark", "skip"), default="mark", help="How to handle malformed lines"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        valid, invalid = capture(
            args.port,
            args.output,
            baud=args.baud,
            invalid=args.invalid,
            timeout=args.timeout,
        )
    except serial.SerialException as exc:
        print(f"serial capture failed: {exc}", file=sys.stderr)
        return 2
    print(f"capture stopped: {valid} valid records, {invalid} invalid lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
