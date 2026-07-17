"""Backward-compatible CLI / re-export for the twin package.

Run: ``python -m tools.ml.twin_view …``
Prefer: ``from tools.ml.twin import …`` for library use.
"""

from __future__ import annotations

# Public rendering / live API
from tools.ml.twin.cli import build_parser, main
from tools.ml.twin.hud import FONT_COLOR, FONT_FAMILY, FONT_SIZE
from tools.ml.twin.live import render_snapshot, run_interactive_live, run_rollout
from tools.ml.twin.meshes import SCENE_LABEL_FONT_SIZE, build_static_meshes, pot_label_text

# Private names kept for existing tests / call sites
_FONT_FAMILY = FONT_FAMILY
_FONT_SIZE = FONT_SIZE
_FONT_COLOR = FONT_COLOR
_SCENE_LABEL_FONT_SIZE = SCENE_LABEL_FONT_SIZE
_pot_label_text = pot_label_text

__all__ = [
    "build_parser",
    "build_static_meshes",
    "main",
    "render_snapshot",
    "run_interactive_live",
    "run_rollout",
]

if __name__ == "__main__":
    raise SystemExit(main())
