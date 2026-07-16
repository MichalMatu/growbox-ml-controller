"""Panel visual regression — element screenshots vs committed baselines."""

from __future__ import annotations

import os
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
from tests.test_panel import FakeBridge

from tools.panel import server as panel_server
from tools.panel.server import PanelHandler

try:
    from PIL import Image, ImageChops
except ImportError:  # pragma: no cover - optional dev dependency
    Image = ImageChops = None  # type: ignore[misc, assignment]

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - optional dev dependency
    sync_playwright = None  # type: ignore[misc, assignment]

pytestmark = pytest.mark.skipif(
    Image is None or ImageChops is None or sync_playwright is None,
    reason="panel visual regression requires pillow and playwright (make setup-dev)",
)

SCREENSHOT_DIR = Path(__file__).resolve().parent / "fixtures" / "panel_screenshots"
VIEWPORT = {"width": 1400, "height": 900}
MAX_CHANNEL_DIFF = 12
MAX_MISMATCH_RATIO = 0.02

PANEL_SHOTS = (
    ("donice-block", ".pots-block"),
    ("sensors-panel", ".sensors-panel"),
    ("toolbar", ".top-bar"),
)


def _image_diff_ratio(actual: Image.Image, expected: Image.Image) -> float:
    if actual.size != expected.size:
        raise AssertionError(f"size mismatch: {actual.size} vs {expected.size}")
    diff = ImageChops.difference(actual.convert("RGB"), expected.convert("RGB"))
    histogram = diff.histogram()
    channels = 3
    bucket_count = len(histogram) // channels
    mismatched = 0
    total = actual.width * actual.height
    for channel in range(channels):
        channel_hist = histogram[channel * bucket_count : (channel + 1) * bucket_count]
        for value, count in enumerate(channel_hist):
            if value > MAX_CHANNEL_DIFF:
                mismatched += count
    return mismatched / total if total else 0.0


@pytest.fixture(scope="module")
def panel_base_url_module():
    original_bridge = panel_server.BRIDGE
    panel_server.BRIDGE = FakeBridge()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), PanelHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    yield base
    httpd.shutdown()
    thread.join(timeout=2.0)
    panel_server.BRIDGE = original_bridge


@pytest.mark.parametrize(("name", "selector"), PANEL_SHOTS)
def test_panel_regions_match_baseline(name, selector, panel_base_url_module):
    if os.environ.get("SKIP_PANEL_VISUAL") == "1":
        pytest.skip("SKIP_PANEL_VISUAL=1")

    baseline_path = SCREENSHOT_DIR / f"{name}.png"
    update = os.environ.get("UPDATE_PANEL_SCREENSHOTS") == "1"

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport=VIEWPORT, device_scale_factor=1)
            page.goto(panel_base_url_module, wait_until="networkidle", timeout=20000)
            page.wait_for_selector(selector, timeout=20000)
            element = page.locator(selector).first
            png_bytes = element.screenshot(type="png")
            browser.close()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"playwright chromium unavailable: {exc}")

    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    actual_path = SCREENSHOT_DIR / f"{name}.actual.png"
    actual_path.write_bytes(png_bytes)

    if update or not baseline_path.exists():
        baseline_path.write_bytes(png_bytes)
        if update:
            return

    actual = Image.open(actual_path)
    expected = Image.open(baseline_path)
    ratio = _image_diff_ratio(actual, expected)
    try:
        assert ratio <= MAX_MISMATCH_RATIO, (
            f"{name}: {ratio:.4f} of pixels differ (max {MAX_MISMATCH_RATIO}); "
            f"see {actual_path.name}"
        )
    finally:
        if ratio <= MAX_MISMATCH_RATIO and actual_path.exists():
            actual_path.unlink()
