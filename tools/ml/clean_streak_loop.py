"""Run host+board+panel verification until N consecutive clean runs.

Ensures exclusive serial access: disconnect panel before direct serial tests,
then panel audit reconnects.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PORT = "/dev/cu.usbmodem1101"
PANEL = "http://127.0.0.1:8765"
OUT = ROOT / "build" / "audit" / "loop"


def panel_disconnect() -> None:
    try:
        req = urllib.request.Request(
            f"{PANEL}/api/disconnect",
            data=b"{}",
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception:
        pass
    time.sleep(0.6)


def panel_up() -> bool:
    try:
        urllib.request.urlopen(f"{PANEL}/api/ports", timeout=2)
        return True
    except Exception:
        return False


def run(cmd: list[str], log: Path, *, env: dict | None = None) -> int:
    import os

    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    with log.open("w", encoding="utf-8") as fh:
        proc = subprocess.run(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT, env=full_env)
    return proc.returncode


def load_summary(path: Path) -> tuple[int, int, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    summary = data["summary"]
    return int(summary["error_count"]), int(summary["warn_count"]), summary.get("by_code", {})


def main() -> int:
    target = 5
    streak = 0
    run_i = 0
    max_runs = 15
    OUT.mkdir(parents=True, exist_ok=True)

    if not panel_up():
        print("panel not running on :8765 — start: python -m tools.panel", file=sys.stderr)
        return 2

    while streak < target and run_i < max_runs:
        run_i += 1
        print(f"======== CLEAN STREAK RUN {run_i} (streak={streak}/{target}) ========", flush=True)
        fail = False
        notes: list[str] = []

        # Host C++
        if run(
            ["ctest", "--test-dir", "build/host-tests", "--output-on-failure"],
            OUT / f"run{run_i}_host.txt",
        ):
            fail = True
            notes.append("host fail")

        # Exclusive serial for pytest hardware + board audit
        panel_disconnect()
        rc = run(
            [
                ".venv/bin/python",
                "-m",
                "pytest",
                "tests/test_board_e2e.py",
                "tests/test_contract_active.py",
                "tests/test_scenario_payload.py",
                "tests/test_export.py",
                "tests/test_panel_sync.py",
                "-q",
                "--tb=line",
            ],
            OUT / f"run{run_i}_pytest.txt",
            env={"GROWBOX_BOARD_PORT": PORT},
        )
        if rc:
            fail = True
            notes.append("pytest fail")

        panel_disconnect()
        time.sleep(0.4)
        board_report = OUT / f"run{run_i}_board.json"
        run(
            [
                ".venv/bin/python",
                "-m",
                "tools.ml.board_engine_audit",
                "--port",
                PORT,
                "--report",
                str(board_report),
            ],
            OUT / f"run{run_i}_board.log",
        )
        try:
            be, bw, bc = load_summary(board_report)
        except Exception as exc:
            fail = True
            be, bw, bc = 99, 99, {"load": str(exc)}
        print(f"  board errors/warns: {be} {bw} {bc}", flush=True)
        if be:
            fail = True
            notes.append(f"board errors={be}")

        # Panel matrix (owns serial via bridge)
        panel_disconnect()
        time.sleep(0.3)
        panel_report = OUT / f"run{run_i}_panel.json"
        run(
            [
                ".venv/bin/python",
                "-m",
                "tools.ml.panel_endpoint_audit",
                "--base",
                PANEL,
                "--port",
                PORT,
                "--report",
                str(panel_report),
            ],
            OUT / f"run{run_i}_panel.log",
        )
        try:
            pe, pw, pc = load_summary(panel_report)
        except Exception as exc:
            fail = True
            pe, pw, pc = 99, 99, {"load": str(exc)}
        print(f"  panel errors/warns: {pe} {pw} {pc}", flush=True)
        if pe:
            fail = True
            notes.append(f"panel errors={pe}")

        # Clean = zero errors and zero warns
        if not fail and be == 0 and pe == 0 and bw == 0 and pw == 0:
            streak += 1
            print(f"CLEAN — streak {streak}/{target}", flush=True)
        else:
            streak = 0
            print(
                f"NOT CLEAN ({', '.join(notes) or f'warns b={bw} p={pw}'}) — streak reset",
                flush=True,
            )
            if pe or be or bw or pw:
                for label, path in ("board", board_report), ("panel", panel_report):
                    try:
                        data = json.loads(path.read_text(encoding="utf-8"))
                        for item in (data["summary"].get("errors") or [])[:6]:
                            print(
                                f"  ERR {label}: {item.get('case')} {item.get('code')} {item.get('message')}",
                                flush=True,
                            )
                        for item in (data["summary"].get("warns") or [])[:6]:
                            print(
                                f"  WARN {label}: {item.get('case')} {item.get('code')} {item.get('message')}",
                                flush=True,
                            )
                    except Exception:
                        pass

    print(f"FINAL STREAK={streak} after {run_i} runs", flush=True)
    return 0 if streak >= target else 2


if __name__ == "__main__":
    raise SystemExit(main())
