"""PyVista plotter setup: mono/stereo guard, studio background, helpers."""

from __future__ import annotations

import struct
import tempfile
import zlib
from pathlib import Path
from typing import Any

# Radial studio BG: darker center → slightly brighter edges (subtle, not washed out)
_BG_CENTER = (0x1C, 0x20, 0x2A)  # cool dark hub
_BG_EDGE = (0x32, 0x38, 0x46)  # soft rim — only a mild lift vs center
# Wide enough for 16:9 / typical twin window (avoids black letterbox bars)
_BG_RADIAL_W = 1280
_BG_RADIAL_H = 800
_BG_RADIAL_VERSION = 3  # bump to regenerate cached PNG


def require_pyvista() -> Any:
    try:
        import pyvista as pv
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(f"PyVista required: pip install pyvista\nOriginal error: {exc}") from exc
    return pv


def safe_remove(pl: Any, name: str) -> None:
    try:
        pl.remove_actor(name)
    except Exception:
        pass


def force_mono_render(pl: Any) -> None:
    """Kill red/blue anaglyph stereo and MSAA line fringes (macOS VTK).

    Root cause of the purple scene + double red/blue chamber edges: VTK's
    default interactor binds key ``3`` to *toggle stereo* (RedBlue anaglyph).
    Our live mode also uses ``3`` for fan ON — so every fan press enabled stereo.

    Only StereoRenderOff — never SetStereoTypeTo* (Cocoa logs WARN for
    CrystalEyes / unsupported stereo type changes on the window).
    """
    try:
        rw = pl.render_window
    except Exception:
        return
    try:
        if rw.GetStereoRender():
            rw.StereoRenderOff()
    except Exception:
        try:
            rw.StereoRenderOff()
        except Exception:
            pass
    try:
        if rw.GetMultiSamples() != 0:
            rw.SetMultiSamples(0)
    except Exception:
        pass
    try:
        pv_theme = require_pyvista().global_theme
        if getattr(pv_theme, "multi_samples", None) != 0:
            pv_theme.multi_samples = 0
    except Exception:
        pass


def install_stereo_guard(pl: Any) -> None:
    """Re-assert mono every frame / key so VTK default '3'=stereo cannot stick."""

    def _on_start(_obj: Any = None, _evt: Any = None) -> None:
        force_mono_render(pl)

    try:
        pl.render_window.AddObserver("StartEvent", _on_start)
    except Exception:
        pass
    # VTK CharEvent handles '3' as stereo toggle *after* some key callbacks.
    # Kill stereo on every key so fan key never leaves anaglyph on.
    try:
        iren = pl.iren.interactor if hasattr(pl, "iren") and pl.iren is not None else None
        if iren is not None:
            iren.AddObserver("KeyPressEvent", _on_start)
            iren.AddObserver("CharEvent", _on_start)
    except Exception:
        pass
    force_mono_render(pl)


def clear_vtk_default_keys(pl: Any) -> None:
    """Clear per-key PyVista callbacks we will rebind (never wipe all keys).

    Do **not** call ``clear_key_event_callbacks()`` — that drops every binding
    (including HOME 7/c) and was why camera presets appeared dead in live mode.
    """
    keys = (
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "KP_7",
        "8",
        "KP_8",
        "9",
        "KP_9",
        "0",
        "KP_0",
        "s",
        "S",
        "r",
        "R",
        "w",
        "W",
        "c",
        "C",
        "i",
        "I",
        "f",
        "F",
        "h",
        "H",
        "u",
        "U",
        "m",
        "M",
        "p",
        "P",
        "j",
        "J",
        "k",
        "K",
        "minus",
        "equal",
        "plus",
        "-",
        "=",
        "bracketleft",
        "bracketright",
        "[",
        "]",
        "Up",
        "Down",
        "Left",
        "Right",
        "Escape",
        "Tab",
        "Return",
        "KP_Enter",
        "space",
    )
    iren = getattr(pl, "iren", None)
    if iren is None:
        return
    clear = getattr(iren, "clear_events_for_key", None)
    if clear is None:
        return
    for key in keys:
        try:
            clear(key)
        except Exception:
            pass


def _radial_bg_cache_path() -> Path:
    """Temp file only — never write into the package tree."""
    name = f"growbox_ml_twin_radial_bg_v{_BG_RADIAL_VERSION}.png"
    return Path(tempfile.gettempdir()) / name


def _write_png_rgb(path: Path, width: int, height: int, rgb: bytes) -> None:
    """Minimal RGB PNG writer (no Pillow dependency)."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw = bytearray()
    row = width * 3
    for y in range(height):
        raw.append(0)  # filter None
        raw.extend(rgb[y * row : (y + 1) * row])
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
        + chunk(b"IEND", b"")
    )


def _ensure_radial_background_png() -> Path:
    """Dark center, brighter outside — elliptical falloff matching window aspect."""
    path = _radial_bg_cache_path()
    if path.is_file() and path.stat().st_size > 200:
        return path

    w, h = _BG_RADIAL_W, _BG_RADIAL_H
    c0 = _BG_CENTER
    c1 = _BG_EDGE
    half_w = (w - 1) * 0.5
    half_h = (h - 1) * 0.5
    r_max = (1.0 + 1.0) ** 0.5  # unit-ellipse corner
    pixels = bytearray(w * h * 3)
    for y in range(h):
        ny = (y - half_h) / half_h
        row = y * w * 3
        for x in range(w):
            nx = (x - half_w) / half_w
            r = (nx * nx + ny * ny) ** 0.5 / r_max
            if r > 1.0:
                r = 1.0
            # Gentle ease-in: keep center flat longer, only soft lift near rim
            t = r * r  # quadratic — subtler than smoothstep at mid radii
            i = row + x * 3
            pixels[i] = int(c0[0] + (c1[0] - c0[0]) * t)
            pixels[i + 1] = int(c0[1] + (c1[1] - c0[1]) * t)
            pixels[i + 2] = int(c0[2] + (c1[2] - c0[2]) * t)
    _write_png_rgb(path, w, h, bytes(pixels))
    return path


def apply_studio_background(pl: Any) -> None:
    """Circular gradient: darker in the center, brighter toward the edges."""
    edge = [c / 255.0 for c in _BG_EDGE]
    center = [c / 255.0 for c in _BG_CENTER]
    # Letterbox fill matches rim (never pure black bars)
    try:
        pl.set_background(edge)
    except Exception:
        pl.set_background("#323846")

    try:
        try:
            pl.remove_background_image()
        except Exception:
            pass
        png = _ensure_radial_background_png()
        pl.add_background_image(str(png), scale=1.05, auto_resize=True)
    except Exception:
        try:
            pl.set_background(center, top=edge)
        except Exception:
            pass


def configure_plotter(pl: Any) -> None:
    """Stable look: mono only, no scalar bar, no MSAA color fringes."""
    apply_studio_background(pl)
    force_mono_render(pl)
    try:
        pl.disable_anti_aliasing()
    except Exception:
        pass
    try:
        pl.remove_scalar_bar()
    except Exception:
        pass
    install_stereo_guard(pl)
