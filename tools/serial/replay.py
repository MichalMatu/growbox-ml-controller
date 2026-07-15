"""Replay JSONL commands to the demo firmware and capture the session."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import serial


class ReplayError(RuntimeError):
    """Raised when the firmware rejects a replay command."""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def load_commands(path: Path) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                command = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc.msg}") from exc
            if not isinstance(command, dict):
                raise ValueError(f"{path}:{line_number}: command must be a JSON object")
            commands.append(command)
    if not commands:
        raise ValueError(f"{path}: no commands found")
    return commands


def _write_session(destination: Any, direction: str, payload: Any) -> None:
    entry = {"timestamp": _utc_now(), "direction": direction, "payload": payload}
    destination.write(json.dumps(entry, separators=(",", ":")) + "\n")
    destination.flush()


def _expected_response(command: dict[str, Any]) -> tuple[str, str | None]:
    command_name = command.get("command")
    if command_name == "step":
        return "decision", None
    if command_name == "status":
        return "status", None
    return "ack", command_name if isinstance(command_name, str) else None


def _matches_response(response: dict[str, Any], expected: tuple[str, str | None]) -> bool:
    response_type, command_name = expected
    if response.get("type") != response_type:
        return False
    return response_type != "ack" or response.get("command") == command_name


def _expected_response_description(expected: tuple[str, str | None]) -> str:
    response_type, command_name = expected
    if response_type == "ack":
        return f"ack for command {command_name!r}"
    return response_type


def replay(
    port: str,
    scenario: Path,
    output: Path,
    *,
    baud: int = 115_200,
    timeout: float = 3.0,
    settle: float = 0.1,
) -> int:
    if timeout <= 0:
        raise ValueError("timeout must be greater than zero")

    commands = load_commands(scenario)
    output.parent.mkdir(parents=True, exist_ok=True)
    responses = 0

    read_timeout = min(0.1, timeout)
    with serial.Serial(port=port, baudrate=baud, timeout=read_timeout) as device:
        time.sleep(0.25)
        device.reset_input_buffer()
        with output.open("w", encoding="utf-8", buffering=1) as destination:
            for index, command in enumerate(commands, 1):
                expected = _expected_response(command)
                encoded = json.dumps(command, separators=(",", ":")).encode("utf-8") + b"\n"
                device.write(encoded)
                device.flush()
                _write_session(destination, "tx", command)

                deadline = time.monotonic() + timeout
                response: dict[str, Any] | None = None
                while time.monotonic() < deadline:
                    raw = device.readline()
                    if not raw:
                        continue
                    text = raw.decode("utf-8", errors="replace").strip()
                    try:
                        parsed = json.loads(text)
                    except json.JSONDecodeError:
                        _write_session(destination, "rx_invalid", text)
                        continue
                    _write_session(destination, "rx", parsed)
                    if not isinstance(parsed, dict):
                        continue
                    if parsed.get("type") == "error":
                        code = parsed.get("code", "unknown_error")
                        message = parsed.get("message", "firmware returned no message")
                        command_name = command.get("command", "<missing>")
                        raise ReplayError(
                            f"command {index} ({command_name!r}) failed: {code}: {message}"
                        )
                    if _matches_response(parsed, expected):
                        response = parsed
                        break

                if response is None:
                    description = _expected_response_description(expected)
                    raise TimeoutError(
                        f"command {index} received no matching {description} within {timeout:g}s"
                    )
                responses += 1
                if settle > 0:
                    time.sleep(settle)
    return responses


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--scenario", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--baud", type=int, default=115_200)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--settle", type=float, default=0.1)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        count = replay(
            args.port,
            args.scenario,
            args.output,
            baud=args.baud,
            timeout=args.timeout,
            settle=args.settle,
        )
    except (
        ValueError,
        ReplayError,
        TimeoutError,
        serial.SerialException,
        OSError,
    ) as exc:
        print(f"replay failed: {exc}", file=sys.stderr)
        return 2
    print(f"replayed {count} commands; session written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
