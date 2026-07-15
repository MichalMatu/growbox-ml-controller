"""Local web control panel for the growbox ML demo firmware."""

from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from tools.panel.bridge import SerialBridge, SerialBridgeError
from tools.panel.form_schema import build_panel_schema, default_scenario, list_scenario_presets

STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_MIME = {
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}
BRIDGE = SerialBridge()


PANEL_PERMISSIONS_POLICY = "unload=(self)"


def _panel_headers(handler: BaseHTTPRequestHandler) -> None:
    handler.send_header("Permissions-Policy", PANEL_PERMISSIONS_POLICY)


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: Any) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    _panel_headers(handler)
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    parsed = json.loads(raw.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("JSON body must be an object")
    return parsed


class PanelHandler(BaseHTTPRequestHandler):
    server_version = "GrowboxPanel/0.1"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        try:
            if path in {"/", "/index.html"}:
                self._serve_index()
            elif path == "/api/schema":
                _json_response(self, HTTPStatus.OK, build_panel_schema())
            elif path == "/api/state":
                _json_response(self, HTTPStatus.OK, BRIDGE.snapshot())
            elif path == "/api/diagnostics":
                query = parse_qs(urlparse(self.path).query)
                refresh = query.get("refresh", ["0"])[0].lower() in {"1", "true", "yes"}
                if refresh and BRIDGE.snapshot().get("connected"):
                    BRIDGE.request_diagnostics()
                _json_response(self, HTTPStatus.OK, BRIDGE.diagnostics_snapshot())
            elif path == "/api/ports":
                _json_response(self, HTTPStatus.OK, {"ports": BRIDGE.list_ports()})
            elif path == "/api/presets":
                _json_response(self, HTTPStatus.OK, {"presets": list_scenario_presets()})
            elif path in {"/favicon.ico", "/favicon.svg"}:
                self._serve_favicon()
            elif path == "/panel.css":
                self._serve_static_file(STATIC_DIR / "panel.css")
            elif path.startswith("/css/"):
                rel = path.removeprefix("/css/")
                if ".." in rel or rel.startswith("/"):
                    _json_response(self, HTTPStatus.NOT_FOUND, {"error": "not_found"})
                else:
                    self._serve_static_file(STATIC_DIR / "css" / rel)
            elif path.startswith("/js/"):
                rel = path.removeprefix("/js/")
                if ".." in rel or rel.startswith("/"):
                    _json_response(self, HTTPStatus.NOT_FOUND, {"error": "not_found"})
                else:
                    self._serve_static_file(STATIC_DIR / "js" / rel)
            else:
                _json_response(self, HTTPStatus.NOT_FOUND, {"error": "not_found"})
        except Exception as exc:  # noqa: BLE001 - surface to UI
            _json_response(self, HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            body = _read_json(self)
            if path == "/api/connect":
                BRIDGE.connect(body.get("port", ""), baud=int(body.get("baud", 115200)))
                _json_response(self, HTTPStatus.OK, BRIDGE.snapshot())
            elif path == "/api/disconnect":
                BRIDGE.disconnect()
                _json_response(self, HTTPStatus.OK, BRIDGE.snapshot())
            elif path == "/api/command":
                BRIDGE.send_command(body)
                _json_response(self, HTTPStatus.OK, {"ok": True})
            elif path == "/api/load_scenario":
                scenario = body.get("scenario")
                if not isinstance(scenario, dict):
                    raise ValueError("scenario must be an object")
                seed = body.get("seed")
                BRIDGE.load_scenario(scenario, seed=int(seed) if seed is not None else None)
                _json_response(self, HTTPStatus.OK, {"ok": True})
            elif path == "/api/step":
                sensors = body.get("sensors")
                validity = body.get("validity")
                actuators = body.get("actuators")
                command: dict[str, Any] = {"command": "step"}
                if isinstance(sensors, dict):
                    command["sensors"] = sensors
                if isinstance(validity, dict):
                    command["validity"] = validity
                if isinstance(actuators, dict):
                    command["actuators"] = actuators
                BRIDGE.send_command(command)
                _json_response(self, HTTPStatus.OK, {"ok": True})
            elif path == "/api/defaults":
                seed = int(body.get("seed", 101))
                preset = str(body.get("preset", "nominal"))
                _json_response(
                    self,
                    HTTPStatus.OK,
                    {"scenario": default_scenario(seed=seed, preset=preset), "preset": preset},
                )
            else:
                _json_response(self, HTTPStatus.NOT_FOUND, {"error": "not_found"})
        except (ValueError, SerialBridgeError) as exc:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            _json_response(self, HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def _serve_index(self) -> None:
        index_path = STATIC_DIR / "index.html"
        body = index_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        _panel_headers(self)
        self.end_headers()
        self.wfile.write(body)

    def _serve_favicon(self) -> None:
        self._serve_static_file(STATIC_DIR / "favicon.svg")

    def _serve_static_file(self, file_path: Path) -> None:
        if not file_path.is_file():
            _json_response(self, HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        body = file_path.read_bytes()
        mime = STATIC_MIME.get(file_path.suffix, "application/octet-stream")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        if file_path.suffix in {".css", ".js"}:
            self.send_header("Cache-Control", "no-cache")
        elif file_path.suffix in {".svg", ".ico"}:
            self.send_header("Cache-Control", "public, max-age=3600")
        _panel_headers(self)
        self.end_headers()
        self.wfile.write(body)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), PanelHandler)
    print(f"Growbox panel: http://{args.host}:{args.port}")
    print("Połącz płytkę w panelu (port usbmodem), potem Wyślij scenariusz → Krok.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        BRIDGE.disconnect()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
