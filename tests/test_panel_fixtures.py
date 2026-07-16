"""Shared panel HTTP test fixtures."""

from __future__ import annotations

import threading
from http.server import ThreadingHTTPServer

import pytest
from tests.test_panel import FakeBridge

from tools.panel import server as panel_server
from tools.panel.server import PanelHandler


@pytest.fixture
def panel_http_server(monkeypatch):
    fake = FakeBridge()
    monkeypatch.setattr(panel_server, "BRIDGE", fake)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), PanelHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        yield fake, base
    finally:
        httpd.shutdown()
        thread.join(timeout=2.0)
